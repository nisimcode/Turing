"""Zero-credit validation of the Q26 paired economics experiment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.q26_economics import evaluate_candidate, summarize, tasks


def _candidate(cost, gate_pass, audit_pass):
    return {
        "model": "fake",
        "cost": cost,
        "gate_pass": gate_pass,
        "audit_pass": audit_pass,
    }


def task_controls() -> None:
    selected = tasks()
    assert len(selected) == 7
    for task in selected:
        correct = evaluate_candidate(task, task.correct_js)
        assert correct["gate_pass"], (task.name, correct)
        assert correct["audit_pass"], (task.name, correct)

        bad = evaluate_candidate(task, task.bad_js)
        assert not bad["gate_pass"], (
            task.name,
            "known-bad control escaped the visible gate",
            bad,
        )

    # Deliberately overfit the visible additive-Roman cases. This must pass the
    # gate but fail the disjoint holdout, proving that the Q26 outcome is not
    # simply the same battery grading itself.
    roman = next(task for task in selected if task.name == "additive_roman")
    lookup = {
        str(args[0]): expected for args, expected in roman.gate_cases
    }
    overfit = f"""
function toRomanAdditive(n) {{
  const visible = {json.dumps(lookup)};
  if (Object.prototype.hasOwnProperty.call(visible, String(n)))
    return visible[String(n)];
  const table=[[1000,"M"],[900,"CM"],[500,"D"],[400,"CD"],[100,"C"],
    [90,"XC"],[50,"L"],[40,"XL"],[10,"X"],[9,"IX"],[5,"V"],[4,"IV"],[1,"I"]];
  let out=""; for(const [v,s] of table) while(n>=v){{out+=s;n-=v;}}
  return out;
}}"""
    leaked = evaluate_candidate(roman, overfit)
    assert leaked["gate_pass"], leaked
    assert not leaked["audit_pass"], leaked


def economics_controls() -> None:
    records = [
        {
            "task": "a", "trial": 0,
            "cheap": _candidate(0.01, True, True),
            "strong": _candidate(0.05, True, True),
        },
        {
            "task": "b", "trial": 0,
            "cheap": _candidate(0.01, False, False),
            "strong": _candidate(0.05, True, True),
        },
        {
            "task": "c", "trial": 0,
            "cheap": _candidate(0.01, False, True),
            "strong": _candidate(0.05, False, True),
        },
    ]
    report = summarize(records)
    assert report["pairs"] == 3
    assert report["escalations"] == 2
    assert report["gate_matrix"] == {
        "true_accept": 3,
        "false_accept": 0,
        "false_reject": 2,
        "true_reject": 1,
    }
    cascade = report["arms"]["gated_cascade"]
    assert cascade["correct_accepted"] == 2
    assert cascade["incorrect_accepted"] == 0
    assert cascade["rejected"] == 1
    assert abs(cascade["cost"] - 0.13) < 1e-12
    assert abs(report["cascade_savings_vs_always_strong"] - (2 / 15)) < 1e-12
    assert report["cascade_false_rejects"] == 1


def main() -> int:
    task_controls()
    economics_controls()
    print("OFFLINE Q26 PREFLIGHT: PASS")
    print("  fixed task adapters: 7/7 correct controls accepted")
    print("  known-bad controls: 7/7 rejected")
    print("  disjoint holdout: caught gate-overfit control")
    print("  three-arm cost/correctness replay: PASS")
    print("  API spend: $0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
