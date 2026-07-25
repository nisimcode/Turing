"""Bill-splitter acceptance spec: oracle + functional checks for the splitBill slot.

Third vertical, NON-GAME (Q13a). Same pattern as the game specs. The rounding +
remainder-distribution rules are pinned exactly so oracle and model agree.
"""

# (subtotalCents, tipPercent, people)
BATTERY = [
    (1000, 15, 3),   # tip 150, total 1150 -> [384,383,383]
    (1000, 0, 3),    # -> [334,333,333]
    (1005, 15, 4),   # tip 151, total 1156 -> [289,289,289,289]
    (1000, 20, 1),   # -> [1200]
    (999, 10, 2),    # tip 100, total 1099 -> [550,549]
    (2500, 18, 7),   # tip 450, total 2950 -> [422,422,422,421,421,421,421]
    (100, 15, 3),    # tip 15, total 115 -> [39,38,38]
    (0, 15, 3),      # -> [0,0,0]
]


def split_bill(subtotal, tip_percent, people):
    """Tip = round-half-up of subtotal*tip%/100 (in cents). Total split into
    integer-cent shares summing EXACTLY to total; first `remainder` shares +1."""
    tip = (subtotal * tip_percent + 50) // 100
    total = subtotal + tip
    base = total // people
    rem = total - base * people
    return [base + (1 if i < rem else 0) for i in range(people)]


def functional_checks(page):
    checks = []
    has_hook = page.evaluate(
        "!!(window.__tool && typeof window.__tool.split === 'function')"
    )
    checks.append({"name": "contract", "ok": bool(has_hook),
                   "detail": "window.__tool.split"})
    if not has_hook:
        return checks

    mism = []
    for subtotal, tip, people in BATTERY:
        got = page.evaluate("(a) => window.__tool.split(a[0], a[1], a[2])",
                            [subtotal, tip, people])
        got = list(got) if got is not None else None
        exp = split_bill(subtotal, tip, people)
        if got != exp:
            mism.append(f"({subtotal},{tip},{people}): got {got}, expected {exp}")

    ok = not mism
    detail = (f"all {len(BATTERY)} cases correct" if ok
              else mism[0] + (f"  (+{len(mism)-1} more)" if len(mism) > 1 else ""))
    checks.append({"name": "billsplit_logic", "ok": ok, "detail": detail})
    return checks
