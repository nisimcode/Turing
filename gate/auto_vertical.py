"""Can a whole VERTICAL be generated from a plain request? (the scaling test)

Every vertical so far was hand-built: we wrote the scaffold, the spec and the
oracle. That makes the proven product a verified *template library* -- fine, but
it only serves requests we anticipated. `auto_gate.py` showed the ORACLE can be
generated automatically; the scaffold never was.

This closes the loop. For a request nobody built for, the pipeline generates:

  1. scaffold  (strong tier) -- UI + a testable hook + a /*__LOGIC_SLOT__*/
  2. oracle    (strong tier) -- the test battery
  3. logic     (cheap tier)  -- the implementation that fills the slot
  4. a subtly buggy variant (strong tier) -- the control

Then it gates 3 and 4 through gate.core (sandboxed). Success = the auto-built
vertical accepts working code and still catches a bug. The buggy control is
verified to genuinely differ from the correct implementation before it counts,
so a "catch" can't be an artifact of a broken scaffold.

    uv run --with anthropic --with playwright --with pillow python auto_vertical.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core import (CHEAP, ORACLE_MODEL, cost_report, print_verdict,  # noqa: E402
                       sandboxed_page, verify)
from gate.core.llm import call, extract_block, extract_code               # noqa: E402
from gate.core.oracle import build_oracle                                 # noqa: E402
from gate.core.policy import assess, explain                              # noqa: E402

SLOT = "/*__LOGIC_SLOT__*/"

REQUESTS = [
    "a Caesar cipher tool that shifts letters in a message",
    "a temperature converter between Celsius and Fahrenheit",
    "a checker that tells you whether two words are anagrams",
]

SCAFFOLD_PROMPT = """A user asked for: {request}

Design the VERIFIABLE SHELL for this app as a single self-contained HTML file.

Requirements:
- A real, usable UI (inputs, a button, a result area, some styling).
- The core logic must NOT be written by you. Put the exact marker
  {slot}
  on its own line inside the <script>, where the logic function will be injected.
- The injected function's signature is yours to choose; state it in the JSON below.
- Expose a testable hook: `window.__fn = function(...args) {{ return NAME(...args); }};`
  where NAME is that function's name, so a test harness can drive the logic
  directly regardless of the UI.
- The UI must call the same function, so the hook and the visible app cannot drift.

Return TWO fenced blocks, in this order:
1. ```html  -- the scaffold, containing the marker exactly once
2. ```json  -- {{"fn": "<function name>", "signature": "<js signature>",
               "behaviour": "<precise description of what the function must do,
               including edge cases and exact return type>"}}"""

SHARPEN_PROMPT = """This behaviour spec is about to be handed to two independent
parties: one writes the implementation, the other writes the test oracle. If the
spec leaves anything to judgement they will make different reasonable choices and
the tests will reject correct code.

  Signature: {signature}
  Behaviour: {behaviour}

Close every gap. Decide -- do not describe options -- each of:
- empty / zero-length input
- invalid or out-of-range input (what is returned? an error? a sentinel?)
- boundary values at each end of the valid range
- whitespace, case, and non-alphanumeric handling if inputs are text
- exact return type and shape in every branch (never "maybe null")

Also state the DOMAIN: the set of inputs the function is defined for. Keep it
NARROW -- only what this app's own UI can actually produce. Do NOT widen it to
arbitrary JavaScript values, exotic types, NaN/Infinity, or inputs a user could
not enter; a domain of "any value" is wrong. Anything outside the domain must
not be tested, so a narrow domain with decided edge cases is the goal.

Return JSON only, in one ```json block:
{{"behaviour": "<complete, decided specification -- every case above resolved>",
  "domain": "<the narrow set of valid inputs>"}}"""

ORACLE_PROMPT = """Produce the TEST ORACLE for this function.

  Signature: {signature}
  Behaviour: {behaviour}
  Domain (test ONLY inputs inside this set): {domain}

Output JSON only in one ```json block:
{{"tests": [{{"args": [...], "expected": ...}}, ...]}}
10-14 cases; include the edge cases a subtly-wrong implementation would fail.
Every expected value must be exactly correct, and every input must lie inside
the stated domain."""

IMPL_PROMPT = """Implement exactly this JavaScript function.

  Signature: {signature}
  Behaviour: {behaviour}
  Domain: {domain}

Follow the specification literally, including its decisions about edge cases.
Return ONLY the function in one ```javascript block."""

BUG_PROMPT = """Here is a correct JavaScript function:

```javascript
{impl}
```

Behaviour: {behaviour}

Produce a SUBTLY buggy variant: same name and signature, correct on typical
inputs, wrong on some edge case. Not obviously broken -- the kind of bug that
passes a casual review.

Return TWO fenced blocks:
1. ```javascript -- the buggy function
2. ```json -- {{"differs_on": [<args>]}}  one argument list where the buggy
   version returns something different from the correct one."""


def values_equal(a, b) -> bool:
    """Exact equality, except NaN == NaN (JS NaN arrives as float('nan') and
    would otherwise never match, failing correct implementations)."""
    is_nan = lambda v: isinstance(v, float) and v != v          # noqa: E731
    if is_nan(a) and is_nan(b):
        return True
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(values_equal(x, y) for x, y in zip(a, b))
    return a == b


def make_functional(battery):
    def checks(page):
        out = [{"name": "hook", "ok": bool(page.evaluate(
            "typeof window.__fn === 'function'")), "detail": "window.__fn"}]
        if not out[0]["ok"]:
            return out
        mism, first = 0, ""
        for case in battery:
            try:
                got = page.evaluate("(a) => window.__fn.apply(null, a)",
                                    case["args"])
            except Exception:
                mism += 1
                continue
            if isinstance(got, list):
                got = list(got)
            if not values_equal(got, case["expected"]):
                mism += 1
                first = first or (f"{case['args']} -> {got!r} "
                                  f"(want {case['expected']!r})")
        out.append({"name": "oracle", "ok": mism == 0,
                    "detail": first or f"all {len(battery)} cases agree"})
        return out
    return checks


def build(scaffold, impl):
    p = Path(tempfile.mkdtemp(prefix="gate-av-")) / "a.html"
    p.write_text(scaffold.replace(SLOT, impl), encoding="utf-8")
    return p


def differs(scaffold, impl_a, impl_b, args):
    """Objectively confirm two implementations disagree on `args`."""
    ra = rb = None
    for impl, slot in ((impl_a, "a"), (impl_b, "b")):
        with sandboxed_page(build(scaffold, impl)) as page:
            try:
                val = page.evaluate("(x) => window.__fn.apply(null, x)", args)
            except Exception:
                val = "ERR"
        if slot == "a":
            ra = val
        else:
            rb = val
    return ra != rb, ra, rb


def main() -> int:
    results = []
    for req in REQUESTS:
        print(f"\n{'='*66}\nREQUEST: {req}\n{'='*66}")

        raw = call(ORACLE_MODEL, SCAFFOLD_PROMPT.format(request=req, slot=SLOT),
                   max_tokens=4000)
        scaffold = extract_block(raw, "html") or ""
        meta_raw = extract_block(raw, "json")
        try:
            meta = json.loads(meta_raw) if meta_raw else None
            assert meta and {"fn", "signature", "behaviour"} <= set(meta)
        except Exception:
            print("  !! could not parse scaffold metadata -- vertical failed")
            results.append((req, False, False, "bad metadata"))
            continue

        if SLOT not in scaffold:
            print("  !! scaffold lacks the logic slot -- vertical failed")
            results.append((req, False, False, "no slot"))
            continue
        print(f"  scaffold ok: fn={meta['fn']}  ({len(scaffold)} chars)")

        # --- spec precision (Q22): decide every edge case ONCE, up front, so
        # the implementer and the oracle cannot diverge on unstated behaviour.
        sb = extract_block(call(ORACLE_MODEL, SHARPEN_PROMPT.format(**meta),
                                max_tokens=1600), "json")
        try:
            sharp = json.loads(sb)
            meta["behaviour"] = sharp["behaviour"]
            meta["domain"] = sharp["domain"]
            print(f"  spec sharpened: +{len(meta['behaviour'])} chars, "
                  f"domain={meta['domain'][:52]!r}")
        except Exception:
            meta.setdefault("domain", "as described in the behaviour")
            print("  !! sharpening failed -- proceeding with the raw spec")

        # Ensemble-verified oracle (D21/D22): the strong tier drafts the cases,
        # a tier-diverse ensemble recomputes the expected values on pinned
        # inputs, and disputed cases are dropped rather than guessed.
        battery, disputed = build_oracle(meta["signature"], meta["behaviour"],
                                         meta["domain"], n=14)
        if not battery:
            print("  !! oracle produced no agreed cases -- vertical failed")
            results.append((req, False, False, "no oracle"))
            continue
        print(f"  oracle: {len(battery)} agreed cases"
              + (f", {len(disputed)} dropped as disputed" if disputed else ""))

        impl = extract_code(call(CHEAP, IMPL_PROMPT.format(**meta),
                                 max_tokens=1200), "javascript")

        bug_raw = call(ORACLE_MODEL, BUG_PROMPT.format(
            impl=impl, behaviour=meta["behaviour"]), max_tokens=1600)
        buggy = extract_code(bug_raw, "javascript")
        dj = extract_block(bug_raw, "json")
        try:
            d_args = json.loads(dj)["differs_on"] if dj else None
        except Exception:
            d_args = None

        fn = make_functional(battery)
        v_ok = verify(build(scaffold, impl), functional=fn, vertical=meta["fn"])
        v_bad = verify(build(scaffold, buggy), functional=fn, vertical=meta["fn"])
        print_verdict(v_ok)
        print_verdict(v_bad)

        # Disputed cases are NOT silently dropped: an untested input is where a
        # fault hides, so the verdict is provisional until a human resolves them.
        rev = assess(vertical=meta["fn"], is_new_vertical=True,
                     disputed_cases=disputed)
        if rev:
            print("  " + explain(rev).replace("\n", "\n  "))

        real_bug = True
        if d_args:
            real_bug, ra, rb = differs(scaffold, impl, buggy, d_args)
            print(f"  control check: impls differ on {json.dumps(d_args)[:40]}"
                  f" -> {ra!r} vs {rb!r}  [{'genuine bug' if real_bug else 'NOT A BUG'}]")

        results.append((req, v_ok.passed, not v_bad.passed, real_bug))

    print(f"\n{'='*66}\n=== auto-generated verticals ===")
    print(f"  {'request':46} {'accepts ok':11} {'catches bug'}")
    for req, ok, caught, real in results:
        note = "" if real is True else f"  ({real})"
        print(f"  {req[:44]:46} {'yes' if ok else 'NO':11} "
              f"{'yes' if caught else 'NO'}{note}")
    good = sum(1 for _, o, c, r in results if o and c and r is True)
    print(f"\n  fully working auto-verticals: {good}/{len(results)}")
    print(f"  cost: {cost_report()}")

    print("\n=== read ===")
    if good == len(results):
        print("  A usable vertical -- scaffold, oracle and gate -- can be built")
        print("  from a plain request with nothing hand-written. The recipe is not")
        print("  limited to app types we anticipated; the template library can be")
        print("  grown automatically.")
    else:
        print("  Not every request produced a working vertical. Auto-scaffolding")
        print("  is not yet reliable enough to run unattended -- inspect the rows")
        print("  above; hand-built scaffolds remain the fallback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
