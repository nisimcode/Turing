"""Volume validation (Q5): the cheap tier's real pass@k per vertical.

Every reliability figure so far came from n=3-6. Routing decisions need RATES,
not single runs -- a task can pass or fail the same gate run to run (measured:
50% vs 67% on the VSM task). This generates N implementations per vertical
through the real pipeline and reports pass@1 with a confidence interval, plus
pass@k (the chance at least one of k attempts clears the gate), which is what a
retry-cheap-before-escalating policy actually depends on.

Runs through gate.core, so every verdict lands in telemetry and the ops alarms
have real data to fire on.

    uv run --with anthropic --with playwright --with pillow python volume_check.py [N]
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate.core import CHEAP, cost_report, verify                       # noqa: E402
from gate.core.llm import call, extract_code                           # noqa: E402
from gate.core.policy import assess, explain                           # noqa: E402
from gate.core.telemetry import alarms, stats                          # noqa: E402

import billsplit_spec, game2048_spec, wordle_spec                      # noqa: E402

HERE = Path(__file__).resolve().parent
SLOT = "/*__LOGIC_SLOT__*/"

VERTICALS = {
    "wordle": {
        "scaffold": HERE / "scaffold" / "wordle_scaffold.html",
        "checks": wordle_spec.functional_checks,
        "prompt": (
            "Implement exactly one JavaScript function "
            "`function computeFeedback(guess, answer)`. Both are uppercase "
            "5-letter strings. Return 5 characters: 'G' where the letter is "
            "right and in the right spot; 'Y' where the letter is in the answer "
            "but in the wrong spot, limited by how many copies remain after "
            "greens are accounted for (correct duplicate handling); 'B' "
            "otherwise. Return ONLY the function in one code block."),
    },
    "game2048": {
        "scaffold": HERE / "scaffold" / "game2048_scaffold.html",
        "checks": game2048_spec.functional_checks,
        "prompt": (
            "Implement exactly one JavaScript function `function slideRow(row)` "
            "for 2048. `row` is 4 integers (0 = empty). Slide non-zero values "
            "left, then merge adjacent equal values into one of double the "
            "value. Each tile may merge at most ONCE per call -- a tile formed "
            "by a merge must not merge again. Return a NEW array of length 4, "
            "left-aligned, zero-filled. Return ONLY the function in one code "
            "block."),
    },
    "billsplit": {
        "scaffold": HERE / "scaffold" / "tool_billsplit_scaffold.html",
        "checks": billsplit_spec.functional_checks,
        "prompt": (
            "Implement exactly one JavaScript function "
            "`function splitBill(subtotalCents, tipPercent, people)`. All are "
            "non-negative integers, people >= 1. 1) tip = "
            "Math.floor((subtotalCents * tipPercent + 50) / 100). 2) total = "
            "subtotalCents + tip. 3) split total into `people` integer-cent "
            "shares summing EXACTLY to total: base = Math.floor(total/people); "
            "the FIRST (total - base*people) shares are base+1, the rest base. "
            "Return an array of `people` integers. Return ONLY the function in "
            "one code block."),
    },
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval -- honest for small n, unlike the normal approx."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def run_vertical(name: str, cfg: dict, n: int) -> dict:
    scaffold = cfg["scaffold"].read_text(encoding="utf-8")
    tmp = Path(tempfile.mkdtemp(prefix=f"gate-vol-{name}-"))
    passes = 0
    for i in range(n):
        impl = extract_code(call(CHEAP, cfg["prompt"], max_tokens=1200),
                            "javascript")
        art = tmp / f"{name}_{i}.html"
        art.write_text(scaffold.replace(SLOT, impl), encoding="utf-8")
        v = verify(art, functional=cfg["checks"], vertical=name)
        passes += 1 if v.passed else 0
        print(f"    {i+1:>2}/{n}  {'PASS' if v.passed else 'FAIL'}"
              + ("" if v.passed else f"  ({', '.join(v.failed_checks())})"))
    lo, hi = wilson(passes, n)
    return {"passes": passes, "n": n, "rate": passes / n, "lo": lo, "hi": hi}


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print(f"Volume validation: {n} generations x {len(VERTICALS)} verticals "
          f"on {CHEAP}\n")

    out = {}
    for name, cfg in VERTICALS.items():
        print(f"  --- {name} ---")
        out[name] = run_vertical(name, cfg, n)
        print()

    print("=== pass@1 by vertical (Wilson 95% CI) ===")
    for name, r in out.items():
        print(f"  {name:12} {r['passes']:>2}/{r['n']}  = {r['rate']:.0%}   "
              f"95% CI [{r['lo']:.0%}, {r['hi']:.0%}]")

    print("\n=== pass@k: chance at least one of k cheap attempts clears ===")
    print(f"  {'vertical':12} {'k=1':>7} {'k=2':>7} {'k=3':>7}")
    for name, r in out.items():
        p = r["rate"]
        row = "  ".join(f"{1 - (1 - p) ** k:>6.0%}" for k in (1, 2, 3))
        print(f"  {name:12} {row}")

    print("\n=== telemetry ===")
    for name in VERTICALS:
        s = stats(name)
        print(f"  {name:12} verifications={s['verifications']:<4} "
              f"pass_rate={s['pass_rate']:.0%}" if s["pass_rate"] is not None
              else f"  {name:12} no data")
        for a in alarms(name):
            print(f"      ALARM: {a}")
        rev = assess(vertical=name, alarms=alarms(name))
        if rev:
            print("      " + explain(rev).replace("\n", "\n      "))

    print(f"\n  cost: {cost_report()}")
    print("\n=== read ===")
    lows = [k for k, r in out.items() if r["rate"] < 0.9]
    if not lows:
        print("  The cheap tier clears every vertical at a high rate, so a")
        print("  cascade here is effectively 'use the cheap model behind the")
        print("  gate' -- escalation is insurance that rarely fires.")
    else:
        print(f"  Cheap-tier reliability is partial on: {', '.join(lows)}.")
        print("  That is the band where escalation earns its keep -- compare")
        print("  retry-cheap (pass@2/@3 above) against escalating a tier.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
