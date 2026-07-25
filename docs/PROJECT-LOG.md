# Project Log — Turing

**Purpose:** the single running record of this project — decisions made, steps
finished, plans set, and open questions (with when they must be answered). Not a
transcript. Updated as work progresses; newest entries at the top of each section.

**How to maintain:** when a decision is made, add a `D#` row. When a step
finishes, add it to Milestones. When a question arises, add a `Q#` with "when
needed"; when answered, mark it ANSWERED and note the answer. **Stamp new entries
with date AND time** (`YYYY-MM-DD HH:MM TZ`). Keep it terse. (Entries before
2026-07-25 17:29 JDT are date-only — exact times weren't recorded.)

---

## Current status (2026-07-25)

Product = a cost-saving **model cascade** for commercial "build me X" web-app
generation; the **gate** is the do-or-die backbone (D14). Vertical = single-file
browser games (D13). Gate Layer 0 (runtime floor) and Layer 1 (functional, via
the `window.__wordle` contract) are built and running in `gate/`; the gate is
proven to catch a logically-broken game the floor false-accepts.
Phase 2 kill check (first cut) run: gate surfaced BOTH error types on real
output — false-reject from low contract conformance (3/6), false-accept from a
coverage gap (dead game passes). Gate not yet at target.
**Validated core loop, on TWO verticals (Wordle + 2048):** constrained
generation (D16/D17) — model fills a narrow logic slot in a scaffold we own →
inject → gate. Both: conformance 5/5, logic 5/5, buggy control correctly failed.
The gate backbone works and the recipe generalizes.
Recipe proven on THREE verticals + thin cascade wired on the gate: cascade is
81% cheaper than always-Opus at equal quality by defaulting cheap behind the
gate. Escalation rarely/never fires (cheap tier is reliable on well-specified
logic). Net: **the product ≈ one cheap model + a trustworthy gate; escalation is
insurance.**
**Latest (18:24 JDT): the oracle-verification design is validated and Q17 is
closed.** Design: cheap **tier-diverse** ensemble → unanimous ⇒ accept → ANY
disagreement escalates that case to the strong tier (never majority-vote).
Evidence across two adversarial stress tests: **83 inputs, 55 oracle errors, 0
unanimous-wrong, 100% of errors flagged**, strong tier 100% correct. Flag rate
self-adjusts to spec difficulty (3% canonical → 50% adversarial), so cost tracks
need automatically (D24).
**All major research questions are now closed (18:57 JDT).** False accepts are
0/15 with coverage-aware gating; oracle errors are 100% flagged by tier-diverse
disagreement; the scope boundary is mapped (logic-verifiable = correctness
decision, content/UI = floor only); operations are specified in
`docs/gate-operations.md`. Repo is prepped for GitHub (`.gitignore`,
`.env.example`, `README.md`, proprietary `LICENSE`).
**Engineering pass done (19:24 JDT):** the three gaps that blocked "ready" are
addressed — sandboxed execution (D33, exfiltration probe blocked 4/4),
consolidation into `gate.core` with one `verify()` entry point (D32), and
auto-vertical generation proven end-to-end on 1/3 requests (D34). Repo is on
GitHub (private, `main`, proprietary © Nisim Levi).
**Second engineering pass done (19:45 JDT):** spec precision + ensemble oracle
(auto-verticals accept correct code 3/3, D35), ops doc implemented as
telemetry + policy code (D37), and volume validation answering Q5 (30/30,
CI [72%,100%]). Also corrected my own unsafe drop-on-dispute design (D36).
**Q22 and Q23 closed (19:56 JDT):** disputed cases are re-voted per pinned case
and recovered (D38); bug-catching is now measured by **mutation score** on
execution-validated mutants — **100%, 15/15, zero survivors** on the production
batteries (D39).
**Next action:** Q24 — score an AUTO-generated battery the same way (the
hand-written ones are proven; the auto ones that would serve unanticipated
requests are not). Then commit this batch.

---

## Decision log

| # | Date/time | Decision |
|---|------|----------|
| D39 | 2026-07-25 19:56 JDT | **Mutation score is the gate's headline quality metric.** "Catches the bugs we injected" only proves it catches faults we thought of. A mutant counts only once EXECUTION shows a behavioural divergence (models predicted non-existent bugs 2/3 of the time); score = validated mutants killed / validated mutants. Production batteries score **100% (15/15)**. |
| D38 | 2026-07-25 19:56 JDT | **Disputed oracle cases get a focused second pass** (`resolve_disputed`) before being escalated to a human: one pinned case at a time is a far narrower task than drafting a battery, and narrow tasks are done accurately (97-100%). Restores coverage instead of permanently excluding the input; anything still disputed is a spec gap, not arithmetic, and goes to review. |
| D37 | 2026-07-25 19:45 JDT | **Ops doc is now code**: `core/telemetry.py` (durable JSONL of every verdict + flag-rate/pass-rate alarms with the measured 3%/50% baselines) and `core/policy.py` (`assess()` implements the §2 trigger table, returning reasons + a `provisional` flag). `verify()` records every run. |
| D36 | 2026-07-25 19:45 JDT | **Disputed oracle cases must NOT be silently dropped.** Dropping removes that input from testing entirely, so a fault there passes — trading a false reject for a false *accept*, the opposite of the founding rule (D8). Disputed cases are excluded from the battery but recorded, and they make the verdict **PROVISIONAL** pending human resolution. Corrects my own initial design in `core/oracle.py`. |
| D35 | 2026-07-25 19:45 JDT | **Auto-verticals need spec sharpening + an ensemble-verified oracle, together.** Sharpening alone failed (it *widened* the domain to "any JavaScript value" and invented semantics); the fix is a sharpening pass constrained to a NARROW domain, plus recomputing expected values with a tier-diverse ensemble on pinned inputs. Result: correct code accepted 1/3 → **3/3**. |
| D34 | 2026-07-25 19:24 JDT | **Auto-scaffolding is viable; the weak link is SPEC PRECISION, not scaffold generation.** 3/3 auto-generated scaffolds were structurally sound (slot + hook + floor pass); the failures came from underspecified `behaviour` text letting oracle and implementation diverge on edge cases. Fix belongs in the spec step (enumerate edge-case handling, or restrict the oracle's domain to what the spec defines) — same root cause as Q21. |
| D33 | 2026-07-25 19:24 JDT | **All untrusted artifacts execute sandboxed** (`gate/core/sandbox.py`): ephemeral 127.0.0.1 origin rooted in a temp dir (no `file://` host access), every non-artifact request aborted, fresh browser context per run, dialogs/downloads refused, hard timeouts. Outbound attempts are also *reported* — `no_outbound_requests` is a floor check, so code that phones home fails the gate. Docker unavailable on this host; scope limited to single-file HTML/JS, containers still required for build steps/servers/native deps. |
| D32 | 2026-07-25 19:24 JDT | **Consolidated into a `gate.core` package** with one entry point `verify(artifact, functional=...) -> Verdict`, shared config/tiers/pricing, cost accounting and logging — replacing ~12 scripts that each carried their own key loader and browser setup. Verification deliberately does **not** import the Anthropic SDK (lazy), so gating runs in a minimal environment. |
| D31 | 2026-07-25 18:57 JDT | **Gate operations spec written** (`docs/gate-operations.md`) — answers Q18. Humans review at *creation* (each new vertical's oracle) and on *anomaly* (deviating spec, top-tier failure, flag-rate excursion, ambiguous edge); everything else runs unattended. Flag rate doubles as a live spec-difficulty alarm — and near-zero on a NEW vertical is suspicious (may mean the ensemble lacks tier diversity), not reassuring. |
| D30 | 2026-07-25 18:57 JDT | **Content/UI verticals are FLOOR-ONLY.** Objective checks guarantee *working, accessible, complete*; they cannot judge *good*. Sell those verticals on the floor, not on quality — and lead commercially with logic-verifiable verticals where the oracle decides correctness outright. |
| D29 | 2026-07-25 18:53 JDT | **Licence: proprietary / all rights reserved** (`LICENSE`), source-available for evaluation only. Deliberately the restrictive starting point — it can be loosened later, whereas permissions once granted cannot be withdrawn from copies already taken. Copyright-holder name still to be filled in. |
| D28 | 2026-07-25 18:53 JDT | **Coverage-aware gating is the production design** (`gate/coverage_gate.py`): the strong tier declares the input domain; enumerate exhaustively when finite and ≤100k cases, otherwise differential-fuzz. Removes arbitrary-point false accepts entirely (0/15). Accept the resulting rise in spec-ambiguity false rejects — trading fatal errors for margin cost. |
| D27 | 2026-07-25 18:41 JDT | **Gate strategy by domain size: enumerate exhaustively when the input domain is small and finite (e.g. int 1..3999); random differential fuzzing otherwise.** Fuzz coverage is only as good as the generator's distribution — the one L5 miss was an unreachable-in-practice value under a skewed generator, which exhaustive enumeration removes entirely. |
| D26 | 2026-07-25 18:35 JDT | **The gate is a correctness check, NOT a security boundary.** An arbitrary trigger (magic value / rare substring) reliably evades a finite battery, so the gate cannot be relied on to stop deliberately hidden behaviour. Fine for verifying honest generation; do not market it as a safety guarantee against malicious code. |
| D25 | 2026-07-25 18:35 JDT | **Move from fixed batteries to differential/property testing where the slot is a pure function.** Have the strong tier emit a REFERENCE IMPLEMENTATION as well as cases, then fuzz the cheap model's slot against it over random inputs. Converts finite coverage into probabilistic coverage of the whole input space — the only way to close the L5 gap. |
| D24 | 2026-07-25 18:24 JDT | **The flag rate self-adjusts to spec difficulty** — 3% flagged on canonical specs, 50% on prior-fighting ones. The system automatically spends more verification effort where the spec is unusual. This is the adaptive behaviour originally wanted from a "boss", achieved by *verification* rather than *prediction*. |
| D23 | 2026-07-25 18:24 JDT | **The STRONG tier is the oracle authority; the cheap ensemble is a cost-saving pre-filter that decides when to consult it.** Across both stress tests Sonnet/Opus were 100% correct and a strong tier was right on 100% of inputs; safety rests on that, not on voting. Cheap models only decide *when* to ask. |
| D22 | 2026-07-25 18:18 JDT | **Ensemble DIVERSITY beats ensemble size.** 3 samples of the same cheap model are highly correlated — they failed together. The disagreement signal only existed because tiers differed (Haiku vs Sonnet/Opus). Always build the oracle ensemble across model *tiers*, never as N samples of one model. |
| D21 | 2026-07-25 18:18 JDT | **Use disagreement as a TRIPWIRE, not a vote.** Never majority-vote oracle values: on adversarial specs the 3 cheap voters were wrong together and the majority was confidently wrong (45/51 vs Opus 51/51). Correct design: cheap ensemble → if unanimous, accept; if ANY disagreement, escalate that case to the strongest model (or a human). Opus was right on 100% of flagged cases. |
| D20 | 2026-07-25 18:18 JDT | **QUALIFIES D19 / partly restores D18.** Cheap-ensemble oracles are only sufficient on canonical tasks. When the spec CONTRADICTS a famous convention (real custom business rules), cheap models revert to the prior and fail together: Haiku 84–88% vs Sonnet 100% / Opus 100%. Strong models earn their price on instruction-following against a trained prior. |
| D19 | 2026-07-25 18:09 JDT | **REVISES D18. Decompose the oracle task, then ensemble cheap models.** Split oracle generation into (1) choose test inputs and (2) compute expected values for pinned inputs. Step 2 is narrow: 3× Haiku majority scored 30/30 at $0.023 vs 1× Opus 29/30 at $0.045 — cheaper AND more accurate. Don't buy a big model for the oracle; buy decomposition + redundancy. (D18 held only for one free-form "write the whole battery" ask.) |
| D18 | 2026-07-25 18:03 JDT | **Tier by ROLE, not by task difficulty:** cheap model *generates code*, strong model *generates the oracle/gate*. Evidence: auto-oracle wrong 2/3 (Haiku) vs 0/3 (Opus) — the first measured case in the whole project where the strong model outperformed. Spend on the verifier, not the builder. |
| D17 | 2026-07-25 17:29 JDT | Standardize the **vertical recipe**: scaffold we own + narrow logic slot + Python oracle + gate + buggy control. Adding a game = new scaffold + spec + prompt (no gate changes). Proven on a 2nd game (2048). |
| D16 | 2026-07-25 | **Constrained generation (Q12a):** own a fixed playable scaffold per game type; the model fills only a narrow logic slot (`computeFeedback`). Conformance + working UI guaranteed by construction. This is the gate/generation approach for the game vertical. |
| D15 | 2026-07-25 | Adopt a **generation contract** (`window.__wordle.{setAnswer,guess}`) so functional gating generalizes across implementations (see `gate/contract.md`). Answers Q9. |
| D14 | 2026-07-25 | **The gate IS the product**; cascade/routing/dial are thin wrappers. Organize effort and planning around the gate as the spine, built in layers (runtime floor → functional → acceptance criteria → judge), not one phase. |
| D13 | 2026-07-25 | First vertical = **single-file (no-build) browser games** (Wordle-like). Answers Q1 and Q4. |
| D12 | 2026-07-25 | Adopt the gate-first phased plan in `docs/implementation-plan.md`. |
| D11 | 2026-07-25 | Start narrow: small self-contained, browser-testable apps (Wordle-like) first — not IGN-scale sites. |
| D10 | 2026-07-25 | Objective checks are the primary gate; LLM judge is secondary — may withhold (escalate) but never approve past an objective failure. |
| D9  | 2026-07-25 | Route/decide on pass@k (rates), never single runs. |
| D8  | 2026-07-25 | Tune the gate conservative: prefer false-rejects to false-accepts — but only up to the point where the cascade still beats always-strong. |
| D7  | 2026-07-25 | Correctness is a non-negotiable floor. The user-facing dial governs effort/polish/budget *above* "it works" — framed as such, never as a reliability knob. |
| D6  | 2026-07-25 | The gate is the backbone; build and *validate* it before any cascade. Do-or-die. |
| D5  | 2026-07-25 | Product target = model cascade for commercial "build me X" web apps (e.g. IGN-like sites, Wordle-like games). |
| D4  | 2026-07-25 | Tiers: Haiku 4.5 (cheap) → Sonnet 5 (mid) → Opus 4.8 (strong) → Fable 5 (optional, deferred: pricier, access/retention constraints). |
| D3  | 2026-07-25 | Tooling: run Python via `uv`; API key read from `E:\Turing\.env` (`CLAUDE_API_KEY`). |
| D2  | 2026-07-25 | Validate empirically with cheap dry runs before building anything. |
| D1  | 2026-07-25 | Pivot from the original "AI Boardroom (Turing)" concept toward escalation/routing (per `docs/plan.md`), then refined to a model cascade. |

---

## Milestones completed

- **2026-07-25 19:56 JDT** — **Q22 answered: mutation testing**
  (`gate/core/mutation.py`, `gate/mutation_check.py`). Mutants are proposed by
  the strong tier but accepted **only when execution demonstrates a divergence**
  — which is the fix for the unreliable buggy-control generator (it *predicted*
  differences instead of showing them). Result on the production batteries:
  **wordle 5/5, game2048 5/5, billsplit 5/5 — mutation score 100%, 0
  survivors**, cost $0.09. First evidence the gate catches faults nobody here
  thought of, rather than only the ones we injected.
  *Harness bug found and fixed en route (the third of its kind today): the
  mutation module hardcoded `window.__fn` while the production scaffolds expose
  `__wordle`/`__game2048`/`__tool`, so every call threw identically for original
  and mutant and all 30 candidates were silently discarded as "no divergence".
  `find_divergence` now aborts loudly when the original throws on every probe.*
  → D39.
- **2026-07-25 19:56 JDT** — **Q23 answered: dispute resolution**
  (`resolve_disputed` in `core/oracle.py`). Disputed cases now get a focused
  per-case second pass across the ensemble before exclusion; recovered cases
  rejoin the battery, so coverage is restored rather than merely made safe.
  Anything still disputed after focused voting is a spec gap and routes to human
  review via `policy.assess()`. → D38.
- **2026-07-25 19:45 JDT** — **Volume validation (Q5 answered)**
  (`gate/volume_check.py`). 10 generations × 3 verticals through the real
  pipeline: **wordle 10/10, game2048 10/10, billsplit 10/10** — pass@1 100%,
  Wilson 95% CI **[72%, 100%]** (n=10 cannot prove better than 72%; reported
  honestly rather than as "100% reliable"). Cost $0.037. Confirms the standing
  conclusion: behind a gate, the cheap tier clears these verticals, so
  escalation is insurance that rarely fires.
- **2026-07-25 19:45 JDT** — **`docs/gate-operations.md` implemented**
  (`core/telemetry.py`, `core/policy.py`). Every `verify()` is recorded to
  JSONL; `alarms()` fires on flag-rate excursions in *both* directions
  (>60% = spec fighting the models; <0.5% on a new vertical = ensemble probably
  lacks tier diversity) and on sustained low pass rate; `assess()` returns the
  §2 human-review triggers with a `provisional` flag. Smoke-tested. → D36, D37.
- **2026-07-25 19:45 JDT** — **Spec precision + ensemble oracle (Q22)**.
  Sharpening alone made things *worse* (it widened the domain to "any JavaScript
  value"); constraining it to a narrow domain AND recomputing expectations with
  a tier-diverse ensemble fixed it: **correct code accepted 1/3 → 3/3**. The
  ensemble automatically caught and corrected a real oracle error
  (`draft corrected on [123, 1]: '234' -> '123'` — the strong tier had
  miscomputed a Caesar shift), which is the validated design working unattended.
  Two harness bugs fixed en route: NaN never compares equal (false rejects), and
  the buggy-control generator still produces non-bugs in 2/3 cases (Q22 open).
  → D35.
- **2026-07-25 19:24 JDT** — **Auto-generated VERTICALS tested**
  (`gate/auto_vertical.py`). From a plain request the pipeline generates
  scaffold → oracle → implementation → buggy control, then gates it via
  `gate.core`. Result **1/3 fully working** (anagram checker: correct code
  accepted, injected bug caught, control confirmed genuine).
  The other two did **not** fail on scaffolding — all 3 scaffolds were
  structurally sound (slot + hook + floor pass) and all 3 oracles generated.
  They failed on **spec ambiguity**: the temperature converter's oracle wanted
  `None` for empty input while the impl returned `32` (false reject — the same
  `""` class as Q21); the Caesar cipher's "buggy" control did not actually
  differ from the correct code, so its result is inconclusive rather than a
  false accept. Cost $0.24. → D34.
- **2026-07-25 19:24 JDT** — **Sandboxed execution shipped** (`gate/core/sandbox.py`)
  — closes the standing security gap (generated JS had been running on the host
  via `file://`). Verified with `gate/fixtures/exfiltrate.html`, a benign-looking
  page that phones home four ways: **all 4 blocked** (fetch, image pixel,
  sendBeacon, XHR) and the artifact **failed** the gate on
  `no_outbound_requests`. Docker is not installed on this host, so isolation is
  built from browser-level controls; honest scope limits documented in the module.
- **2026-07-25 19:24 JDT** — **Research scripts consolidated into `gate.core`**
  — `config` / `llm` / `sandbox` / `checks` / `verify` plus a `verify_cli.py`
  entry point. Re-verified through the new module: `wordle_correct` PASS,
  `wordle_broken` FAIL on `wordle_logic` — correctness detection survives the
  refactor. Fixed a real bug found en route: `extract_code`'s optional language
  tag matched a *closing* fence and silently returned garbage (it broke all 3
  auto-verticals on the first run); replaced with strict `extract_block`. → D32.
- **2026-07-25 18:57 JDT** — **Q18 answered: gate operations spec**
  (`docs/gate-operations.md`). Codifies who watches the three known blind spots:
  human review at vertical *creation* + on anomaly; flag-rate monitoring as a
  spec-difficulty alarm; escalate-never-vote; top-tier failure ⇒ reject to human,
  never auto-accept; ambiguous-edge disagreements route to spec clarification
  rather than auto-fail. Every rule cites the measurement it came from. → D31.
- **2026-07-25 18:57 JDT** — **Q13b answered: the objective boundary for
  content/UI** (`gate/content_spec.py`, `gate/run_content_gate.py`, 8 landing-page
  fixtures). Defect ladder result: **objectively-checkable defects caught 5/5**
  (blank render, missing section, mobile overflow at 375px, WCAG contrast
  failure, element collision); **subjective defects passed 2/2** (garish but
  fully accessible design; contentless marketing copy); **false rejects 0/1**.
  Conclusion: for content/UI the gate is a **floor** (works / usable / complete),
  not a **quality bar** — the inverse of the tool & game verticals where the
  oracle decides correctness outright. → D30.
  *Two fixture/check artifacts were found and fixed mid-run: `required_sections`
  matched nav-link text rather than headings, and the "ugly but valid" fixture
  accidentally violated contrast (so it wasn't isolating pure taste).*
- **2026-07-25 18:53 JDT** — **Coverage-aware gating closes the false-accept gap**
  (`gate/coverage_gate.py`) — answers Q20. The strong tier now also declares the
  domain via `enumerateDomain()`; roman was correctly identified as enumerable
  (3999 cases) and checked exhaustively, catching `n===1847`.
  **L5 arbitrary-point: battery 0/3 → fuzz 2/3 → coverage-aware 3/3. Total false
  accepts 3/15 → 1/15 → 0/15.**
  Trade-off surfaced: **false rejects rose 0/3 → 1/3.** The luhn reference
  disagrees with the hand-verified correct impl on `""` — an input the spec never
  addresses, where both made different reasonable choices. (Caveat: luhn's L5 was
  therefore flagged at `""`, not at the injected `"77"` fault; the earlier fuzz
  run independently confirmed that fault *is* caught.) Broader coverage removes
  fatal false accepts but exposes spec-ambiguity false rejects → D28, Q21.
- **2026-07-25 18:41 JDT** — **Differential fuzzing built and measured**
  (`gate/fuzz_gate.py`) — answers Q19. Strong tier emits `referenceImpl` +
  `randomInput`; candidate is compared against the reference over 20,000 random
  inputs in-page. Versus the fixed battery on the identical ladder:
  **L5 arbitrary-point 2/3 caught (was 0/3); total false accepts 1/15 (was
  3/15); false rejects 0/3.** It caught the `"77"` substring and `length===9`
  faults. The single miss (`n===1847`) is a generator-distribution artifact —
  uniform sampling over 1..3999 should hit it ~5× in 20k — hence D27: enumerate
  exhaustively for small finite domains. Reference-generation cost $0.06.
  Note: no false rejects means the auto-generated references were correct.
- **2026-07-25 18:35 JDT** — **Bug-subtlety ladder / kill-check done properly**
  (`gate/subtlety_ladder.py`) — answers Q14 and the substance of Q2/Q3.
  3 tasks × 6 hand-verified implementations, gated by Opus-generated oracles.
  Catch rate: **L1 obvious 3/3, L2 systematic 3/3, L3 class-conditional 3/3,
  L4 canonical-edge (empty/singleton/max) 3/3, L5 arbitrary-point 0/3.**
  **False accepts 3/15, all at L5; false rejects 0/3.** The boundary is exactly
  canonical-vs-arbitrary: auto-oracles reliably probe boundaries, empty,
  singleton and max — where real bugs cluster — but a finite battery is blind to
  a fault placed at an arbitrary input (`n===1847`, substring `"77"`,
  `length===9`). Note the first pass (L1–L4 only) scored 0/12 false accepts and
  was misleading: those L4 bugs sat on canonical edges the oracle probes by
  habit. → D25 (differential/fuzz testing), D26 (not a security boundary).
- **2026-07-25 18:24 JDT** — **Q17 unanimity blind-spot test**
  (`gate/stress_unanimous.py`). Hardest test yet: maximum-prior-pull specs
  (swapped FizzBuzz; `sortDesc` that sorts *ascending*; zero treated as odd;
  `e` not a vowel; reverse-all-but-first), each deviation stated **plainly once**
  (no capitals/emphasis, unlike Q16) to maximise reversion. 32 inputs.
  Result: **0 unanimous-wrong again**; 34 wrong values, **all 34 flagged** by
  disagreement; a strong tier was correct on **32/32** inputs.
  Tier split is now stark: Haiku 53–75%, Sonnet 100%, Opus 100%.
  Cumulative across Q16+Q17: **83 inputs, 55 oracle errors, 0 unanimous-wrong,
  100% flagged.** Also observed: haiku#3 missed all 5 FizzBuzz cases while
  haiku#1/#2 passed (sampling variance gives some in-tier signal), yet all 3
  Haikus failed `sortDesc` together (correlated) — both effects are real. → D23, D24.
- **2026-07-25 18:18 JDT** — **Q16 adversarial consensus stress test**
  (`gate/stress_consensus.py`). 5 specs deliberately contradicting famous
  conventions (additive Roman `IIII`; Luhn doubling from the LEFT; MODIFIED
  competition ranking 1,3,3,4; leap years with no 100/400 exception; banker's
  rounding), 51 pinned inputs, same 5 oracles. Three findings:
  (1) **0 unanimous-wrong** — all 21 wrong values landed on inputs where oracles
  disagreed, so disagreement-flagging caught 100% (now on n=21 errors, far
  stronger than the earlier n=1);
  (2) **majority vote FAILED** — all three Haiku voters reverted to the canonical
  convention *together*, so the 5-oracle majority scored 45/51 while Opus alone
  scored 51/51. Correlated failure among same-model samples is real;
  (3) accuracy split cleanly by tier: Haiku 84–88%, Sonnet 100%, Opus 100% — the
  failures were exactly the "override the prior" cases (1994/3999 additive Roman,
  every ranking tie, 16-digit Luhn-left). Leap-year and banker's rounding: no
  errors from anyone. → D20, D21, D22.
- **2026-07-25 18:09 JDT** — **Q15 (detecting bad oracles without ground truth)
  — first cut** (`gate/oracle_consensus.py`). 5 independent oracles (3× Haiku,
  1× Sonnet, 1× Opus) computed expected values for 30 pinned inputs across the
  3 tasks; Python held real ground truth. Results: **only 1 wrong value out of
  150** — and it was **Opus** (called the valid Luhn number `4532015112830366`
  invalid; hand-verified sum 50). Every Haiku run was 30/30. Detection: the one
  error coincided with cross-oracle disagreement (1/1 flagged); **0
  unanimous-wrong** cases. Economics: 3× Haiku majority 30/30 @ $0.023 beat
  1× Opus 29/30 @ $0.045. Two conclusions: disagreement-flagging looks viable as
  a no-ground-truth defense, and **decomposing the oracle (pinned inputs →
  compute values) makes cheap models sufficient** — revising D18 into D19.
  CAVEAT: only 1 error occurred, so the 100% detection figure is near-meaningless
  statistically; and canonical tasks understate correlated-error risk.
- **2026-07-25 18:03 JDT** — **Auto-generated gates tested** (`gate/auto_gate.py`).
  Can the system produce its own oracle for an unanticipated request? 3 novel
  tasks (Luhn validation, tie-aware competition ranking, Roman numerals) ×
  2 oracle-generator models, each auto-gate run against hand-verified CORRECT and
  subtly-BUGGY implementations. Results: **false accepts 0/6** (every injected bug
  caught — missing Luhn −9, dense-vs-competition ranking, non-subtractive Roman);
  **wrong oracles 2/6, all from Haiku** (Opus 0/3): Haiku claimed
  `luhnValid("10")===true` and mis-ranked `[100,90,80,90,100,80]` — both verified
  wrong by hand. Cost $0.07. **First measured case where the strong model beats
  the cheap one → oracle generation is where you pay (D18).** Caveats: n=6,
  semi-canonical tasks, clear-cut injected bugs. Also fixed a harness artifact
  (minimal test scaffold failed the floor's `has_dom>=5`, initially mimicking
  "wrong oracles" 6/6).
- **2026-07-25 17:53 JDT** — Thin cascade wired ON TOP of the gate
  (`gate/run_cascade_calc.py`, `gate/scaffold/tool_calc_scaffold.html`,
  `gate/calc_spec.py`) on a harder slot (integer expr eval, div truncates toward
  zero). Over 6 trials: always-Haiku 6/6 $0.0211, always-Opus 6/6 $0.1106,
  **CASCADE 6/6 $0.0211 — 81% cheaper than always-Opus at equal gate-verified
  quality.** Escalation fired 0/6 (Haiku aced it — prompt over-specified the
  trap). Finding: the cascade's proven value is **"cheap-first behind the gate"**;
  the multi-tier escalation is rarely-fired insurance. The gate is what makes
  defaulting to cheap SAFE — that's the savings. (Original "boss routing between
  models" ≈ "one cheap model + a great verifier".)
- **2026-07-25 17:44 JDT** — Recipe extends to a NON-GAME tool (Q13a answered:
  yes). Bill splitter with tip + exact-cent rounding: `splitBill(subtotalCents,
  tipPercent, people)`. `gate/scaffold/tool_billsplit_scaffold.html`,
  `gate/billsplit_spec.py`, `gate/constrained_gen_billsplit.py`. Contract 5/5,
  logic 5/5, buggy control (drops remainder cents) correctly FAILED. Three
  verticals now (Wordle, 2048, bill-splitter) — the recipe is not games-specific;
  it fits any app whose critical logic is a checkable pure function.
- **2026-07-25 17:29 JDT** — Approach GENERALIZES to a 2nd vertical (2048).
  `gate/scaffold/game2048_scaffold.html`, `gate/game2048_spec.py`,
  `gate/constrained_gen2048.py` — different logic (array transform + merge-once,
  not string matching). Same pattern, no gate changes: contract **5/5**, logic
  **5/5**, buggy control (merge-until-stable) **correctly FAILED**. The
  scaffold+slot+oracle+gate recipe is repeatable, not Wordle-specific.
- **2026-07-25** — Constrained generation VALIDATED (`gate/constrained_gen.py`,
  `gate/scaffold/wordle_scaffold.html`). Model fills only `computeFeedback`;
  injected into a scaffold we own. Results: contract conformance **5/5** (vs 3/6
  free-form), logic correct **5/5**, and a known-buggy control **correctly
  FAILED** — so the gate still catches wrong logic. Also closes the earlier
  coverage-gap false-accept (scaffold guarantees a working, playable UI). This is
  a validated core loop for the Wordle vertical: gen logic → inject → gate.
- **2026-07-25** — Conformance repair attempt (`gate/repair_conformance.py`) —
  FAILED to lift conformance (3/6 → 3/6), $0.15 wasted. Root causes diagnosed:
  (a) cheap model ignored the "add hook" instruction in 2/3 repairs (no
  `__wordle` at all); (b) the 3rd regenerated the FULL HTML and **truncated** at
  the 8192-token cap → hook code present in source but script broken → runtime
  `window.__wordle` undefined. **The gate correctly rejected the runtime-broken
  build (gate is trustworthy — verified via `gate/probe_hook.py`).** Lesson:
  full-file regeneration is the wrong repair mechanism (truncation + cost); and
  voluntary contract conformance is unreliable at the cheap tier. (Also fixed a
  `str.format` brace bug in the repair prompt.)
- **2026-07-25** — Phase 2 kill check, first cut (`gate/kill_check.py`, N=6 real
  Haiku builds with the contract). Findings: **contract conformance 3/6** (half
  ignored the `window.__wordle` hook despite the prompt → false-reject driver,
  conflating "bad game" with "didn't follow protocol"); **coloring 3/3 correct
  among conformant** (cheap tier reliable when it conforms); **coverage-gap false
  accept CONFIRMED** — the sneaky `wordle_hook_only.html` (correct hook, dead UI)
  PASSes because the gate checks hook+floor, not that the game actually plays.
  Gate is not yet at "false-accept≈0 / tolerable false-reject" — work needed in
  both directions (conformance/repair + acceptance-criteria coverage + UI driving).
- **2026-07-25** — Gate Layer 1 (functional) built and PROVEN to see correctness:
  `gate/wordle_spec.py` drives the `window.__wordle` contract over a
  duplicate-letter battery vs a Python oracle. On controlled fixtures, correct
  Wordle PASSes and a logically-broken one FAILs on `wordle_logic` — even though
  BOTH pass the runtime floor. First demonstrated catch of a floor-level
  false-accept. Files: `gate/contract.md`, `gate/wordle_spec.py`,
  `gate/fixtures/wordle_{correct,broken}.html`, `gate/run_wordle_gate.py`.
- **2026-07-25** — Gate Layer 0 (runtime floor) skeleton built and running:
  `gate/browser_gate.py` (Playwright headless Chromium). Checks loads / no page
  errors / no console errors / has DOM / non-blank / interactive. Both real
  Wordle builds (`eval/artifacts/`) PASS the floor. Note: floor cannot see
  correctness (a pretty-but-broken game would also pass) — functional layer next.
- **2026-07-25** — Wrote gate-first implementation plan (`docs/implementation-plan.md`).
- **2026-07-25** — Ran full empirical investigation (~$2.70 total). Built eval
  harness and 8 experiment scripts under `eval/`. Key results captured in
  Findings below.
- **2026-07-25** — Critiqued original plan; wrote `docs/plan-revised.md`.
- **2026-07-25** — Established project direction through Q&A: cascade for "build
  me X", gate as backbone.

---

## Plans set

- **Implementation plan:** `docs/implementation-plan.md` (gate-first, Phases 0–7,
  with a Phase-2 kill criterion).
- **Revised strategy critique:** `docs/plan-revised.md`.
- **Original concept:** `docs/plan.md` (superseded).

---

## Open questions

| # | Question | When needed | Status |
|---|----------|-------------|--------|
| Q1 | Which exact first vertical (specific app type + example requests)? | Now (Phase 0) | ANSWERED (2026-07-25): single-file browser games. |
| Q2 | Can the gate reach false-accept ≈ 0 with tolerable false-reject on that vertical? | Phase 2 — **kill check** | LARGELY ANSWERED (2026-07-25 18:35 JDT): yes for the realistic bug distribution — false-accepts 0/12 on obvious→canonical-edge bugs, false-rejects 0/3. Residual false-accepts only for arbitrary-point faults (3/3) → D25/Q19. |
| Q3 | What false-reject rate / cost budget is acceptable (the tuning target)? | Before Phase 2 tuning | OPEN |
| Q4 | Build vs no-build apps for the first gate (recommend no-build/single-file first)? | Phase 1 | ANSWERED (2026-07-25): no-build/single-file first (D13). |
| Q5 | Cheap tier's real pass@k per vertical (decides if the cascade pays). | — | ANSWERED (2026-07-25 19:45 JDT): 10/10 on each of wordle, game2048, billsplit via constrained generation — pass@1 100%, Wilson 95% CI [72%, 100%]. Escalation is rarely-fired insurance for these verticals. |
| Q6 | Can an LLM judge reliably score the *subjective* residual for real builds? | Phase 4 (fundamentally limited) | OPEN |
| Q7 | Does the API key have access to Sonnet 5 and Fable 5 (Fable needs 30-day retention)? | Before Phase 6 | OPEN |
| Q18 | Human spot-check + flag-rate monitoring for the residual unanimous-wrong risk. | Before unsupervised production use | ANSWERED (2026-07-25 18:57 JDT): spec written — `docs/gate-operations.md` (D31). Residual risk itself remains irreducible; mitigated by one-time human review per new vertical. |
| Q17 | Does "unanimous ⇒ correct" hold when even the STRONG models revert? | Before auto-gates go live unsupervised | ANSWERED (2026-07-25 18:24 JDT): unanimity did NOT break — 0 unanimous-wrong across 32 hardest-yet inputs (83 cumulative), all 34 errors flagged, strong tier 100%. Safety rests on the strong tier being reliable (D23) → residual risk moved to Q18. |
| Q16 | Correlated (unanimous-wrong) oracle failure — the residual fatal risk. | Before auto-gates go live | LARGELY ANSWERED (2026-07-25 18:18 JDT): adversarial specs produced 21 errors, **0 unanimous-wrong**; disagreement flagged 100%. BUT correlated failure IS real *within* a tier (3× Haiku wrong together) → don't vote, escalate (D21); diversify tiers (D22). Residual risk → Q17. |
| Q15 | A wrong oracle is INVISIBLE in production (looks identical to bad code). Detect it without a hand-verified reference? | Before auto-generated gates go live | PARTIAL (2026-07-25 18:09 JDT): cross-oracle disagreement flagged the only error (1/1), 0 unanimous-wrong, and a 3× cheap ensemble beat 1× Opus on both accuracy and cost. But only 1 error occurred → weak evidence; see Q16. |
| Q24 | Mutation score is measured on HAND-WRITTEN batteries. Auto-generated batteries (the ones that would serve unanticipated requests) are still unscored — run `mutation_check` against an auto-vertical's battery to close the loop. | Before auto-verticals run unattended | OPEN (raised 2026-07-25 19:56 JDT) |
| Q23 | Disputed cases were excluded, losing coverage. | — | ANSWERED (2026-07-25 19:56 JDT): `resolve_disputed()` re-votes per pinned case; recovered cases rejoin the battery, unresolved ones route to human review (D38). |
| Q22 | Auto-verticals need spec precision + a real buggy-control generator. | — | ANSWERED (2026-07-25 19:56 JDT): precision via narrow-domain sharpening + ensemble oracle (accept 1/3 → 3/3, D35); controls via execution-validated mutants — production batteries score 100% (15/15), D39. |
| Q21 | Spec-ambiguity false rejects: broad coverage hits inputs the spec never addresses (e.g. `""` for a card number), where the reference's arbitrary choice becomes "truth" and correct code fails. Handle by constraining the declared domain to spec-defined inputs, and/or routing ambiguous-edge disagreements to spec clarification instead of auto-failing. | Before productizing the gate | OPEN (raised 2026-07-25 18:53 JDT) |
| Q20 | Generator coverage bottleneck; should enumeration be automatic when the domain is enumerable? | — | ANSWERED (2026-07-25 18:53 JDT): yes — declare the domain, enumerate ≤100k exhaustively, fuzz otherwise. False accepts 0/15 (D28). Cost: more spec-ambiguity false rejects → Q21. |
| Q19 | Does differential fuzzing close the L5 gap? | — | ANSWERED (2026-07-25 18:41 JDT): largely — L5 2/3 (was 0/3), false accepts 1/15 (was 3/15), false rejects 0/3. Residual miss is a generator-distribution artifact → D27, Q20. |
| Q14 | Does the auto-gate hold on subtler bugs? | — | ANSWERED (2026-07-25 18:35 JDT): yes up to canonical-edge bugs (12/12 caught), no for arbitrary-point bugs (0/3 caught). False accepts 3/15, false rejects 0/3. → D25, D26. |
| Q13 | Generalization boundary beyond web games. (a) non-game logic-tools; (b) content/UI-heavy apps like IGN. Strategic implication: gate is strongest for logic-verifiable categories; lead there, defer content sites. | Before committing to "build me any site" scope | FULLY ANSWERED. (a) 2026-07-25 17:44 JDT: YES — bill-splitter tool works (5/5, buggy caught). (b) 2026-07-25 18:57 JDT: **floor-only** — objective defects caught 5/5, subjective passed 2/2 → the gate guarantees working/accessible/complete, not *good* (D30). |
| Q12 | How to GUARANTEE conformance, given voluntary contracts fail at the cheap tier? | — | ANSWERED (2026-07-25): option (a) constrained generation — validated (D16). |
| Q11 | Contract conformance ~50% with free-form gen; full-regen repair failed. | — | ANSWERED (2026-07-25): solved by constrained generation (D16), not repair. |
| Q10 | Hook-vs-UI divergence + coverage gap (sneaky dead-game passed). | Gate coverage | MOSTLY CLOSED (2026-07-25): constrained scaffold owns the working UI, so a dead-game-with-correct-hook can't occur for scaffolded builds. Revisit if generation freedom expands beyond the scaffold. |
| Q9 | Impose a generation *contract* (fixed testable interface / DOM `data-testid`s) so functional gating generalizes across implementations? | Gate Layer 1 (functional) | ANSWERED (2026-07-25): yes — `window.__wordle` contract (D15). |
| Q8 | Was the VSM cascade failure variance or gate design? | — | ANSWERED (2026-07-25): variance. pass@k = Haiku 50%, Opus 67%. |

---

## Empirical findings (dry runs, 2026-07-25, ~$2.70 total)

- **Self-contained coding (23 tasks, easy→contest→a self-modifying VM):** cheap
  model (Haiku) passed effectively all; escalation never fired; Opus added cost,
  not quality. Well-specified coding does not need a cascade.
- **Mental algorithm execution (UPMH-64):** both models hallucinated; escalation
  doubled cost for the same wrong answer; the real lever is **tool use / code
  execution** (a Python oracle solved it instantly).
- **Open-ended engineering ("overhaul"):** no deterministic oracle; both failed a
  completeness floor (Haiku truncated, Opus shipped 2 syntax-broken blocks at
  4.5× cost). This is the **scoring wall** — correctness needs a judge.
- **Judge reliability:** judges were position-invariant; on a controlled
  correct-vs-buggy pair, Opus judge 6/6, Haiku judge 5/6 (never chose buggy). A
  judge *can* be a correctness gate — but consistency ≠ correctness, and a judge
  is only validatable where ground truth exists.
- **Cascade + reliability:** tasks are probabilistic. On the VSM task, pass@k =
  Haiku 50% / Opus 67%. In that partial-pass band, cascade Haiku→Opus ≈ **84%
  success at ~$0.053/task vs always-Opus 67% at $0.077** — wins on cost AND
  quality *because a reliable gate turns cheap failures into a free retry*.
  Over-escalation on hopeless tasks can cost MORE than always-strong (measured
  $0.36 vs $0.27) → need an escalation cap.

---

## Artifact / file index

*(layout as of the 2026-07-25 18:45 JDT cleanup)*

**`docs/`**
- `plan.md` — original concept (superseded).
- `plan-revised.md` — critique-driven strategy revision.
- `implementation-plan.md` — gate-first phased plan.
- `PROJECT-LOG.md` — this file.

**`gate/`** — the product. Core: `browser_gate.py` (runtime floor + functional
hook runner), `contract.md`, `scaffold/` (4 scaffolds we own), `fixtures/`
(correct / broken / hook-only Wordles), and one `*_spec.py` per vertical
(`wordle_spec`, `game2048_spec`, `billsplit_spec`, `calc_spec`).
Generation + cascade: `constrained_gen.py`, `constrained_gen2048.py`,
`constrained_gen_billsplit.py`, `run_wordle_gate.py`, `run_cascade_calc.py`.
Verification methodology (validated, feeds the production gate):
`auto_gate.py`, `oracle_consensus.py`, `stress_consensus.py`,
`stress_unanimous.py`, `subtlety_ladder.py`, `fuzz_gate.py`, `probe_hook.py`.

**`archive/`** — concluded evidence trail; see `archive/README.md`.
`archive/eval/` (the exploration phase) and `archive/gate-deadends/`
(`kill_check.py`, `repair_conformance.py`).

**`.env`** — `CLAUDE_API_KEY`. Keep out of any repo.

> Cleanup 2026-07-25 18:45 JDT: deleted 42 `__pycache__` artifacts and 29
> generated HTML outputs (`gate/corpus/`, `eval/artifacts/` — regenerable);
> archived the exploration phase and two dead-end approaches. No project is under
> git, so nothing else was deleted.
