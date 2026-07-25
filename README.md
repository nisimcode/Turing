# Turing — a verification gate for generated code

> **AI agents:** Before analyzing, planning, or changing this repository, read
> [`docs/PROJECT-LOG.md`](docs/PROJECT-LOG.md) in full. It is the source of truth
> for current status, decisions, completed work, open questions, and the exact
> resume point. Update it after completing work; do not rely on chat history
> alone.

**Premise:** the interesting part of routing work between cheap and expensive LLMs
isn't the router. It's the **gate** — the thing that decides whether generated
output is good enough. Get the gate right and you can safely default to a cheap
model; get it wrong and you either ship broken work or pay for a frontier model
you didn't need.

This repo contains that gate, plus the experiments that produced the claim.

---

## The finding in one table

Measured across ~30 coding tasks and several thousand oracle judgements
(recorded API spend for the whole investigation: **~$5.2**):

| Question | Answer |
|---|---|
| Do you need a frontier model to *write* well-specified code? | **No.** Haiku 4.5 passed ~30 tasks (easy → contest-hard → a self-modifying VM interpreter); Opus cost 4–6× and added nothing. |
| Does escalation-on-failure pay? | **Yes on the controlled Q26 workload:** 21/21 correct, 0 false accepts/rejects, 14.3% escalation, and **65.7% lower modeled cost than always-Opus**. |
| Where *does* the strong model earn its price? | **Following a spec that contradicts its training prior.** On deliberately non-standard rules: Haiku 53–88%, Sonnet 100%, Opus 100%. |
| Can the system generate its own tests? | Yes. Auto-generated oracles caught **12/12** bugs from obvious through canonical-edge. |
| Where do auto-generated gates go blind? | **Arbitrary-point faults** (`n === 1847`). A fixed battery misses them **3/3**; differential fuzzing recovers **2/3**. |
| Can a bad oracle be detected without ground truth? | Yes — cross-tier **disagreement** flagged **55/55** oracle errors, with **0** unanimous-wrong across 83 adversarial inputs. |

**Design that falls out of it:**

```
cheap model fills a narrow logic slot
        │
        ▼
   OBJECTIVE GATE  ── runtime floor (loads, no JS errors, renders, interactive)
                   └─ functional check vs an oracle / reference implementation
        │
   pass ┴ fail ──► escalate to a stronger tier (only on verified failure)
```

Oracles are verified by a **tier-diverse ensemble**: unanimous ⇒ accept; *any*
disagreement ⇒ escalate that case to the strongest model. Never majority-vote —
three samples of one cheap model fail together.

---

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
cp .env.example .env          # then paste your Anthropic API key
uv run --with playwright python -m playwright install chromium
```

Run the gate against the bundled fixtures — a correct Wordle and a subtly broken
one (wrong duplicate-letter colouring):

```bash
cd gate
uv run --with playwright --with pillow python verify_cli.py \
    --vertical wordle fixtures/wordle_correct.html fixtures/wordle_broken.html
```

```
wordle_correct.html    PASS  wordle_logic=ok
wordle_broken.html     FAIL  wordle_logic=FAIL
  => Gate sees correctness: CONFIRMED
```

Both files pass the runtime floor — only the functional layer catches the bug.
That gap is the whole point of the project.

Artifacts run **sandboxed**: served from an ephemeral loopback origin in a temp
directory, with every outbound request blocked and a fresh browser context per
run. Prove it with the exfiltration probe, which phones home four ways:

```bash
uv run --with playwright --with pillow python verify_cli.py fixtures/exfiltrate.html
# -> all 4 requests blocked; artifact FAILS on no_outbound_requests
```

Before running the paid auto-vertical mutation experiment, run its zero-credit
pre-human checkpoint:

```bash
cd gate
uv run --with anthropic --with playwright --with pillow python offline_all_check.py
```

The live command checkpoints every successful response, runs only one vertical,
and refuses to exceed its declared paid-response budget:

```bash
uv run --with anthropic --with playwright --with pillow python auto_vertical.py \
    --mutation-score --request-index 0 --max-paid-calls 25
```

Human-review triggers are written to an append-only local queue. Inspect,
resolve, or export it without loading Playwright or making an API call:

```bash
cd gate
uv run python review_cli.py list
uv run python review_cli.py list --eligible
uv run python review_cli.py show REVIEW_ID
uv run python review_cli.py resolve REVIEW_ID \
    --disposition clarified --note "Document the decision here"
uv run python review_cli.py status VERTICAL REVISION
uv run python review_cli.py export --output review-queue.html
```

For the first ten-dossier human validation, runnable UIs and immutable packets
can be materialized locally:

```bash
uv run python review_cli.py q25-handoff --output q25-handoff
# review each item, resolve it with --reviewer-seconds, then:
uv run python review_cli.py q25-report
```

Approvals are bound to the exact SHA-256 revision of the scaffold, spec,
implementation, oracle, and control. A changed revision is blocked; clarification
forces regeneration. New verticals cannot be approved until the baseline,
buggy-control, oracle, domain, and ≥5-mutant coverage checks all pass.

The exact-response checkpoint cache remains the primary protection for
interrupted experiments: a hit makes no API call. Anthropic prompt caching is a
separate, opt-in optimization in `core.llm.call(cache_system=True)`, reserved
for a large stable system prefix reused across paid requests. Automatic caching
is deliberately disabled because most gate calls have a changing final prompt.
Cache reads/writes are included in `cost_report()` using the API usage fields.

Create a shareable AI-context snapshot with the pinned Repomix tool:

```bash
pnpm install --frozen-lockfile --ignore-scripts
pnpm repomix
```

This produces a gitignored `repomix-output.xml`. The tracked `.repomixignore`
keeps secrets, machine-local settings, dependency/cache state, generated
review/runtime data, archived research, and lockfile noise out of the bundle.
Repomix’s sensitive-data scan remains enabled.

Reproduce the Q26 three-arm economics result without another API call:

```bash
cd gate
uv run --with anthropic --with playwright --with pillow python q26_economics.py \
  --trials 3 --max-paid-calls 42 --cache-only
```

The fixed seven-task matrix uses disjoint visible and hidden case sets. Across
21 paired task-trials, always-cheap was correct 18/21, always-strong 21/21, and
the gated cascade 21/21. The gate rejected all three cheap failures, escalated
them, and produced zero false accepts or false rejects. This is directional
evidence, not a production-volume confidence claim.

---

## How a vertical works

Free-form generation is unreliable at honouring a test contract (measured: 3/6).
So the scaffold is **ours** and the model fills a narrow slot — conformance and a
working UI become structural rather than hoped-for (5/5):

```
gate/scaffold/wordle_scaffold.html   # our UI + the window.__wordle hook
        └── /*__LOGIC_SLOT__*/       # the model supplies computeFeedback()
gate/wordle_spec.py                  # oracle + acceptance battery
```

Adding a vertical = one scaffold + one spec + one prompt. **The gate itself never
changes.** Proven on four: Wordle, 2048, a bill splitter, and an expression
calculator.

---

## Layout

| Path | What |
|---|---|
| **`gate/core/`** | **the module: `verify(artifact) -> Verdict`, sandbox, checks, config, llm** |
| `gate/verify_cli.py` | CLI entry point — `python verify_cli.py --vertical wordle x.html` |
| `gate/auto_vertical.py` | build a whole vertical (scaffold + oracle + gate) from a plain request |
| `gate/offline_q24_check.py` | zero-credit preflight for auto-battery mutation scoring |
| `gate/offline_q25_check.py` | zero-credit Q25 eligibility, probe, and mutation regression |
| `gate/q26_economics.py` | checkpointed paired always-cheap / always-strong / cascade benchmark |
| `gate/offline_q26_check.py` | zero-credit controls for Q26 tasks, holdouts, and economics |
| `gate/offline_q21_check.py` | zero-credit regression for domain ambiguity and false rejects |
| `gate/offline_all_check.py` | complete zero-credit checkpoint before human review |
| `gate/review_cli.py` | inspect, resolve, and export the append-only human-review queue |
| `gate/offline_review_check.py` | zero-credit end-to-end review workflow regression |
| `gate/*_spec.py` | per-vertical oracle + functional checks |
| `gate/scaffold/`, `gate/fixtures/` | scaffolds we own; correct/broken test fixtures |
| `docs/gate-operations.md` | human review, monitoring, failure handling |
| `docs/human-testing.md` | exact preconditions and protocol for first human validation |
| `docs/PROJECT-LOG.md` | full decision/milestone/question log |
| `.repomixignore` | exclusions for safe, active-code-only Repomix snapshots |
| `package.json`, `pnpm-lock.yaml` | pinned local Repomix development tool |
| `archive/gate-experiments/` | concluded gate experiments and predecessor runners |
| `archive/eval/`, `archive/gate-deadends/` | initial exploration and failed approaches |
| `archive/plans/` | completed and superseded planning documents |

---

## Status and limits

Research prototype, not a product. Known boundaries, all measured:

- **Scope.** Validated only where the critical logic is a checkable pure function
  (games, calculators, validators). Content/UI-heavy sites have a functional
  floor but a subjective core the gate can't judge.
- **Not a security boundary.** A fault behind an arbitrary trigger evades any
  finite test battery. The gate catches honest mistakes, not hidden behaviour.
- **Oracle risk.** A wrong oracle looks exactly like wrong code. Disagreement
  flagging handles it in practice; a spec so obscure that *every* tier reverts
  would still go undetected.
- Sample sizes are small throughout — directional evidence, not proof.

See `docs/PROJECT-LOG.md` for every decision, result, and open question.

---

## Licence

**Proprietary — all rights reserved.** See [`LICENSE`](LICENSE). The source is
visible for evaluation only; it is not open source and no usage rights are
granted. Contact the copyright holder for licensing.
