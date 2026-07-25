"""ARCHIVED PREDECESSOR: run the legacy standalone Wordle gate on the
controlled fixtures, to prove the gate catches a logically-broken game.

    uv run --with playwright --with pillow python run_wordle_gate.py [file ...]

With no args it gates the correct/broken fixtures; pass paths to gate real builds
(they must implement the window.__wordle contract -- see contract.md).
"""

import sys
from pathlib import Path

from browser_gate import gate_html, print_verdict
import wordle_spec

HERE = Path(__file__).resolve().parent


def main():
    args = sys.argv[1:]
    targets = [Path(a) for a in args] if args else [
        HERE / "fixtures" / "wordle_correct.html",
        HERE / "fixtures" / "wordle_broken.html",
    ]
    results = []
    for t in targets:
        v = gate_html(t, functional=wordle_spec.functional_checks)
        print_verdict(v)
        results.append(v)

    print("\n=== summary ===")
    for v in results:
        name = Path(v["path"]).name
        logic = next((c for c in v["checks"] if c["name"] == "wordle_logic"), None)
        logic_str = "" if logic is None else f"  wordle_logic={'ok' if logic['ok'] else 'FAIL'}"
        print(f"  {name:22} {'PASS' if v['passed'] else 'FAIL'}{logic_str}")
    if not args:
        c = results[0]["passed"] and any(
            x["name"] == "wordle_logic" and x["ok"] for x in results[0]["checks"])
        b = (not results[1]["passed"]) and any(
            x["name"] == "wordle_logic" and not x["ok"] for x in results[1]["checks"])
        print("\n  => Gate sees correctness: "
              + ("CONFIRMED (correct PASSes, broken FAILs on logic)."
                 if c and b else "NOT confirmed -- investigate."))


if __name__ == "__main__":
    main()
