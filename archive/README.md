# Archive

Concluded work, kept as the evidence trail behind the claims in
`docs/PROJECT-LOG.md`. Nothing here is on the active path; nothing here needs to
run again. (Scripts moved out of their original directories may no longer resolve
their imports — that's fine, they are records, not tools.)

## `eval/` — the exploration phase (2026-07-25)

The experiments that answered the original question: *"is there merit to a strong
model delegating to cheaper ones?"* Established that cheap models handle
well-specified coding tasks (~30 tasks, 0 failures), that escalation rarely fires,
and that the value sits in the **verifier**, not the router.

| File | What it showed |
|---|---|
| `run_eval.py`, `tasks*.py` | cheap vs expensive vs escalation over 23 coding tasks — cheap passed everything |
| `upmh.py`, `run_answer.py` | mental algorithm execution: both tiers hallucinated; the real lever is tool use |
| `run_bigcode.py` | open-ended engineering: no oracle exists → the scoring wall |
| `run_judge.py`, `run_judge2.py` | LLM judges are position-invariant and can catch a real bug |
| `run_cascade.py`, `run_cascade_calc.py`* | cascade economics (*still active, in `gate/`) |
| `diagnose_vsm.py`, `reliability_vsm.py` | task outcomes are probabilistic — decide on pass@k, not single runs |

## `gate-deadends/` — approaches that failed

| File | Why it's here |
|---|---|
| `kill_check.py` | Phase-2 kill check on free-form generation. Found contract conformance of only 3/6 and a coverage-gap false accept. Superseded by constrained generation (D16). |
| `repair_conformance.py` | Tried to fix missing hooks by regenerating the whole file. Failed (3/6 → 3/6): the model ignored the instruction, and full-file regen truncated. Superseded by constrained generation. |

## Deleted, not archived

Generated model output (`gate/corpus/*.html`, `eval/artifacts/*.html`) was
deleted — regenerable by re-running the relevant script for a few cents.
