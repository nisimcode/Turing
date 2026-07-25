"""Validated mutants and mutation scoring (Q22).

Asking a model for "a subtly buggy variant, and where it differs" produced
non-bugs 2 times out of 3: it *predicts* a divergence instead of demonstrating
one. Same failure the whole project keeps circling -- guessing where knowing is
available.

So a mutant is only accepted as a bug once we EXECUTE both versions and observe
an input where they disagree. Mutants that never diverge are discarded, not
counted. That turns a vague "does the gate still catch bugs?" into the standard
metric:

    mutation score = validated mutants the battery kills / validated mutants

A battery that scores 100% kills every observable fault it was shown. A low
score means the battery looks fine but tests too little.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path

from .config import ORACLE_MODEL, get_logger
from .sandbox import sandboxed_page

log = get_logger("gate.mutation")

MUTANT_PROMPT = """Here is a correct JavaScript function:

```javascript
{impl}
```

Behaviour: {behaviour}

Produce a SUBTLY buggy variant -- same name and signature, correct on typical
inputs, wrong on some input inside the valid domain. It should look plausible;
the kind of mistake that survives a casual review. Vary the KIND of fault
(off-by-one, wrong boundary, dropped edge case, wrong operator, mishandled
duplicate/empty) -- variant #{i}.

Return TWO fenced blocks:
1. ```javascript -- the subtly buggy function
2. ```json -- {{"differs_on": [<args>]}} with one argument list INSIDE the
   valid domain where you predict the mutant differs from the original.

The prediction is not trusted: both functions will be executed on that input,
and the mutant is discarded unless a real behavioural difference is observed."""


def _build(scaffold: str, impl: str, slot: str) -> Path:
    p = Path(tempfile.mkdtemp(prefix="gate-mut-")) / "a.html"
    p.write_text(scaffold.replace(slot, impl), encoding="utf-8")
    return p


# Default hook. Verticals with their own hook (window.__wordle, __game2048,
# __tool ...) must pass their own `invoke` -- a JS arrow taking the args array.
# Getting this wrong makes every call throw identically for original AND mutant,
# so nothing ever looks divergent and every mutant is silently discarded.
DEFAULT_INVOKE = "(a) => window.__fn.apply(null, a)"

MECHANICAL_RULES = (
    (" % 26", " % 25", "wrong modulus"),
    ("c <= 90", "c < 90", "exclude uppercase boundary"),
    ("c >= 65", "c > 65", "exclude uppercase boundary"),
    ("c <= 122", "c < 122", "exclude lowercase boundary"),
    ("c >= 97", "c > 97", "exclude lowercase boundary"),
    ("i < text.length", "i < text.length - 1", "drop final character"),
    ("result += text[i]", "result += ''", "drop passthrough characters"),
    ("c - 65", "c - 64", "uppercase offset"),
    ("c - 97", "c - 96", "lowercase offset"),
    ("+ normalizedShift", "- normalizedShift", "reverse shift direction"),
)


def generic_source_mutants(impl: str):
    """Yield plausible one-site mutations for arbitrary JavaScript functions.

    These are only *candidates*. `validated_mechanical_mutants` executes every
    candidate against the baseline on independent probes and discards syntax
    errors, inert edits, and changes that affect no in-domain behavior.
    """
    replacements = {
        "<=": "<",
        ">=": ">",
        "===": "!==",
        "!==": "===",
        ".toLowerCase()": ".toUpperCase()",
        ".toUpperCase()": ".toLowerCase()",
        ".trim()": "",
    }
    for old, new in replacements.items():
        for match in re.finditer(re.escape(old), impl):
            yield (
                impl[:match.start()] + new + impl[match.end():],
                f"{old} -> {new}",
            )

    # Regex mutations cover validators and formatters that have no arithmetic
    # boundaries. Each candidate is still execution-validated before counting.
    for old, new, label in (
        ("/^", "/", "remove regex start anchor"),
        ("$/", "/", "remove regex end anchor"),
        ("/g", "/", "remove regex global flag"),
    ):
        for match in re.finditer(re.escape(old), impl):
            yield (
                impl[:match.start()] + new + impl[match.end():],
                label,
            )
    for match in re.finditer(r"\.test\(([^()\n]*)\)", impl):
        yield (
            impl[:match.end()] + " === false" + impl[match.end():],
            "invert regex predicate",
        )

    # Numeric boundary/off-by-one mutations work across converters, validators,
    # rankings and range-based business rules. Avoid mutating 0/1 first because
    # those often create only catastrophic rather than subtle controls.
    for match in re.finditer(r"(?<![\w.])(\d+)(?![\w.])", impl):
        value = int(match.group(1))
        deltas = (-1, 1, -2, 2) if value > 2 else (1, 2)
        for delta in deltas:
            changed = str(max(0, value + delta))
            yield (
                impl[:match.start()] + changed + impl[match.end():],
                f"constant {value} -> {changed}",
            )

    # Single arithmetic operator swaps. The guards avoid ++, --, comments,
    # arrow functions and compound assignments; execution validation is the
    # final authority on whether the resulting program is usable.
    swaps = {"+": "-", "-": "+", "*": "+", "/": "*", "%": "/"}
    for match in re.finditer(r"(?<![+\-*/%=<>!])([+\-*/%])(?![+\-*/%=<>])",
                             impl):
        old = match.group(1)
        new = swaps[old]
        yield (
            impl[:match.start()] + new + impl[match.end():],
            f"operator {old} -> {new}",
        )


def run_many(scaffold: str, impl: str, slot: str, inputs: list,
             invoke: str = DEFAULT_INVOKE) -> list:
    """Evaluate the vertical's hook over many inputs in one page load."""
    artifact = _build(scaffold, impl, slot)
    try:
        with sandboxed_page(artifact) as page:
            return page.evaluate(
                """(args) => args.map(a => {
                     try { return JSON.stringify((%s)(a)); }
                     catch (e) { return 'ERR:' + e.message; }
                   })""" % invoke, inputs)
    finally:
        shutil.rmtree(artifact.parent, ignore_errors=True)


# Compatibility aliases for archived/research callers that imported internals.
_generic_source_mutants = generic_source_mutants
_run_many = run_many


def find_divergence(scaffold: str, slot: str, impl: str, mutant: str,
                    inputs: list, invoke: str = DEFAULT_INVOKE
                    ) -> tuple[int, str, str] | None:
    """First input where mutant and original observably disagree, by execution."""
    try:
        a = run_many(scaffold, impl, slot, inputs, invoke)
        b = run_many(scaffold, mutant, slot, inputs, invoke)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("divergence search failed: %s", exc)
        return None
    if all(str(x).startswith("ERR:") for x in a):
        log.error("original implementation throws on every probe input -- the "
                  "`invoke` hook is probably wrong (%s); aborting", invoke)
        return None
    for i, (x, y) in enumerate(zip(a, b)):
        # A throwing baseline means this is not a usable witness for a fault in
        # the mutant, even if the generated domain description was imperfect.
        if str(x).startswith("ERR:"):
            continue
        if x != y:
            return i, x, y
    return None


def validated_mutants(scaffold: str, slot: str, impl: str, behaviour: str,
                      probe_inputs: list, want: int = 5, attempts: int = 10,
                      invoke: str = DEFAULT_INVOKE,
                      excluded_inputs: list | None = None) -> list[dict]:
    """Generate mutants and keep only those with a demonstrated divergence."""
    # Keep deterministic mechanical mutation usable in the public, no-AI
    # dependency set. The optional Anthropic SDK is needed only on this paid
    # generation path.
    from .llm import call, extract_block, extract_code

    kept, tried = [], 0
    excluded = {
        json.dumps(args, sort_keys=True, default=str)
        for args in (excluded_inputs or [])
    }
    while len(kept) < want and tried < attempts:
        tried += 1
        try:
            raw = call(ORACLE_MODEL, MUTANT_PROMPT.format(
                impl=impl, behaviour=behaviour, i=tried), max_tokens=1600)
        except RuntimeError as exc:
            if not any(marker in str(exc) for marker in (
                "paid-call budget exhausted",
                "cache-only mode refused",
            )):
                raise
            log.warning(
                "mutation generation stopped before a new paid call; scoring "
                "the %d independently validated mutant(s) already available",
                len(kept),
            )
            break
        mutant = extract_code(raw, "javascript")
        witness_block = extract_block(raw, "json")
        try:
            witness = json.loads(witness_block)["differs_on"]
            assert isinstance(witness, list)
        except (AssertionError, KeyError, TypeError, json.JSONDecodeError):
            witness = None

        inputs = list(probe_inputs)
        if witness is not None:
            key = json.dumps(witness, sort_keys=True, default=str)
            if key not in excluded:
                inputs.insert(0, witness)
            else:
                log.info("mutant %d witness overlaps the scored battery; "
                         "ignoring it", tried)

        div = find_divergence(scaffold, slot, impl, mutant, inputs, invoke)
        if div is None:
            log.info("mutant %d discarded: no observable divergence", tried)
            continue
        idx, orig, mut = div
        kept.append({"code": mutant, "diverges_on": inputs[idx],
                     "original": orig, "mutant": mut})
        log.info("mutant %d validated: differs on %s (%s vs %s)",
                 tried, json.dumps(inputs[idx])[:40], orig, mut)
    if tried >= attempts and len(kept) < want:
        log.warning("only %d/%d mutants validated in %d attempts",
                    len(kept), want, tried)
    return kept


def validated_mechanical_mutants(scaffold: str, slot: str, impl: str,
                                 probe_inputs: list, want: int = 5,
                                 invoke: str = DEFAULT_INVOKE) -> list[dict]:
    """Execution-validate standard local source mutations with zero LLM calls."""
    candidates = []
    seen = {impl}
    for old, new, label in MECHANICAL_RULES:
        start = 0
        while True:
            index = impl.find(old, start)
            if index < 0:
                break
            mutant = impl[:index] + new + impl[index + len(old):]
            start = index + len(old)
            if mutant not in seen:
                seen.add(mutant)
                candidates.append((mutant, label))
    for mutant, label in generic_source_mutants(impl):
        if mutant not in seen:
            seen.add(mutant)
            candidates.append((mutant, f"generic: {label}"))

    kept = []
    for mutant, label in candidates:
        divergence = find_divergence(
            scaffold, slot, impl, mutant, probe_inputs, invoke
        )
        if divergence is None:
            continue
        index, original, changed = divergence
        kept.append({
            "code": mutant,
            "kind": f"mechanical: {label}",
            "diverges_on": probe_inputs[index],
            "original": original,
            "mutant": changed,
        })
        log.info(
            "mechanical mutant validated (%s): differs on %s (%s vs %s)",
            label,
            json.dumps(probe_inputs[index])[:40],
            original,
            changed,
        )
        if len(kept) >= want:
            break
    return kept


def mutation_score(battery: list[dict], scaffold: str, slot: str,
                   mutants: list[dict], compare,
                   invoke: str = DEFAULT_INVOKE) -> dict:
    """Fraction of validated mutants the battery kills (detects)."""
    def decode(value):
        # JSON.stringify(undefined) crosses the Playwright boundary as None.
        # A mutant returning undefined is a valid observable fault, not a
        # reason for the scorer itself to crash.
        if not isinstance(value, str) or value.startswith("ERR:"):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    inputs = [c["args"] for c in battery]
    killed, survivors = 0, []
    for m in mutants:
        got = run_many(scaffold, m["code"], slot, inputs, invoke)
        detected = any(
            not compare(decode(g), c["expected"])
            for g, c in zip(got, battery))
        if detected:
            killed += 1
        else:
            survivors.append(m)
    return {"mutants": len(mutants), "killed": killed,
            "score": killed / len(mutants) if mutants else None,
            "survivors": survivors}
