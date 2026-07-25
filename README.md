# Turing — a verification gate for generated code

**Premise:** the interesting part of routing work between cheap and expensive LLMs
isn't the router. It's the **gate** — the thing that decides whether generated
output is good enough. Get the gate right and you can safely default to a cheap
model; get it wrong and you either ship broken work or pay for a frontier model
you didn't need.

This repo contains that gate, plus the experiments that produced the claim.

---

## The finding in one table

Measured across ~30 coding tasks and several thousand oracle judgements
(total API spend for the whole investigation: **~$4**):

| Question | Answer |
|---|---|
| Do you need a frontier model to *write* well-specified code? | **No.** Haiku 4.5 passed ~30 tasks (easy → contest-hard → a self-modifying VM interpreter); Opus cost 4–6× and added nothing. |
| Does escalation-on-failure pay? | Rarely fires — but behind a gate it made the cascade **81% cheaper than always-Opus at equal verified quality**. |
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

Generate five Wordles from the cheap model and gate them (costs a few cents):

```bash
uv run --with anthropic --with playwright --with pillow python constrained_gen.py
```

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
| `gate/browser_gate.py` | earlier standalone runner (superseded by `core/`) |
| `gate/*_spec.py` | per-vertical oracle + functional checks |
| `gate/scaffold/`, `gate/fixtures/` | scaffolds we own; correct/broken test fixtures |
| `gate/constrained_gen*.py` | generate a logic slot → inject → gate |
| `gate/run_cascade_calc.py` | the cheap→strong cascade, measured |
| `gate/auto_gate.py`, `oracle_consensus.py`, `stress_*.py` | can the system write and verify its own oracles? |
| `gate/subtlety_ladder.py`, `fuzz_gate.py`, `coverage_gate.py` | how subtle can a bug get before the gate misses it? |
| `gate/content_spec.py`, `run_content_gate.py` | the objective boundary for content/UI pages |
| `docs/gate-operations.md` | human review, monitoring, failure handling |
| `docs/PROJECT-LOG.md` | full decision/milestone/question log |
| `archive/` | concluded exploration + dead ends, with notes |

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
