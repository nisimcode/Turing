"""Q19 / D25: differential fuzzing -- close the L5 (arbitrary-point) gap.

A fixed battery is blind to a fault placed at an input nobody thought to probe
(subtlety_ladder.py: L5 false accepts 3/3). Differential testing replaces the
finite case list with probabilistic coverage of the whole input domain:

  strong tier emits  ->  referenceImpl(...)  +  randomInput()
  gate runs          ->  candidate vs reference over N random inputs, in-page

Run against the SAME subtlety ladder to compare directly with the fixed-battery
result. Measures whether fuzzing catches arbitrary-point bugs, and whether it
introduces false rejects (which would mean the generated reference is wrong).

    uv run --with anthropic --with playwright python fuzz_gate.py
"""

import json
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

import anthropic
from playwright.sync_api import sync_playwright

from subtlety_ladder import TASKS

HERE = Path(__file__).resolve().parent
MODEL = "claude-opus-4-8"
PRICING = (5.0, 25.0)
N_FUZZ = 20000

PROMPT = """Write TWO JavaScript functions for this specification.

  Function under test: {signature}
  Behaviour: {desc}

1. `function referenceImpl(...)` -- a correct implementation, same arguments and
   return type as the function under test.
2. `function randomInput()` -- returns an ARRAY holding one randomly generated
   argument list for that function. Sample across the WHOLE realistic input
   domain, not just typical values: vary sizes/lengths/magnitudes, and include
   boundaries and unusual-but-valid values. It will be called many thousands of
   times, so make the distribution broad.

Return ONLY the two functions in a single JavaScript code block."""


def load_api_key() -> str:
    for var in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    for env_path in (HERE / ".env", HERE.parent / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(("CLAUDE_API_KEY=", "ANTHROPIC_API_KEY=")):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("No API key found (set CLAUDE_API_KEY in E:\\Turing\\.env).")


client = anthropic.Anthropic(api_key=load_api_key())
_cost = 0.0


def gen_reference(task):
    global _cost
    prompt = PROMPT.format(signature=task["signature"], desc=task["desc"])
    resp = client.messages.create(model=MODEL, max_tokens=2048,
                                  messages=[{"role": "user", "content": prompt}])
    _cost += (resp.usage.input_tokens / 1e6 * PRICING[0]
              + resp.usage.output_tokens / 1e6 * PRICING[1])
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"```(?:javascript|js)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


PAGE = """<!doctype html><html><head><meta charset='utf-8'><title>fuzz</title></head>
<body><h1>fuzz</h1><div id='a'>x</div><div id='b'>y</div><button id='c'>go</button>
<script>
const __cand = (function(){ %CAND%
  return %FN%; })();
const __mod = (function(){ %REF%
  return {referenceImpl: typeof referenceImpl === 'function' ? referenceImpl : null,
          randomInput: typeof randomInput === 'function' ? randomInput : null}; })();
window.__fn = __cand;
window.__ref = __mod.referenceImpl;
window.__gen = __mod.randomInput;
window.__fuzz = function(n){
  if (!window.__ref || !window.__gen) return {ok:false, fatal:'missing ref/gen'};
  for (let i=0;i<n;i++){
    let args;
    try { args = window.__gen(); } catch(e){ return {ok:false, fatal:'gen threw: '+e.message}; }
    let a,b;
    try { a = JSON.stringify(window.__fn.apply(null,args)); } catch(e){ a='ERR:'+e.message; }
    try { b = JSON.stringify(window.__ref.apply(null,args)); } catch(e){ b='ERR:'+e.message; }
    if (a !== b) return {ok:false, i:i, args:args, got:a, want:b};
  }
  return {ok:true};
};
window.__sample = function(k){ const o=[]; for(let i=0;i<k;i++) o.push(window.__gen()); return o; };
</script></body></html>"""


def fuzz(candidate, fn_name, refcode, n=N_FUZZ, sample=False):
    html = (PAGE.replace("%CAND%", candidate).replace("%FN%", fn_name)
                .replace("%REF%", refcode))
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as f:
        path = f.name
        f.write(html)
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            pg = br.new_page()
            pg.goto(Path(path).as_uri(), wait_until="load")
            samp = pg.evaluate("(k) => window.__sample(k)", 6) if sample else None
            res = pg.evaluate("(n) => window.__fuzz(n)", n)
            br.close()
        return res, samp
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def main():
    levels = ["L0_correct", "L1_obvious", "L2_systematic", "L3_class",
              "L4_point", "L5_arbitrary"]
    caught, total = Counter(), Counter()
    false_rejects = 0

    for task in TASKS:
        ref = gen_reference(task)
        print(f"\n=== {task['id']} (fuzz N={N_FUZZ}) ===")
        first = True
        for lvl in levels:
            res, samp = fuzz(task["impls"][lvl], task["fn"], ref,
                             sample=first)
            first = False
            if samp is not None:
                print(f"    generator samples: {json.dumps(samp)[:130]}")
            if res.get("fatal"):
                print(f"    !! {res['fatal']}")
            passed = res.get("ok", False)
            if lvl == "L0_correct":
                if not passed:
                    false_rejects += 1
                    print(f"    {lvl:15} fuzz={'PASS' if passed else 'FAIL'}"
                          f"   <-- FALSE REJECT  {json.dumps(res.get('args'))[:60]}"
                          f" got={res.get('got')} want={res.get('want')}")
                else:
                    print(f"    {lvl:15} fuzz=PASS")
            else:
                total[lvl] += 1
                if not passed:
                    caught[lvl] += 1
                    print(f"    {lvl:15} fuzz=FAIL   (caught at i={res.get('i')}, "
                          f"args={json.dumps(res.get('args'))[:44]})")
                else:
                    print(f"    {lvl:15} fuzz=PASS   <-- FALSE ACCEPT")

    print("\n=== catch rate by subtlety: FUZZ vs fixed battery ===")
    battery_ref = {"L1_obvious": 3, "L2_systematic": 3, "L3_class": 3,
                   "L4_point": 3, "L5_arbitrary": 0}   # from subtlety_ladder.py
    for lvl in levels[1:]:
        print(f"  {lvl:15} fuzz {caught[lvl]}/{total[lvl]}    "
              f"fixed battery {battery_ref[lvl]}/3")
    fa = sum(total[l] - caught[l] for l in levels[1:])
    print(f"\n  fuzz false-accepts: {fa}/{sum(total.values())}"
          f"   (fixed battery: 3/15)")
    print(f"  fuzz false-rejects: {false_rejects}/{len(TASKS)}")
    print(f"  reference generation cost: ${_cost:.4f}")

    print("\n=== read ===")
    if caught["L5_arbitrary"] == total["L5_arbitrary"] and false_rejects == 0:
        print("  Differential fuzzing closes the L5 gap that a fixed battery cannot:")
        print("  arbitrary-point faults are found because coverage is probabilistic")
        print("  over the whole domain, not a finite list. Adopt it wherever the")
        print("  logic slot is a pure function.")
    elif false_rejects:
        print("  Fuzzing rejected CORRECT code -> the generated reference (or the")
        print("  input generator) is itself wrong. Reference quality is now the")
        print("  bottleneck; it needs the same cross-check treatment as oracles.")
    else:
        print("  Fuzzing did not catch every arbitrary-point fault -- check the")
        print("  input generator's domain coverage.")


if __name__ == "__main__":
    main()
