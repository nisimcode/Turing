"""Can a whole VERTICAL be generated from a plain request? (the scaling test)

Every initial vertical was hand-built: we wrote the scaffold, the spec and the
oracle. That made the proven product a verified *template library* -- fine, but
it only served requests we anticipated. The archived `auto_gate.py` experiment
showed the ORACLE could be generated automatically; the scaffold never was.

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

Q24 also scores each generated battery against mutants whose behavioural
divergence is established on a separate, independently generated probe pool:

    uv run --with anthropic --with playwright --with pillow python auto_vertical.py --mutation-score
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import tempfile
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core import (CHEAP, ORACLE_MODEL, cost_report, print_verdict,  # noqa: E402
                       sandboxed_page, verify)
from gate.core.llm import (LLMCallBlocked, call, extract_block,           # noqa: E402
                           extract_code)
from gate.core.identity import revision_digest                           # noqa: E402
from gate.core.domain import validate_args                               # noqa: E402
from gate.core.mutation import (mutation_score,                          # noqa: E402
                                validated_mechanical_mutants,
                                validated_mutants)
from gate.core.oracle import (build_oracle_detailed,                     # noqa: E402
                              draft_battery)
from gate.core.policy import assess, explain                              # noqa: E402

SLOT = "/*__LOGIC_SLOT__*/"
MUTANTS_WANTED = 5
MUTATION_PROBES = 40

REQUESTS = [
    "a Caesar cipher tool that shifts letters in a message",
    "a temperature converter between Celsius and Fahrenheit",
    "a checker that tells you whether two words are anagrams",
    "a word counter that counts whitespace-separated words in a text",
    "a shipping-price calculator based on an integer package weight in grams",
    "a validator for usernames made from ASCII letters, digits, and underscores",
    "a tool that returns min, max, sum, and average for a list of integers",
    "a 24-hour clock tool that adds integer minutes and wraps across midnight",
    "a checker that validates a Gregorian calendar date",
    "a text tool that counts overlapping occurrences of one substring in another",
    "a tool that clamps an integer to the inclusive range from 0 to 100",
    "a checker that tests whether one integer is evenly divisible by another nonzero integer",
    "a formatter that converts red, green, and blue integers from 0 to 255 into a six-digit uppercase hex color",
    "a formatter that converts an integer duration from 0 to 359999 seconds into zero-padded HH:MM:SS",
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
  "domain": "<the narrow set of valid inputs>",
  "domain_schema": {{"args": [<one schema per function argument>]}}}}

`domain_schema` is mandatory and machine-enforced. Supported schemas:
- string: {{"type":"string", "minLength":0, "maxLength":100,
             "pattern":"optional full-match regex"}}
- integer/number: {{"type":"integer", "minimum":0, "maximum":100}}
- boolean: {{"type":"boolean"}}
- array: {{"type":"array", "minItems":0, "maxItems":10,
            "items":<schema>, "uniqueItems":false}}
- exact alternatives: add "enum":[...].
Use only keys shown above. Encode the SAME narrow domain described in `domain`;
do not add invalid-input cases to the schema."""

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


def independent_probe_inputs(signature, behaviour, domain, battery,
                             n=MUTATION_PROBES):
    """Generate mutation witnesses independently of the battery being scored.

    Reusing the battery as the probe pool would make the result circular:
    every mutant accepted as observable would, by definition, already be
    killed by that battery. Expected values from this second draft are ignored;
    only its in-domain inputs are used to execute original vs mutant.
    """
    draft = draft_battery(signature, behaviour, domain, n=n)
    battery_keys = {
        json.dumps(case["args"], sort_keys=True, default=str)
        for case in battery
    }
    seen = set()
    probes = []
    for case in draft:
        args = case["args"]
        key = json.dumps(args, sort_keys=True, default=str)
        if key in battery_keys or key in seen:
            continue
        seen.add(key)
        probes.append(args)
    return probes


def _schema_values(spec, observed):
    if "enum" in spec:
        return list(spec["enum"])
    kind = spec.get("type")
    values = list(observed)
    if kind in {"integer", "number"}:
        low = spec.get("minimum", 0)
        high = spec.get("maximum", max(low + 2, 10))
        values.extend([low, high, low + 1, high - 1, 0, 1, -1,
                       (low + high) // 2])
        for value in observed:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.extend([value - 2, value - 1, value + 1, value + 2])
    elif kind == "boolean":
        values.extend([False, True])
    elif kind == "string":
        minimum = spec.get("minLength", 0)
        maximum = spec.get("maxLength", max(minimum, 12))
        values.extend([
            "", "a", "A", "0", "_", " ", "ab", "a_b", "test",
            "two words", "a" * minimum, "z" * min(maximum, 32),
        ])
        for value in observed:
            if isinstance(value, str):
                values.extend([
                    value.lower(), value.upper(), value[::-1],
                    value[:1], value[:-1], value + value[:1],
                    " " + value, value + " ",
                ])
    elif kind == "array":
        values.append([])
        for value in observed:
            if isinstance(value, list):
                values.extend([
                    value[:1], value[::-1], value + value[:1],
                ])
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def schema_probe_inputs(domain_schema, battery, limit=500):
    """Build deterministic in-domain probes disjoint from the scored battery."""
    specs = (
        domain_schema.get("args")
        if isinstance(domain_schema, dict) else None
    )
    if not isinstance(specs, list) or not battery:
        return []
    observed = [
        [case["args"][index] for case in battery
         if len(case.get("args", [])) > index]
        for index in range(len(specs))
    ]
    choices = [
        _schema_values(spec, values)
        for spec, values in zip(specs, observed)
    ]
    excluded = {
        json.dumps(case["args"], sort_keys=True, default=str)
        for case in battery
    }
    probes, seen = [], set()

    def add(args):
        key = json.dumps(args, sort_keys=True, default=str)
        if key in excluded or key in seen or validate_args(args, domain_schema):
            return
        seen.add(key)
        probes.append(args)

    baseline = list(battery[0]["args"])
    for index, values in enumerate(choices):
        for value in values:
            candidate = list(baseline)
            candidate[index] = value
            add(candidate)
    for combo in itertools.product(*(values[:8] for values in choices)):
        add(list(combo))
        if len(probes) >= limit:
            break
    return probes[:limit]


def deterministic_caesar_probes(battery):
    """Broad, zero-cost boundary grid for re-probing cached Caesar mutants."""
    texts = [
        "", "a", "z", "A", "Z", "az", "AZ", "xyz", "XYZ",
        "Hello, World!", "MixedCASE 123!@#", "a z", " \t\n",
        "abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "😀", "a😀z", "éclair", "Shift-100 test",
    ]
    shifts = [
        -1_000_000, -101, -100, -53, -52, -27, -26, -25,
        -2, -1.9, -1, -0.9, 0, 0.9, 1, 1.9, 2,
        25, 26, 27, 52, 53, 100, 101, 1_000_000,
    ]
    excluded = {
        json.dumps(case["args"], sort_keys=True, default=str)
        for case in battery
    }
    return [
        [text, shift]
        for text in texts
        for shift in shifts
        if json.dumps([text, shift], sort_keys=True, default=str)
        not in excluded
    ]


def caesar_reference(text, shift):
    """Independent Python reference for the sharpened Caesar domain."""
    if not isinstance(text, str):
        raise ValueError("text is outside the Caesar domain")
    if (isinstance(shift, bool) or not isinstance(shift, int)
            or not -100 <= shift <= 100):
        raise ValueError("shift is outside the Caesar domain")
    normalized = shift % 26
    out = []
    for char in text:
        code = ord(char)
        if 65 <= code <= 90:
            out.append(chr(65 + (code - 65 + normalized) % 26))
        elif 97 <= code <= 122:
            out.append(chr(97 + (code - 97 + normalized) % 26))
        else:
            out.append(char)
    return "".join(out)


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


def executable_probe_inputs(scaffold, impl, inputs):
    """Keep only probes the passing baseline can execute successfully."""
    with sandboxed_page(build(scaffold, impl)) as page:
        ok = page.evaluate(
            """(allArgs) => allArgs.map(args => {
                 try { window.__fn.apply(null, args); return true; }
                 catch (e) { return false; }
               })""",
            inputs,
        )
    return [probe for probe, passed in zip(inputs, ok) if passed]


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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mutation-score",
        action="store_true",
        help="Q24: score each generated battery against independently "
             "execution-validated mutants",
    )
    parser.add_argument(
        "--q25-mode",
        action="store_true",
        help="prepare human-review dossiers using deterministic schema probes "
             "and a hybrid of one model-proposed plus local validated mutants",
    )
    parser.add_argument(
        "--cache-dir",
        help="checkpoint model responses here; defaults to "
             "gate/.llm-cache/q24 in mutation-score mode",
    )
    parser.add_argument(
        "--request-index",
        type=int,
        choices=range(len(REQUESTS)),
        help=f"run only one request (0..{len(REQUESTS) - 1})",
    )
    parser.add_argument(
        "--max-paid-calls",
        type=int,
        help="refuse new model calls after this many cached paid responses; "
             "defaults to 25 in mutation-score mode",
    )
    parser.add_argument(
        "--cache-only",
        action="store_true",
        help="refuse every cache miss; guarantees that no API call is made",
    )
    parser.add_argument(
        "--caesar-reprobe",
        action="store_true",
        help="add a deterministic zero-cost Caesar boundary grid to mutation "
             "probes (requires --request-index 0)",
    )
    parser.add_argument(
        "--caesar-resolve-disputes",
        action="store_true",
        help="resolve in-domain Caesar disputes with the independent local "
             "Python reference (requires --request-index 0)",
    )
    args = parser.parse_args()
    if args.q25_mode and not args.mutation_score:
        parser.error("--q25-mode requires --mutation-score")
    if ((args.caesar_reprobe or args.caesar_resolve_disputes)
            and args.request_index != 0):
        parser.error("Caesar-specific options require --request-index 0")
    if args.cache_dir or args.mutation_score:
        default_cache = "q25" if args.q25_mode else "q24"
        cache_dir = Path(args.cache_dir) if args.cache_dir else (
            Path(__file__).resolve().parent / ".llm-cache" / default_cache
        )
        os.environ["GATE_LLM_CACHE_DIR"] = str(cache_dir.resolve())
        print(f"LLM response cache: {cache_dir.resolve()}")
    if args.max_paid_calls is not None or args.mutation_score:
        paid_limit = (
            args.max_paid_calls if args.max_paid_calls is not None
            else (140 if args.q25_mode else 25)
        )
        if paid_limit < 1:
            parser.error("--max-paid-calls must be positive")
        os.environ["GATE_LLM_MAX_PAID_CALLS"] = str(paid_limit)
        print(f"Paid-response cap: {paid_limit}")
    if args.cache_only:
        os.environ["GATE_LLM_CACHE_ONLY"] = "1"
        print("Cache-only mode: API calls disabled")

    results = []
    mutation_rows = []
    requests = (
        [REQUESTS[args.request_index]]
        if args.request_index is not None else REQUESTS
    )
    for req in requests:
        print(f"\n{'='*66}\nREQUEST: {req}\n{'='*66}")

        try:
            raw = call(
                ORACLE_MODEL,
                SCAFFOLD_PROMPT.format(request=req, slot=SLOT),
                max_tokens=4000,
            )
        except LLMCallBlocked as exc:
            print(f"  !! skipped safely: {exc}")
            results.append((req, False, False, "model call blocked"))
            if args.mutation_score:
                mutation_rows.append((
                    req, None, 0, [], "model call blocked"
                ))
            continue
        scaffold = extract_block(raw, "html") or ""
        meta_raw = extract_block(raw, "json")
        try:
            meta = json.loads(meta_raw) if meta_raw else None
            assert meta and {"fn", "signature", "behaviour"} <= set(meta)
        except Exception:
            print("  !! could not parse scaffold metadata -- vertical failed")
            results.append((req, False, False, "bad metadata"))
            if args.mutation_score:
                mutation_rows.append((req, None, 0, [], "bad metadata"))
            continue

        if SLOT not in scaffold:
            print("  !! scaffold lacks the logic slot -- vertical failed")
            results.append((req, False, False, "no slot"))
            if args.mutation_score:
                mutation_rows.append((req, None, 0, [], "no slot"))
            continue
        print(f"  scaffold ok: fn={meta['fn']}  ({len(scaffold)} chars)")

        # --- spec precision (Q22): decide every edge case ONCE, up front, so
        # the implementer and the oracle cannot diverge on unstated behaviour.
        try:
            sharpened = call(
                ORACLE_MODEL,
                SHARPEN_PROMPT.format(**meta),
                max_tokens=1600,
            )
        except LLMCallBlocked as exc:
            print(f"  !! skipped safely: {exc}")
            results.append((req, False, False, "model call blocked"))
            if args.mutation_score:
                mutation_rows.append((
                    req, None, 0, [], "model call blocked"
                ))
            continue
        sb = extract_block(sharpened, "json")
        try:
            sharp = json.loads(sb)
            meta["behaviour"] = sharp["behaviour"]
            meta["domain"] = sharp["domain"]
            meta["domain_schema"] = sharp["domain_schema"]
            print(f"  spec sharpened: +{len(meta['behaviour'])} chars, "
                  f"domain={meta['domain'][:52]!r}")
        except Exception:
            meta.setdefault("domain", "as described in the behaviour")
            meta.setdefault("domain_schema", None)
            print("  !! sharpening failed -- proceeding with the raw spec")

        # Ensemble-verified oracle (D21/D22): the strong tier drafts the cases,
        # a tier-diverse ensemble recomputes the expected values on pinned
        # inputs, and disputed cases are dropped rather than guessed.
        try:
            oracle = build_oracle_detailed(
                meta["signature"],
                meta["behaviour"],
                meta["domain"],
                meta.get("domain_schema"),
                n=14,
            )
        except LLMCallBlocked as exc:
            print(f"  !! skipped safely: {exc}")
            results.append((req, False, False, "model call blocked"))
            if args.mutation_score:
                mutation_rows.append((
                    req, None, 0, [], "model call blocked"
                ))
            continue
        battery = oracle.battery
        disputed = oracle.disputed
        clarifications = oracle.clarifications
        if clarifications:
            print(f"  spec clarification required: "
                  f"{len(clarifications)} domain issue(s)")
        if ((args.caesar_resolve_disputes or args.q25_mode)
                and req == REQUESTS[0] and disputed):
            unresolved = []
            recovered = []
            for case in disputed:
                try:
                    expected = caesar_reference(*case["args"])
                except (TypeError, ValueError):
                    unresolved.append(case)
                    continue
                recovered.append({
                    "args": case["args"],
                    "expected": expected,
                })
            battery.extend(recovered)
            disputed = unresolved
            print(f"  local Caesar reference resolved: {len(recovered)}, "
                  f"still disputed: {len(disputed)}")
        if not battery:
            print("  !! oracle produced no agreed cases -- vertical failed")
            results.append((req, False, False, "no oracle"))
            if args.mutation_score:
                mutation_rows.append((req, None, 0, [], "no oracle"))
            continue
        print(f"  oracle: {len(battery)} agreed cases"
              + (f", {len(disputed)} dropped as disputed" if disputed else ""))

        try:
            impl_raw = call(
                CHEAP,
                IMPL_PROMPT.format(**meta),
                max_tokens=1200,
            )
        except LLMCallBlocked as exc:
            print(f"  !! skipped safely: {exc}")
            results.append((req, False, False, "model call blocked"))
            if args.mutation_score:
                mutation_rows.append((
                    req, None, 0, [], "model call blocked"
                ))
            continue
        impl = extract_code(impl_raw, "javascript")

        fn = make_functional(battery)
        v_ok = verify(build(scaffold, impl), functional=fn, vertical=meta["fn"])
        print_verdict(v_ok)

        # In the general experiment a model proposes the explicit bad control.
        # Q25 instead reuses an execution-validated mutant that the battery
        # demonstrably kills (selected after mutation scoring below). That is
        # stronger evidence and avoids a separate model call.
        buggy, d_args, real_bug, v_bad = "", None, False, None
        control_attempts = 0 if args.q25_mode else 1
        for control_attempt in range(control_attempts):
            try:
                bug_raw = call(
                    ORACLE_MODEL,
                    BUG_PROMPT.format(
                        impl=impl, behaviour=meta["behaviour"]
                    ),
                    max_tokens=1600,
                    cache_variant=(
                        None if control_attempt == 0
                        else f"bug-control-{control_attempt}"
                    ),
                )
            except LLMCallBlocked as exc:
                print(f"  control generation stopped safely: {exc}")
                break
            buggy = extract_code(bug_raw, "javascript")
            dj = extract_block(bug_raw, "json")
            try:
                d_args = json.loads(dj)["differs_on"] if dj else None
            except Exception:
                d_args = None
            v_bad = verify(
                build(scaffold, buggy),
                functional=fn,
                vertical=meta["fn"],
            )
            real_bug = False
            if d_args:
                real_bug, ra, rb = differs(
                    scaffold, impl, buggy, d_args
                )
                print(
                    "  control check: impls differ on "
                    f"{json.dumps(d_args)[:40]} -> {ra!r} vs {rb!r}  "
                    f"[{'genuine bug' if real_bug else 'NOT A BUG'}]"
                )
            if real_bug and not v_bad.passed:
                break
            print(
                f"  control attempt {control_attempt + 1}/"
                f"{control_attempts} did not satisfy release checks"
            )
        if v_bad is None and not args.q25_mode:
            print("  !! no buggy control was generated")
            results.append((req, v_ok.passed, False, "model call blocked"))
            if args.mutation_score:
                mutation_rows.append((
                    req, None, 0, [], "model call blocked"
                ))
            continue

        mutation_control = None
        mutants = []
        scored = None
        if args.mutation_score:
            if not v_ok.passed:
                print("  mutation score: skipped (the baseline implementation "
                      "does not pass its battery)")
                mutation_rows.append((req, None, 0, [], "baseline failed"))
            else:
                if args.q25_mode:
                    drafted_probes = schema_probe_inputs(
                        meta.get("domain_schema"), battery
                    )
                    print(f"  local schema probes: {len(drafted_probes)}")
                else:
                    try:
                        drafted_probes = independent_probe_inputs(
                            meta["signature"], meta["behaviour"], meta["domain"],
                            battery,
                        )
                    except LLMCallBlocked as exc:
                        print(f"  mutation probes skipped safely: {exc}")
                        drafted_probes = []
                if ((args.caesar_reprobe or args.q25_mode)
                        and req == REQUESTS[0]):
                    existing = {
                        json.dumps(probe, sort_keys=True, default=str)
                        for probe in drafted_probes
                    }
                    extra = [
                        probe for probe in deterministic_caesar_probes(battery)
                        if json.dumps(probe, sort_keys=True, default=str)
                        not in existing
                    ]
                    drafted_probes.extend(extra)
                    print(f"  deterministic Caesar re-probes added: "
                          f"{len(extra)}")
                probes = executable_probe_inputs(
                    scaffold, impl, drafted_probes
                )
                print(f"  mutation probes: {len(probes)}/"
                      f"{len(drafted_probes)} independent in-domain inputs "
                      "execute on the baseline")
                model_want = 1 if args.q25_mode else MUTANTS_WANTED
                model_attempts = 2 if args.q25_mode else MUTANTS_WANTED * 2
                mutants = validated_mutants(
                    scaffold,
                    SLOT,
                    impl,
                    meta["behaviour"] + "\nValid domain: " + meta["domain"],
                    probes,
                    want=model_want,
                    attempts=model_attempts,
                    excluded_inputs=[case["args"] for case in battery],
                ) if probes else []
                if ((args.caesar_reprobe or args.q25_mode)
                        and len(mutants) < MUTANTS_WANTED):
                    mechanical = validated_mechanical_mutants(
                        scaffold,
                        SLOT,
                        impl,
                        probes,
                        want=MUTANTS_WANTED - len(mutants),
                    )
                    mutants.extend(mechanical)
                    print(f"  mechanical mutants added: {len(mechanical)}")
                if mutants:
                    scored = mutation_score(
                        battery, scaffold, SLOT, mutants, values_equal
                    )
                    mutation_rows.append((
                        req,
                        scored["score"],
                        scored["mutants"],
                        scored["survivors"],
                        "",
                    ))
                    mutation_control = (
                        scored["score"] == 1.0
                        and scored["mutants"] >= MUTANTS_WANTED
                        and not disputed
                    )
                    print(f"  mutation score: {scored['killed']}/"
                          f"{scored['mutants']} = {scored['score']:.0%}")
                    for survivor in scored["survivors"]:
                        print("    SURVIVOR: battery misses divergence on "
                              f"{json.dumps(survivor['diverges_on'])[:60]}")
                else:
                    print("  mutation score: unavailable (no independently "
                          "validated mutants)")
                    mutation_rows.append((
                        req, None, 0, [], "no validated mutants"
                    ))

        if args.q25_mode and scored is not None:
            survivor_ids = {id(item) for item in scored["survivors"]}
            killed = [
                mutant for mutant in mutants
                if id(mutant) not in survivor_ids
            ]
            if killed:
                control = killed[0]
                buggy = control["code"]
                d_args = control["diverges_on"]
                real_bug = True
                v_bad = verify(
                    build(scaffold, buggy),
                    functional=fn,
                    vertical=meta["fn"],
                )
                print(
                    "  dossier control selected from a killed, "
                    "execution-validated mutant"
                )
        if v_bad is None:
            print("  !! no release-quality buggy control available")
            results.append((req, v_ok.passed, False, "no killed control"))
            continue
        print_verdict(v_bad)

        # Approval is bound to the exact scaffold/spec/oracle revision. Humans
        # cannot approve a new vertical unless every objective release check
        # below passes first.
        review_material = {
            "request": req,
            "scaffold": scaffold,
            "implementation": impl,
            "buggy_control": buggy,
            "control_witness": d_args,
            "spec": meta,
            "oracle_battery": battery,
        }
        revision = revision_digest(review_material)
        automated_checks = {
            "baseline_passes": v_ok.passed,
            "buggy_control_rejected": not v_bad.passed,
            "control_execution_diverges": bool(d_args) and real_bug,
            "oracle_has_cases": bool(battery),
            "oracle_zero_disputes": not disputed,
            "domain_zero_clarifications": not clarifications,
            "mutation_target_met": mutation_control is True,
        }
        rev = assess(
            vertical=meta["fn"],
            is_new_vertical=True,
            revision=revision,
            automated_checks=automated_checks,
            review_material=review_material,
            disputed_cases=disputed,
            spec_clarifications=clarifications,
        )
        print(f"  review revision: {revision}")
        if rev:
            print("  " + explain(rev).replace("\n", "\n  "))

        if args.mutation_score and mutation_control is not None:
            results.append((
                req,
                v_ok.passed,
                mutation_control,
                True if mutation_control else "mutation target not met",
            ))
        else:
            results.append((req, v_ok.passed, not v_bad.passed, real_bug))

    print(f"\n{'='*66}\n=== auto-generated verticals ===")
    print(f"  {'request':46} {'accepts ok':11} {'catches bug'}")
    for req, ok, caught, real in results:
        note = "" if real is True else f"  ({real})"
        print(f"  {req[:44]:46} {'yes' if ok else 'NO':11} "
              f"{'yes' if caught else 'NO'}{note}")
    good = sum(1 for _, o, c, r in results if o and c and r is True)
    print(f"\n  fully working auto-verticals: {good}/{len(results)}")

    if args.mutation_score:
        print("\n=== auto-generated battery mutation scores ===")
        for req, score, count, survivors, note in mutation_rows:
            label = "n/a" if score is None else f"{score:.0%}"
            suffix = f" ({note})" if note else ""
            print(f"  {req[:44]:46} {label:>5}  "
                  f"({count} validated, {len(survivors)} survived){suffix}")
        total_mutants = sum(row[2] for row in mutation_rows)
        total_survivors = sum(len(row[3]) for row in mutation_rows)
        if total_mutants:
            aggregate = (total_mutants - total_survivors) / total_mutants
            print(f"\n  aggregate: {total_mutants - total_survivors}/"
                  f"{total_mutants} = {aggregate:.0%}")

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
    return 0 if results and good == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
