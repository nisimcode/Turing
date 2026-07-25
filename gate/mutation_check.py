"""Q22: how strong are our batteries, really? (mutation score)

"Does the gate catch bugs?" was answered until now with bugs *I* wrote, which
only proves it catches the faults I thought of. Mutation testing removes me from
the loop: the model proposes faults, each is kept only if EXECUTION shows it
changes behaviour, and we measure what fraction the battery kills.

Run on the production verticals, whose batteries are hand-written, so the score
is a real measure of the shipped gate.

    uv run --with anthropic --with playwright --with pillow python mutation_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gate.core.llm import cost_report                                  # noqa: E402
from gate.core.mutation import mutation_score, validated_mutants       # noqa: E402

import billsplit_spec, game2048_spec, wordle_spec                      # noqa: E402

HERE = Path(__file__).resolve().parent
SLOT = "/*__LOGIC_SLOT__*/"
WANT = 5


def eq(a, b) -> bool:
    is_nan = lambda v: isinstance(v, float) and v != v                 # noqa: E731
    if is_nan(a) and is_nan(b):
        return True
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(eq(x, y) for x, y in zip(a, b))
    return a == b


CORRECT = {
    "wordle": """
function computeFeedback(g, a){const r=Array(5).fill('B'),c={};
for(const ch of a) c[ch]=(c[ch]||0)+1;
for(let i=0;i<5;i++) if(g[i]===a[i]){r[i]='G';c[g[i]]--;}
for(let i=0;i<5;i++) if(r[i]==='B'&&c[g[i]]>0){r[i]='Y';c[g[i]]--;}
return r.join('');}
""",
    "game2048": """
function slideRow(row){const n=row.filter(x=>x!==0),o=[];let i=0;
while(i<n.length){ if(i+1<n.length&&n[i]===n[i+1]){o.push(n[i]*2);i+=2;}
else {o.push(n[i]);i++;} }
while(o.length<4) o.push(0); return o;}
""",
    "billsplit": """
function splitBill(s,t,p){const tip=Math.floor((s*t+50)/100),tot=s+tip,
b=Math.floor(tot/p),rem=tot-b*p,out=[];
for(let i=0;i<p;i++) out.push(b+(i<rem?1:0)); return out;}
""",
}

# Each vertical exposes its own hook, so the invoke expression differs.
INVOKE = {
    "wordle": "(a) => { window.__wordle.setAnswer(a[1]); "
              "return window.__wordle.guess(a[0]); }",
    "game2048": "(a) => window.__game2048.slide(a[0])",
    "billsplit": "(a) => window.__tool.split(a[0], a[1], a[2])",
}

VERTICALS = {
    "wordle": {
        "scaffold": HERE / "scaffold" / "wordle_scaffold.html",
        "battery": [{"args": list(t), "expected": wordle_spec.oracle(*t)}
                    for t in wordle_spec.BATTERY],
        "behaviour": "Wordle feedback: 'G' right letter right spot, 'Y' in the "
                     "word but wrong spot limited by remaining copies after "
                     "greens, 'B' otherwise.",
        "probe": [list(t) for t in wordle_spec.BATTERY] +
                 [["AAABB", "ABBBA"], ["XYZZY", "ZZYXY"], ["QQQQQ", "QQQQQ"]],
    },
    "game2048": {
        "scaffold": HERE / "scaffold" / "game2048_scaffold.html",
        "battery": [{"args": [r], "expected": game2048_spec.slide_left(r)}
                    for r in game2048_spec.BATTERY],
        "behaviour": "2048 single row: slide non-zero left, merge adjacent "
                     "equals once each (a merged tile cannot merge again), "
                     "return a length-4 array zero-filled on the right.",
        "probe": [[r] for r in game2048_spec.BATTERY] +
                 [[[2, 2, 4, 4]], [[0, 0, 0, 0]], [[4, 0, 0, 4]], [[2, 4, 4, 2]]],
    },
    "billsplit": {
        "scaffold": HERE / "scaffold" / "tool_billsplit_scaffold.html",
        "battery": [{"args": list(t), "expected": billsplit_spec.split_bill(*t)}
                    for t in billsplit_spec.BATTERY],
        "behaviour": "tip = floor((subtotal*pct+50)/100); total = subtotal+tip; "
                     "split into `people` integer-cent shares summing exactly "
                     "to total, the first (total - base*people) shares one cent "
                     "larger.",
        "probe": [list(t) for t in billsplit_spec.BATTERY] +
                 [[1, 15, 7], [99999, 33, 11], [0, 0, 1], [12345, 100, 3]],
    },
}


def main() -> int:
    print(f"Mutation testing the production batteries "
          f"(target {WANT} validated mutants each)\n")
    rows = []
    for name, cfg in VERTICALS.items():
        print(f"  --- {name} ---")
        scaffold = cfg["scaffold"].read_text(encoding="utf-8")
        muts = validated_mutants(scaffold, SLOT, CORRECT[name],
                                 cfg["behaviour"], cfg["probe"], want=WANT,
                                 invoke=INVOKE[name])
        if not muts:
            print("    no validated mutants -- cannot score\n")
            rows.append((name, None, 0, []))
            continue
        res = mutation_score(cfg["battery"], scaffold, SLOT, muts, eq,
                             invoke=INVOKE[name])
        rows.append((name, res["score"], res["mutants"], res["survivors"]))
        print(f"    battery {len(cfg['battery'])} cases | "
              f"mutants validated {res['mutants']} | killed {res['killed']}"
              f" -> score {res['score']:.0%}")
        for s in res["survivors"]:
            print(f"    SURVIVOR: differs on {json.dumps(s['diverges_on'])[:46]}"
                  f" ({s['original']} vs {s['mutant']}) but the battery misses it")
        print()

    print("=== mutation scores ===")
    for name, score, n, surv in rows:
        print(f"  {name:12} {'n/a' if score is None else f'{score:.0%}':>5}"
              f"   ({n} validated mutants, {len(surv)} survived)")
    scored = [s for _, s, _, _ in rows if s is not None]
    if scored:
        print(f"\n  overall: {sum(scored)/len(scored):.0%} of observable faults "
              f"killed")
    print(f"  cost: {cost_report()}")

    print("\n=== read ===")
    total_surv = sum(len(s) for _, _, _, s in rows)
    if scored and all(s == 1.0 for s in scored):
        print("  Every validated mutant was killed: the batteries test enough to")
        print("  catch faults nobody on this project thought of -- a stronger")
        print("  claim than 'it catches the bugs we injected'.")
    elif total_surv:
        print(f"  {total_surv} mutant(s) survived: those are real, observable")
        print("  faults the battery does not test for. Each survivor is a")
        print("  concrete missing test case -- add its diverging input.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
