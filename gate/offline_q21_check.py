"""Zero-API regression for Q21: undefined inputs must not reject correct code.

The generated draft deliberately includes `""` and `"0"`, although the declared
Luhn domain is 2-19 ASCII digits. Domain enforcement withholds both cases from
the executable battery and routes them to spec clarification instead.

    uv run --with playwright --with pillow python offline_q21_check.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core import verify
from gate.core.domain import filter_cases
from gate.core.policy import assess

SCAFFOLD = """<!doctype html><html><body>
<main><h1>Luhn check</h1><label>Number <input></label>
<button>Check</button><output>Ready</output><p>Validation demo</p></main>
<script>
function luhnValid(value) {
  let sum = 0, parity = value.length % 2;
  for (let i = 0; i < value.length; i++) {
    let digit = Number(value[i]);
    if (i % 2 === parity) {
      digit *= 2;
      if (digit > 9) digit -= 9;
    }
    sum += digit;
  }
  return sum % 10 === 0;
}
window.__fn = luhnValid;
</script></body></html>"""

DOMAIN_SCHEMA = {
    "args": [{
        "type": "string",
        "minLength": 2,
        "maxLength": 19,
        "pattern": "[0-9]+",
    }]
}

# The two out-of-domain expectations are intentionally arbitrary. Before Q21,
# either could become "truth" and falsely reject a correct implementation.
DRAFT = [
    {"args": [""], "expected": False},
    {"args": ["0"], "expected": False},
    {"args": ["10"], "expected": False},
    {"args": ["18"], "expected": True},
    {"args": ["4532015112830366"], "expected": True},
    {"args": ["4532015112830367"], "expected": False},
]


def functional(battery):
    def checks(page):
        mismatches = []
        for case in battery:
            actual = page.evaluate("(a) => window.__fn(...a)", case["args"])
            if actual != case["expected"]:
                mismatches.append((case["args"], actual, case["expected"]))
        return [{
            "name": "luhn_oracle",
            "ok": not mismatches,
            "detail": "all in-domain cases agree" if not mismatches
            else repr(mismatches[0]),
        }]
    return checks


def main() -> int:
    previous_queue = os.environ.get("GATE_REVIEW_QUEUE_PATH")
    try:
        with tempfile.TemporaryDirectory(prefix="gate-q21-offline-") as tmp:
            root = Path(tmp)
            os.environ["GATE_REVIEW_QUEUE_PATH"] = str(
                root / "review-queue.jsonl"
            )
            battery, clarifications = filter_cases(DRAFT, DOMAIN_SCHEMA)
            assert len(battery) == 4
            assert [case["args"] for case in clarifications] == [[""], ["0"]]

            review = assess(
                vertical="offline_q21",
                spec_clarifications=clarifications,
            )
            assert review.required and review.provisional and review.review_id
            assert "do not fail the implementation" in review.reasons[0]

            artifact = root / "luhn.html"
            artifact.write_text(SCAFFOLD, encoding="utf-8")
            verdict = verify(
                artifact,
                functional=functional(battery),
                vertical="offline_q21",
            )
    finally:
        if previous_queue is None:
            os.environ.pop("GATE_REVIEW_QUEUE_PATH", None)
        else:
            os.environ["GATE_REVIEW_QUEUE_PATH"] = previous_queue
    assert verdict.passed, verdict.summary()

    print("OFFLINE Q21 REGRESSION: PASS")
    print("  correct implementation: PASS")
    print("  in-domain oracle cases: 4")
    print("  out-of-domain cases withheld: 2")
    print("  disposition: spec clarification required, not code failure")
    print("  false rejects: 0")
    print("  API spend: $0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
