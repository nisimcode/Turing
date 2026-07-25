"""Wordle acceptance spec: the oracle + functional checks the gate runs.

This is the game-specific verification layer (Layer 1/2) that plugs into the
generic browser gate. It drives the `window.__wordle` contract and compares the
implementation's coloring against a trusted Python oracle over a battery of
duplicate-letter edge cases.
"""

# duplicate-letter-heavy battery (guess, answer) -- the cases naive impls fail
BATTERY = [
    ("PPPPP", "APPLE"), ("SPEED", "ERASE"), ("ALLOY", "LOLLY"),
    ("ABBEY", "KEBAB"), ("ROBOT", "OTTER"), ("CRANE", "CANAL"),
    ("LEVEL", "EAGLE"), ("APPLE", "PAPER"), ("EERIE", "THERE"),
    ("GEESE", "SIEGE"),
]


def oracle(guess: str, answer: str) -> str:
    """Correct Wordle feedback with proper duplicate-letter accounting."""
    res = ["B"] * 5
    counts = {}
    for c in answer:
        counts[c] = counts.get(c, 0) + 1
    for i in range(5):
        if guess[i] == answer[i]:
            res[i] = "G"
            counts[guess[i]] -= 1
    for i in range(5):
        if res[i] == "B" and counts.get(guess[i], 0) > 0:
            res[i] = "Y"
            counts[guess[i]] -= 1
    return "".join(res)


def functional_checks(page):
    """Drive window.__wordle and verify coloring. Returns list of check dicts."""
    checks = []
    has_hook = page.evaluate(
        "!!(window.__wordle && typeof window.__wordle.guess === 'function'"
        " && typeof window.__wordle.setAnswer === 'function')"
    )
    checks.append({"name": "contract", "ok": bool(has_hook),
                   "detail": "window.__wordle.{setAnswer,guess}"})
    if not has_hook:
        return checks

    mismatches = []
    for guess, answer in BATTERY:
        got = page.evaluate(
            "([g, a]) => { window.__wordle.setAnswer(a);"
            " return window.__wordle.guess(g); }",
            [guess, answer],
        )
        exp = oracle(guess, answer)
        if got != exp:
            mismatches.append(f"{guess}/{answer}: got {got}, expected {exp}")

    ok = not mismatches
    if ok:
        detail = f"all {len(BATTERY)} cases correct"
    else:
        detail = mismatches[0] + (f"  (+{len(mismatches)-1} more)"
                                  if len(mismatches) > 1 else "")
    checks.append({"name": "wordle_logic", "ok": ok, "detail": detail})
    return checks
