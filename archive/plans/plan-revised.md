> Archived 2026-07-25: strategy critique completed; retained as decision evidence.

### Executive Summary

This revises the original escalation-system plan by reordering it around the decisions that actually carry risk. The prior version was strongest where the work was easy (retiring the "AI Boardroom") and vaguest where the work is hard (choosing a vertical, building the escalation gate, and defining a trustworthy scoring method). This version front-loads those three.

**Core thesis (unchanged, because it's correct):** The value is not multi-agent deliberation — it's *smart routing with escalation*: cheap models handle the common case, and a validated gate escalates edge cases to a frontier model. Everything else is in service of proving that this saves money without losing quality.

---

### What Carries the Risk (read this first)

Three decisions determine whether this project succeeds. They must be made *before* the 240-run experiment, not after.

1. **The vertical.** Every schema, task, and scoring rubric depends on it. Undecided = nothing downstream is real.
2. **The escalation gate.** The "Validation Passed?" step is the entire system. If it's a model call, it reintroduces cost and latency; if it's a heuristic, its accuracy caps the whole system's quality. This is the research problem, not a decision node in a diagram.
3. **The scoring method.** If judging is done by an LLM, verbosity bias and self-preference will distort the exact metrics we care about (correctness, verbosity). If done by humans, 240 outputs is a real labor cost. This must be settled before we generate data we can't trust.

---

### Phase 0 — Choose the Vertical (do this first)

Pick one narrow domain where **task success is deterministically checkable**. Determinism is the selection criterion — it is what lets us score without a flaky judge.

Candidates, ranked by how cleanly success can be verified:

| Vertical | Success signal | Why it's good/bad |
|---|---|---|
| **Structured schema parsing** (NL → typed JSON) | Exact/semantic match against gold schema; validates against Pydantic | Cleanest to grade; escalation triggers on validation failure — the gate is nearly free |
| **Code refactoring** | Test suite passes + behavior unchanged | Objective *if* tests exist; gate = "did tests pass?" |
| **Legal redlining** | Requires expert judgment | High value, but scoring is subjective — worst fit for a first experiment |

**Recommendation:** Start with **structured schema parsing** or **code refactoring**. In both, the escalation gate falls out of the domain almost for free (schema validation / test pass), which lets us prototype the hardest component (the gate) cheaply. Defer legal/subjective verticals until the method is proven.

**Exit criterion:** one vertical named, plus 5 concrete example tasks written by hand.

---

### Phase 1 — Prototype the Escalation Gate

Before any large experiment, build and stress the gate in isolation. This is the centerpiece.

The gate answers: *given a cheap model's output, do we accept it or escalate to frontier?* Three implementations to compare, cheapest first:

1. **Deterministic validator** (preferred where the vertical allows): schema validation, test execution, type checks. Near-zero marginal cost and latency.
2. **Cheap-model self-assessment:** the worker rates its own confidence; escalate below threshold. Fast but poorly calibrated — measure the calibration, don't assume it.
3. **Separate small judge model:** a dedicated critic call. Most expensive; only justified if 1 and 2 leak too many bad outputs.

**What to measure on the gate itself:** false-accept rate (bad output passed) and false-escalate rate (good output needlessly sent to frontier). These two numbers define the system's cost/quality frontier. Tune the threshold against them.

**Exit criterion:** a gate with characterized false-accept / false-escalate rates on the Phase 0 tasks.

---

### Phase 2 — Decide the Scoring Method

Settle *how outputs are judged* before generating them.

- **Prefer deterministic scoring** wherever the vertical allows (that's why Phase 0 selects for determinism): exact match, semantic match, test pass/fail.
- **Where human judgment is unavoidable,** score blind, randomize output order, and reveal config identity only after scoring. **Prefer pairwise comparison** (which of these two outputs is better?) over absolute 1–5 scoring — it gives cleaner signal and is far less sensitive to rubric drift than absolute scores.
- **If using LLM-as-judge at all,** treat it as an instrument that must be calibrated: spot-check a sample against human labels, and correct for known verbosity bias and self-preference. Do not let the judge model be the same family as any model under test without noting the conflict.

**Exit criterion:** a written rubric and a scoring function/harness that a second person could apply and get the same numbers.

---

### Phase 3 — The Evaluation Harness

A ~150-line async Python script. Direct SDK calls (or LiteLLM for provider translation), Pydantic for schemas. **No LangGraph/AutoGen** — the point is control and legibility, not orchestration.

```
                    ┌─────────────────────────┐
                    │       Input Task        │
                    └────────────┬────────────┘
                                 │
                   ┌─────────────┴─────────────┐
                   ▼                           ▼
        [ Baseline Configs ]         [ Escalation Pipeline ]
        • Single Frontier Call       • Tier 1: Cheap Model
        • Deliberative Frontier                  │
        • Full Board (control)          [ GATE from Phase 1 ]
                                         ├─ ACCEPT ──> Output
                                         └─ ESCALATE ─> Tier 2: Frontier
```

No product infra yet. **FastAPI + Postgres are explicitly out of scope until the experiment proves the escalation engine wins.** Log to JSONL files; that is sufficient for 240 runs.

---

### Phase 4 — The Experiment

Four configurations:

1. **Single Frontier Call** — the honest baseline to beat.
2. **Frontier with Explicit Planning & Revision** — one model told to plan, critique, and revise its own answer. (Named this way rather than "chain-of-thought" because internal reasoning may not be exposed or comparable across providers.)
3. **Full Board Architecture** — multi-agent loop. *Included as a control we expect to lose*; the experiment falsifies (or resurrects) the original concept rather than assuming its death.
4. **Escalation Engine** — cheap worker + Phase 1 gate + frontier fallback.

**Sizing:** Runs are nearly free, so don't under-power the task set. Target **50–100 tasks × 3 runs per config**. Be explicit that 3 runs measures *variance*, not statistical proof — this is a directional experiment, and it should be labeled as one.

**Metrics** (scored via Phase 2 method):
- Task success / correctness
- Factual reliability
- Verbosity / unnecessary complexity
- Latency (p50 and p95, not just mean)
- Total cost (including gate and escalation overhead — count every token)
- **Quality-adjusted cost: cost per *accepted, successful* task.** This is the headline number. Raw average cost and raw average correctness, reported separately, can hide a router that looks cheap only because its gate is silently approving more failures (i.e. a high false-accept rate). Cost-per-success ties the two together and exposes that failure mode directly.

**The decision rule, stated in advance:** the escalation engine wins if it reaches ≥ X% of single-frontier correctness at ≤ Y% of the cost. Pick X and Y *before* seeing results.

---

### Phase 5 — The Moat (only if Phase 4 wins)

"Task-specific outcome data" is a moat only if there's a feedback mechanism. Name it explicitly:

- **Routing thresholds** re-tuned from observed false-accept / false-escalate rates (the cheapest, most immediate loop).
- **Escalation-trigger patterns** mined to improve the gate.
- **Fine-tuning the cheap worker** on escalated cases, so fewer tasks need frontier over time — this is the actual compounding asset.

Without one of these wired in, outcome data is still just nicer-looking logs. Decide which loop to build first.

---

### Final Stack (deferred until validated)

Plain async Python + Pydantic + LiteLLM, promoted to FastAPI + Postgres **only after** Phase 4 shows the escalation engine beats the single-frontier baseline on the pre-committed cost/quality rule. Product infrastructure is a reward for a positive result, not a prerequisite.

---

### What Changed From v1

- **Vertical selection moved to Phase 0** — it was a closing bullet; it's now the first gate.
- **Escalation gate promoted to its own phase** with measurable success criteria (false-accept / false-escalate), instead of a "Validation Passed?" box.
- **Scoring method made an explicit phase** with LLM-judge bias called out, rather than an unspecified "score blind."
- **Experiment scaled up** (50–100 tasks) with a *pre-committed* decision rule and p50/p95 latency.
- **Board architecture reframed** as a control we expect to falsify, not a strawman.
- **Moat given a concrete feedback mechanism.**
- **FastAPI/Postgres explicitly deferred** so infra doesn't leak backward into the experiment.
