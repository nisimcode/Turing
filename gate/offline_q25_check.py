"""Zero-credit preflight for Q25 dossier preparation controls."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.auto_vertical import REQUESTS, SLOT, schema_probe_inputs
from gate.core.mutation import (
    mutation_score,
    validated_mechanical_mutants,
)

SCAFFOLD = """<!doctype html><html><body><main><h1>Shipping</h1>
<input><button>Quote</button><output>Ready</output></main><script>
/*__LOGIC_SLOT__*/
window.__fn=(...args)=>shippingPrice(...args);
</script></body></html>"""

IMPL = """
function shippingPrice(weight) {
  if (weight <= 1000) return 500;
  if (weight <= 5000) return 900;
  return 1500;
}
"""

BATTERY = [
    {"args": [1], "expected": 500},
    {"args": [1000], "expected": 500},
    {"args": [1001], "expected": 900},
    {"args": [5000], "expected": 900},
    {"args": [5001], "expected": 1500},
    {"args": [10000], "expected": 1500},
]

SCHEMA = {
    "args": [{
        "type": "integer",
        "minimum": 1,
        "maximum": 10000,
    }],
}


def main() -> int:
    assert len(REQUESTS) >= 10
    probes = schema_probe_inputs(SCHEMA, BATTERY)
    assert probes
    battery_inputs = {tuple(case["args"]) for case in BATTERY}
    assert all(tuple(probe) not in battery_inputs for probe in probes)

    mutants = validated_mechanical_mutants(
        SCAFFOLD,
        SLOT,
        IMPL,
        probes,
        want=5,
    )
    assert len(mutants) == 5
    scored = mutation_score(
        BATTERY,
        SCAFFOLD,
        SLOT,
        mutants,
        lambda actual, expected: actual == expected,
    )
    assert scored["score"] == 1.0, scored

    print("OFFLINE Q25 PREFLIGHT: PASS")
    print("  fixed dossier workload: 10 distinct requests")
    print(f"  disjoint schema-derived probes: {len(probes)}")
    print("  generic local mutants: 5/5 execution-validated and killed")
    print("  API spend: $0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
