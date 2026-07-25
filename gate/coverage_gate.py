"""Q20 / D27: coverage-aware gating -- enumerate small domains, fuzz large ones.

fuzz_gate.py showed differential fuzzing catches arbitrary-point faults *if* the
generator happens to sample them: it caught the "77" and length===9 faults but
missed `n === 1847`, because coverage is only as good as the generator's
distribution.

Fix: have the strong tier also declare the DOMAIN. If the input domain is finite
and small enough to enumerate, test it EXHAUSTIVELY -- then arbitrary-point
faults are impossible to hide. Otherwise fall back to random fuzzing, and report
coverage diagnostics so a weak generator is visible rather than silent.

    uv run --with anthropic --with playwright python coverage_gate.py
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
ENUM_CAP = 100000          # enumerate domains up to this many cases

PROMPT = """Write THREE JavaScript functions for this specification.

  Function under test: {signature}
  Behaviour: {desc}

1. `function referenceImpl(...)` -- a correct implementation, same arguments and
   return type as the function under test.

2. `function enumerateDomain()` -- if the set of VALID inputs is finite and has
   at most {cap} members, return an array of EVERY valid argument list (each
   element is itself an array of arguments), covering the domain completely.
   If the domain is infinite or larger than {cap}, return null instead.

3. `function randomInput()` -- returns an array holding one randomly generated
   argument list, sampled broadly across the realistic domain (vary
   sizes/lengths/magnitudes; include boundaries). Used only when
   enumerateDomain() returns null.

Return ONLY the three functions in a single JavaScript code block."""


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


def gen_harness(task):
    global _cost
    prompt = PROMPT.format(signature=task["signature"], desc=task["desc"],
                           cap=ENUM_CAP)
    resp = client.messages.create(model=MODEL, max_tokens=3000,
                                  messages=[{"role": "user", "content": prompt}])
    _cost += (resp.usage.input_tokens / 1e6 * PRICING[0]
              + resp.usage.output_tokens / 1e6 * PRICING[1])
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"```(?:javascript|js)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


PAGE = """<!doctype html><html><head><meta charset='utf-8'><title>cov</title></head>
<body><h1>coverage gate</h1><div id='a'>x</div><div id='b'>y</div>
<button id='c'>go</button>
<script>
const __cand = (function(){ %CAND%
  return %FN%; })();
const __m = (function(){ %REF%
  return {referenceImpl: typeof referenceImpl==='function'?referenceImpl:null,
          enumerateDomain: typeof enumerateDomain==='function'?enumerateDomain:null,
          randomInput: typeof randomInput==='function'?randomInput:null}; })();
window.__fn=__cand; window.__ref=__m.referenceImpl;
window.__enum=__m.enumerateDomain; window.__gen=__m.randomInput;

window.__domain = function(){
  if (!window.__enum) return {mode:'fuzz', reason:'no enumerateDomain'};
  let d; try { d = window.__enum(); } catch(e){ return {mode:'fuzz', reason:'enum threw'}; }
  if (!d || !d.length) return {mode:'fuzz', reason:'domain infinite/too large'};
  return {mode:'enumerate', size:d.length};
};

function __cmp(args){
  let a,b;
  try { a = JSON.stringify(window.__fn.apply(null,args)); } catch(e){ a='ERR:'+e.message; }
  try { b = JSON.stringify(window.__ref.apply(null,args)); } catch(e){ b='ERR:'+e.message; }
  return a===b ? null : {args:args, got:a, want:b};
}

window.__runExhaustive = function(){
  const d = window.__enum();
  for (let i=0;i<d.length;i++){ const m=__cmp(d[i]); if(m){ m.i=i; return {ok:false, ...m}; } }
  return {ok:true, checked:d.length};
};

window.__runFuzz = function(n){
  const seen = new Set();
  for (let i=0;i<n;i++){
    let args; try { args = window.__gen(); } catch(e){ return {ok:false, fatal:'gen threw'}; }
    seen.add(JSON.stringify(args));
    const m = __cmp(args);
    if (m){ m.i=i; m.distinct=seen.size; return {ok:false, ...m}; }
  }
  return {ok:true, checked:n, distinct:seen.size};
};
</script></body></html>"""


def run(candidate, fn_name, harness, want_domain=False):
    html = (PAGE.replace("%CAND%", candidate).replace("%FN%", fn_name)
                .replace("%REF%", harness))
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as f:
        path = f.name
        f.write(html)
    try:
        with sync_playwright() as p:
            br = p.chromium.launch()
            pg = br.new_page()
            pg.goto(Path(path).as_uri(), wait_until="load")
            dom = pg.evaluate("() => window.__domain()")
            if dom["mode"] == "enumerate":
                res = pg.evaluate("() => window.__runExhaustive()")
            else:
                res = pg.evaluate("(n) => window.__runFuzz(n)", N_FUZZ)
            br.close()
        return (res, dom) if want_domain else (res, dom)
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
        harness = gen_harness(task)
        print(f"\n=== {task['id']} ===")
        first = True
        for lvl in levels:
            res, dom = run(task["impls"][lvl], task["fn"], harness)
            if first:
                if dom["mode"] == "enumerate":
                    print(f"    domain: ENUMERABLE ({dom['size']} cases) "
                          f"-> exhaustive check")
                else:
                    print(f"    domain: infinite/large ({dom.get('reason')}) "
                          f"-> fuzz N={N_FUZZ}")
                first = False
            passed = res.get("ok", False)
            extra = ""
            if not passed and "args" in res:
                extra = f"  at args={json.dumps(res['args'])[:40]}"
            if passed and "distinct" in res:
                extra = f"  ({res['distinct']} distinct inputs sampled)"
            if lvl == "L0_correct":
                if not passed:
                    false_rejects += 1
                print(f"    {lvl:15} {'PASS' if passed else 'FAIL'}"
                      + ("   <-- FALSE REJECT" if not passed else "") + extra)
            else:
                total[lvl] += 1
                if not passed:
                    caught[lvl] += 1
                print(f"    {lvl:15} {'PASS' if passed else 'FAIL'}"
                      + ("   <-- FALSE ACCEPT" if passed else "   (caught)") + extra)

    print("\n=== catch rate: coverage-aware vs earlier approaches ===")
    prior = {"L1_obvious": (3, 3), "L2_systematic": (3, 3), "L3_class": (3, 3),
             "L4_point": (3, 3), "L5_arbitrary": (0, 2)}   # (battery, fuzz)
    print(f"  {'level':16} {'battery':>8} {'fuzz':>6} {'coverage-aware':>15}")
    for lvl in levels[1:]:
        b, f = prior[lvl]
        print(f"  {lvl:16} {b:>6}/3 {f:>4}/3 {caught[lvl]:>13}/{total[lvl]}")
    fa = sum(total[l] - caught[l] for l in levels[1:])
    print(f"\n  false accepts: {fa}/{sum(total.values())}"
          f"   (battery 3/15, fuzz 1/15)")
    print(f"  false rejects: {false_rejects}/{len(TASKS)}")
    print(f"  harness generation cost: ${_cost:.4f}")

    print("\n=== read ===")
    if fa == 0 and false_rejects == 0:
        print("  Coverage-aware gating closes the arbitrary-point gap: enumerable")
        print("  domains are checked exhaustively, so no fault can hide in an")
        print("  untested input. Adopt: declare the domain, enumerate if you can,")
        print("  fuzz only when you must.")
    else:
        print("  Gap not fully closed -- inspect which task still leaks and why")
        print("  (domain mis-declared, or generator coverage too narrow).")


if __name__ == "__main__":
    main()
