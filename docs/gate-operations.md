# Gate operations — human review, monitoring, and failure handling

Answers Q18. Every rule here is grounded in a measured result; the source is
cited so the rule can be re-derived (or overturned) when the evidence changes.

The gate is trustworthy in aggregate but has three known blind spots. This
document says who watches them and when.

---

## 1. The one rule that governs everything

**False accepts are fatal; false rejects only cost margin.** Ship broken work and
you lose the customer; escalate unnecessarily and you lose a few cents. Every
ambiguous call resolves toward *reject and escalate*, never toward *accept*.

Corollary: **correctness is a floor, never a user-facing dial.** The user may
tune effort, polish, and budget *above* "it works" — never below it.

### Public deterministic path

The supported adoption path is the packaged `turing-gate` CLI plus a version-1
JSON manifest. It requires no model, API key, account, or hosted service:

```bash
uv run turing-gate install-browser
uv run turing-gate doctor
uv run turing-gate demo
uv run turing-gate init tool.html
uv run turing-gate verify turing.json
```

On Linux, `turing-gate install-browser --with-deps` also installs Playwright's
required operating-system libraries. `doctor` makes no model/API calls and
tests Python/package discovery, the local telemetry directory, loopback
binding, Playwright, the Chromium executable, and an actual JavaScript-capable
browser launch. It returns exit `2` with a repair command when setup is
incomplete; `--json` is stable machine-readable output.

The manifest binds one self-contained HTML artifact to a dotted browser hook,
machine-readable argument domain, and explicit input/expected-output cases.
Artifact paths are confined to the manifest directory. A runtime-only manifest
is allowed for containment diagnostics but emits a warning because it cannot
establish correctness.

`init` creates a schema-version-1 manifest beside an existing HTML artifact.
It never guesses expected behavior: functional mode requires an explicit hook
and at least one JSON case. Without them it produces a prominently labeled
runtime-only starter. Creation validates through the same manifest loader,
publishes atomically, rejects paths outside the manifest directory, and refuses
overwrite unless `--force` is explicit.

The public CLI records only a local audit trail at
`.turing/telemetry.jsonl`; nothing is transmitted. Exit `0` means all declared
checks passed, `1` means a checked artifact was rejected, and `2` means the
manifest or local browser setup is incomplete.

The built wheel excludes model-assisted auto-vertical generation and research
runners. Those remain source-repository experiments and must not be presented
as part of the dependable public workflow.

`.github/workflows/clean-room.yml` builds the wheel and exercises this public
path on fresh Windows and Linux GitHub-hosted runners for every push and pull
request. It is a clean-environment installation proxy only. It does not replace
unassisted onboarding or count toward the 20/5/3 outside-adoption target.

The same workflow runs `gate/offline_benchmark_check.py` against the paired
logic-tool corpus in `benchmarks/`. Release confidence requires all correct
controls accepted, all broken controls rejected, zero false accepts/rejects,
and the intended diagnostic label for every broken control. Runtime is reported
as total, median and p95. Because cases and defects are hand-authored together,
this is regression evidence only; it is not a production error-rate estimate.

It then runs `gate/offline_benchmark_mutation_check.py --require-perfect`.
Mechanical source mutations count only after execution finds a divergence on
versioned probes whose exact arguments are absent from the scored manifests.
Every counted mutant must then be killed by the manifest cases. Report
survivors rather than discarding them; strengthen the cases with a distinct
example before moving the checkpoint back to green. A perfect score is bounded
to the generated operators and probes, not a guarantee against unknown faults.

---

## 2. Where humans are required

Automation covers the steady state. Humans cover creation and anomalies.

| Trigger | Why | Action |
|---|---|---|
| **A new vertical is created** | The oracle has never been validated for this spec. A wrong oracle is invisible: it looks exactly like wrong code. | Human reviews the generated oracle/reference against the spec once, before the vertical serves traffic. One-time cost per vertical. |
| **The spec deviates from a common convention** | Cheap tiers revert to their training prior and fail *together*: 53–88% vs 100% for strong tiers (`archive/gate-experiments/stress_unanimous.py`). | Flag at authoring time. Require strong-tier oracle + human confirmation of the deviating rule. |
| **The strongest tier fails the gate** | There is nowhere left to escalate. The lazy failure mode is to accept anyway "because it's the best we have" — that is the fatal error. | Reject. Route to a human. Never auto-accept a top-tier failure. |
| **Flag rate leaves its normal band** | Disagreement rate is a live difficulty signal (§3). | Investigate the spec before it silently burns budget. |
| **Ambiguous-edge disagreement** (Q21) | Broad coverage hits inputs the spec never addressed (e.g. `""` as a card number); the reference's arbitrary choice becomes "truth" and correct code fails. | Do not auto-fail. Surface as *spec clarification needed* — the fix is a better spec, not a different implementation. |

Everything else runs unattended.

### Review queue workflow

`core.policy.assess()` opens a deduplicated pending item in
`gate/review-queue.jsonl` and returns its stable review ID. The queue is
append-only: resolving an item adds an audit event rather than rewriting its
creation record. New-vertical review material is SHA-256-bound to the exact
scaffold, implementation, control, sharpened specification, and oracle battery.

```bash
cd gate
uv run python review_cli.py list
uv run python review_cli.py show REVIEW_ID
uv run python review_cli.py resolve REVIEW_ID \
  --disposition approved --note "Why this is safe to accept"
uv run python review_cli.py status VERTICAL REVISION
uv run python review_cli.py export --output review-queue.html
```

Allowed dispositions are `approved`, `clarified`, and `rejected`. The exported
HTML is a read-only escaped view; the JSONL queue and HTML export are local
runtime artifacts and gitignored. Lifecycle projection is fail-closed:
`approved` is the only production-eligible state. Pending, unreviewed, stale
revision, clarified/needs-rebuild, rejected, invalid, tampered, or corrupt
history is blocked. A provisional item or top-tier failure cannot be approved.
For a new vertical, approval is also refused until all seven automated release
checks pass, including 100% coverage of at least five execution-validated
mutants.

Use the release guard when gating a production candidate:

```bash
uv run --with playwright --with pillow python verify_cli.py \
  --vertical VERTICAL --revision REVISION --require-approved ARTIFACT.html
```

### Before asking a human

Run the complete deterministic checkpoint:

```bash
uv run --extra ai python offline_all_check.py
```

It makes no model requests. It composes the review and lifecycle state-machine
tests, public-manifest and adoption-demo controls, Q21 domain regression, Q24
mutation/cache/cost preflight, the independent six-domain mechanical-fault
challenge, Q26 task and economics controls, correct and known-broken Wordle
controls, and the four-vector exfiltration control. Human review starts only
after it reports
`OFFLINE PRE-HUMAN CHECKPOINT: PASS`.
The exact reviewer protocol is in `docs/human-testing.md`.

For Q25, `auto_vertical.py --mutation-score --q25-mode` replaces paid probe
generation with deterministic schema-derived probes and combines one
model-proposed mutant with execution-validated local mutations. Only packets
that pass all seven release checks appear under `review_cli.py list --eligible`.
`review_cli.py q25-handoff` materializes runnable UIs and immutable JSON
dossiers; `q25-report` aggregates the human dispositions, timing, and finding
flags. Blocked and provisional attempts remain in the append-only audit queue
but cannot contaminate the eligible ten-dossier sample.

---

## 3. Flag-rate monitoring

Oracle disagreement is measured per case and **self-adjusts to spec difficulty**
(D24) — the system spends more verification effort exactly where the work is
unusual:

| Spec type | Observed flag rate | Source |
|---|---|---|
| Canonical / conventional | ~3% | `archive/gate-experiments/oracle_consensus.py` (1/30) |
| Prior-fighting / non-standard | ~50% | `archive/gate-experiments/stress_consensus.py` (16/32) |

Use it as an alarm, not just a cost line:

- **Flag rate spikes on a stable vertical** → the spec changed, the model
  changed, or an input distribution shifted. Investigate before it costs money.
- **Flag rate near zero on a *new* vertical** → suspicious, not reassuring. It
  may mean the oracle ensemble lacks tier diversity (D22: three samples of one
  cheap model are one opinion, not three) and cannot disagree.
- **Sustained high flag rate** → the spec is fighting the models. Rewrite the
  spec, or pin the vertical to the strong tier and stop paying for the pre-filter.

---

## 4. Resolution rules

**Oracle disagreement → escalate, never vote** (D21). Majority voting is unsafe:
correlated cheap-tier failure produced a confidently wrong majority (45/51) while
the strong tier was perfect (51/51). Unanimity ⇒ accept; any disagreement ⇒ the
strong tier decides that case.

**Coverage by domain size** (D28). Enumerate exhaustively when the input domain is
finite and ≤100k cases; differential-fuzz otherwise. This removed arbitrary-point
false accepts entirely (3/15 → 1/15 → 0/15 across battery → fuzz → coverage-aware).

**Enforce the declared domain before executing an oracle case** (Q21). Every
auto-vertical supplies both a human-readable domain and a machine-readable
argument schema. Cases outside that schema never become pass/fail evidence:
withhold them and emit `spec clarification required`. A missing schema is itself
a clarification trigger. This prevents an arbitrary reference choice for an
undefined input (such as `""` for a 2–19 digit card number) from falsely
rejecting correct code.

**Content/UI verticals are floor-only** (Q13b). Objective checks catch crash,
missing sections, mobile overflow, contrast failures, and collisions (5/5), but
taste and copy quality pass everything (2/2). Sell those verticals as *guaranteed
working, accessible, complete* — never as *guaranteed good*.

---

## 5. Standing limitations — do not design these away

- **The gate is not a security boundary** (D26). A fault behind an arbitrary
  trigger evades any finite battery. It catches honest mistakes, not deliberately
  hidden behaviour. Do not let this be marketed as a safety guarantee.
- **Unanimous-wrong is possible in principle** (Q18/Q17 residual). Not observed in
  83 adversarial inputs, but the defense rests on at least one strong tier
  resisting the prior. A spec strange enough to flip every tier would pass
  silently. The one-time human review of each new vertical exists for this.
- **Sample sizes are small.** Every figure above is directional evidence, not
  proof. Re-measure as volume grows.

---

## 6. API cost controls

The local exact-response cache (`GATE_LLM_CACHE_DIR`) is the first line of
defense for research runs: an exact hit makes no API request. Pair it with
`GATE_LLM_MAX_PAID_CALLS` and, for replays, `GATE_LLM_CACHE_ONLY=1`.

Anthropic prompt caching is different: it still makes a paid request and
generates new output. `core.llm.call()` therefore supports only explicit,
opt-in caching of a stable system prefix (`cache_system=True`, TTL `5m` or
`1h`). Do not enable automatic caching globally or cache a changing per-request
prompt. `cost_report()` accounts separately for uncached input, 5-minute and
1-hour cache writes, cache reads, and output; `cache_report()` exposes the token
totals. A zero-credit fake-client regression covers the request shape and
billing arithmetic in `offline_q24_check.py`.

### Controlled economics benchmark

`q26_economics.py` compares always-cheap, always-strong, and the cheap-first
gated cascade from the same paired samples. Seven fixed logic tasks include
canonical and prior-fighting rules; the visible gate battery and larger local
holdout are disjoint. The experiment checkpoints responses and records their
original prices, so counterfactual policy costs remain reproducible from cache.

The first three-trial run produced 21 task-pairs:

| Policy | Correct accepted | Incorrect accepted | Cost | Cost/correct |
|---|---:|---:|---:|---:|
| Always cheap | 18/21 | 3 | $0.03230 | $0.00179 |
| Always strong | 21/21 | 0 | $0.16421 | $0.00782 |
| Gated cascade | 21/21 | 0 | $0.05636 | $0.00268 |

The gate had 39 true accepts, 3 true rejects, 0 false accepts, and 0 false
rejects across 42 candidate decisions. All three cheap failures escalated and
were recovered by the strong tier: 14.3% escalation and 65.7% modeled savings
versus always-strong. Total research spend to sample both models was $0.19651;
that is not the cascade's counterfactual serving cost.

Replay the saved result at $0:

```bash
uv run --with anthropic --with playwright --with pillow \
  python q26_economics.py --trials 3 --max-paid-calls 42 --cache-only
```

Treat the result as directional: 21 paired tasks are enough to demonstrate the
mechanism and catch a repeatable cheap-tier failure, not enough to establish a
production error-rate bound.
