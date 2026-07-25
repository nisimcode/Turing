# Implementation Plan — Gate-First

## Thesis

The product is a cost-saving model cascade for commercial "build me X" web-app
generation. The **backbone is the gate** — the component that decides whether a
generated app is good enough. Everything else (routing, tiers, the cost dial) is
worthless without it. Therefore we build and *validate the gate first*, before a
single line of cascade logic.

**Do-or-die:** if a trustworthy gate can't be built for a narrow slice, the whole
thesis fails. We design the early phases to prove or kill that as fast and cheap
as possible.

## Non-negotiable principles (earned from the dry runs)

1. **False-accepts are fatal; false-rejects only cost money.** The gate must be
   tuned so it essentially never ships broken output. Over-escalation is
   survivable; shipping garbage is not.
2. **Correctness is a floor, never a dial.** The objective gate is always on.
   Only *polish/effort/budget* above "it works" is user-tunable.
3. **Maximize the objective surface.** Improving the gate (more executable checks)
   lowers *both* error types; tuning a threshold only trades them. Objective
   checks first; LLM judge only for the residual it can't cover, as a soft signal.
4. **Decide on pass@k, not single runs.** Model output is probabilistic (we
   measured a task swing 50–67% run-to-run). Every reliability number is a rate.
5. **Start narrow.** One well-scoped app type before "any website."
6. **The cascade only pays when the cheap tier's pass rate is high AND the gate is
   reliable.** Prove both before building tiers.

## Kill criterion (check at Phase 2)

If, on the chosen narrow vertical, we cannot get the gate to **false-accept ≈ 0
with a tolerable false-reject rate**, stop. No cascade, no product. This is the
cheapest possible place to learn the thesis doesn't hold.

---

## Phase 0 — Pick the vertical & assemble examples  *(days)*

Pick ONE narrow, functionally-testable target where the objective surface is
large. Recommended start: **small self-contained web apps/games** (Wordle-like,
simple tools) — single-file or no-build, drivable in a browser. Defer large
framework sites (IGN-scale) until the gate works.

- **Work:** choose the target; hand-write 15–20 realistic requests; for each,
  sketch what "good enough" means (feature list).
- **Exit:** a target definition + 15–20 example requests with rough acceptance
  notes.

## Phase 1 — Build the objective gate  *(the core; weeks)*

A harness that takes a generated app and emits `pass/fail` + which checks failed.

- **Sandbox execution:** run/serve the generated app in an isolated container
  (Docker). Never trust generated code on the host.
- **Static checks:** syntax/parse valid; (if a build step) it builds without error.
- **Runtime checks (headless browser — Playwright):** page loads; **no console
  errors / uncaught exceptions**; DOM is non-empty; screenshot is not blank.
- **Functional checks:** drive the app via browser automation against the app
  type's acceptance criteria (e.g. Wordle: type a guess, assert the coloring —
  including the duplicate-letter case; win/lose states).
- **Output:** structured verdict — per-check results, not just a boolean — so
  failures can feed a fix loop later.
- **Exit:** given any build for the vertical, the gate returns a fast, structured
  pass/fail. Seed from the existing `eval/` harness (test-execution + subprocess
  isolation already there).

## Phase 2 — Validate the gate  *(the do-or-die test; weeks)*

Prove the gate is trustworthy before trusting it.

- **Corpus:** assemble known-GOOD and known-BAD builds. Sources: real cheap-model
  outputs (some are naturally bad), plus fault injection into good ones (break
  logic, blank the page, add a runtime error, drop a feature). Human-label once.
- **Measure:** **false-accept rate** (primary) and **false-reject rate** on the
  corpus. Tune toward false-accept ≈ 0.
- **Exit / KILL CHECK:** false-accept below the agreed threshold with a tolerable
  false-reject rate. If unreachable → stop the project here.

## Phase 3 — Acceptance-criteria generation  *(weeks)*

Turn an open-ended request into checks the Phase-1 gate can run.

- **Work:** an LLM step that decomposes a request → structured criteria, split
  into *objective* (browser/DOM/functional-automatable) and *subjective residual*
  (polish/aesthetics). Validate criteria quality on the Phase-0 examples (not
  over- or under-specified).
- **Exit:** request → executable criteria, validated against examples.

## Phase 4 — LLM judge for the subjective residual  *(secondary; weeks)*

Only for what objective checks can't cover.

- **Rules:** validate where ground truth exists (pairwise, both orderings — the
  method from `eval/run_judge2.py`); keep it a *soft* signal; it may **withhold**
  (trigger escalation) but may **never approve past an objective failure**.
- **Exit:** judge adds signal without adding false-accepts.

## Phase 5 — Single-model build loop  *(weeks)*

Wire ONE fixed model + the gate into generate → gate → fix → retry (capped
iterations). No cascade yet. This is already a shippable product.

- **Exit:** end-to-end request → app that passes the gate, at a measured success
  rate and cost, on the example workload.

## Phase 6 — The cascade  *(finally)*

Add tiers (Haiku → Sonnet → Opus [→ Fable]) with:

- **pass@k-based routing**, not single-attempt decisions.
- **Escalation cap / fail-fast** (don't climb the whole ladder on hopeless tasks;
  over-escalation can cost *more* than always-strong — we measured $0.36 vs $0.27).
- Consider **retry-cheap-before-escalate** (best-of-n on a tier can beat jumping
  tiers).
- **Exit:** cascade beats always-strong on cost at equal gate-pass quality.

## Phase 7 — Productize the dial & guardrails

- **Correctness floor:** always on, never sold down.
- **User dial above the floor:** frame as *effort/polish/budget* ("Draft / fast"
  vs "Production / polished", or a spend cap) — **not** a reliability knob. Every
  setting still ships working output.
- **Top-tier guard:** when the strongest tier fails the gate, reject → human
  handoff. Never silently accept because "it's the best we've got."

---

## Metrics to track throughout

- **False-accept rate** — the number that decides survival (target ≈ 0).
- **False-reject rate** — margin cost.
- **Per-tier pass@k** by app type — routing inputs.
- **Cost per *accepted, working* task** — the headline economic metric (a "cheap"
  system that ships failures is not cheap).
- Cascade cost vs always-strong at equal quality.

## Tech stack

- Orchestration: plain async Python (no heavy agent framework).
- Model access: Anthropic SDK (or LiteLLM for multi-provider) — key already wired.
- Sandbox: Docker container per build.
- Verification: Playwright (headless browser) for runtime + functional checks.
- Storage: the labeled corpus + per-run outcomes (this is the real data asset —
  gate errors, escalation triggers, acceptance rates — not raw logs).

## Sequencing

Phases 1–2 are the critical path and the kill gate — do them before anything
else. Phase 3 can start in parallel once the gate's check format is stable.
Phases 4–7 only begin after the Phase-2 kill check passes. Do **not** build the
cascade (Phase 6) before the gate is validated (Phase 2) and a single-model loop
works (Phase 5).
