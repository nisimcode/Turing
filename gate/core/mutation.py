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
import tempfile
from pathlib import Path

from .config import ORACLE_MODEL, get_logger
from .llm import call, extract_code
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

Return ONLY the function in one ```javascript block."""


def _build(scaffold: str, impl: str, slot: str) -> Path:
    p = Path(tempfile.mkdtemp(prefix="gate-mut-")) / "a.html"
    p.write_text(scaffold.replace(slot, impl), encoding="utf-8")
    return p


# Default hook. Verticals with their own hook (window.__wordle, __game2048,
# __tool ...) must pass their own `invoke` -- a JS arrow taking the args array.
# Getting this wrong makes every call throw identically for original AND mutant,
# so nothing ever looks divergent and every mutant is silently discarded.
DEFAULT_INVOKE = "(a) => window.__fn.apply(null, a)"


def _run_many(scaffold: str, impl: str, slot: str, inputs: list,
              invoke: str = DEFAULT_INVOKE) -> list:
    """Evaluate the vertical's hook over many inputs in one page load."""
    with sandboxed_page(_build(scaffold, impl, slot)) as page:
        return page.evaluate(
            """(args) => args.map(a => {
                 try { return JSON.stringify((%s)(a)); }
                 catch (e) { return 'ERR:' + e.message; }
               })""" % invoke, inputs)


def find_divergence(scaffold: str, slot: str, impl: str, mutant: str,
                    inputs: list, invoke: str = DEFAULT_INVOKE
                    ) -> tuple[int, str, str] | None:
    """First input where mutant and original observably disagree, by execution."""
    try:
        a = _run_many(scaffold, impl, slot, inputs, invoke)
        b = _run_many(scaffold, mutant, slot, inputs, invoke)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("divergence search failed: %s", exc)
        return None
    if all(str(x).startswith("ERR:") for x in a):
        log.error("original implementation throws on every probe input -- the "
                  "`invoke` hook is probably wrong (%s); aborting", invoke)
        return None
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x, y
    return None


def validated_mutants(scaffold: str, slot: str, impl: str, behaviour: str,
                      probe_inputs: list, want: int = 5, attempts: int = 10,
                      invoke: str = DEFAULT_INVOKE) -> list[dict]:
    """Generate mutants and keep only those with a demonstrated divergence."""
    kept, tried = [], 0
    while len(kept) < want and tried < attempts:
        tried += 1
        mutant = extract_code(
            call(ORACLE_MODEL, MUTANT_PROMPT.format(
                impl=impl, behaviour=behaviour, i=tried), max_tokens=1400),
            "javascript")
        div = find_divergence(scaffold, slot, impl, mutant, probe_inputs, invoke)
        if div is None:
            log.info("mutant %d discarded: no observable divergence", tried)
            continue
        idx, orig, mut = div
        kept.append({"code": mutant, "diverges_on": probe_inputs[idx],
                     "original": orig, "mutant": mut})
        log.info("mutant %d validated: differs on %s (%s vs %s)",
                 tried, json.dumps(probe_inputs[idx])[:40], orig, mut)
    if tried >= attempts and len(kept) < want:
        log.warning("only %d/%d mutants validated in %d attempts",
                    len(kept), want, tried)
    return kept


def mutation_score(battery: list[dict], scaffold: str, slot: str,
                   mutants: list[dict], compare,
                   invoke: str = DEFAULT_INVOKE) -> dict:
    """Fraction of validated mutants the battery kills (detects)."""
    inputs = [c["args"] for c in battery]
    killed, survivors = 0, []
    for m in mutants:
        got = _run_many(scaffold, m["code"], slot, inputs, invoke)
        detected = any(
            not compare(json.loads(g) if not g.startswith("ERR:") else g,
                        c["expected"])
            for g, c in zip(got, battery))
        if detected:
            killed += 1
        else:
            survivors.append(m)
    return {"mutants": len(mutants), "killed": killed,
            "score": killed / len(mutants) if mutants else None,
            "survivors": survivors}
