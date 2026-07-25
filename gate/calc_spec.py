"""Expression-calculator acceptance spec: hand-verified (expr -> expected) battery.

Harder logic slot, chosen so the cheap tier's pass rate is likely PARTIAL: the
division-truncates-toward-zero rule (-7/2 = -3, not -4) trips naive Math.floor
implementations. Expected values are hand-computed (no Python evaluator to get
wrong).
"""

# (expression, expected integer)  -- semantics pinned in the generation prompt
BATTERY = [
    ("1+2*3", 7),
    ("(1+2)*3", 9),
    ("10/3", 3),
    ("-7/2", -3),        # truncate toward zero (floor would give -4)
    ("7/-2", -3),        # -3.5 -> -3
    ("2*-3+4", -2),      # unary minus
    ("-(3-5)*2", 4),
    ("100/7/2", 7),      # left-assoc: 14 then 7
    ("-10/3", -3),       # -3.33 -> -3 (floor would give -4)
    ("3-(-4)", 7),
    ("2+3*4-6/2", 11),
    ("((2))", 2),
]


def functional_checks(page):
    checks = []
    has_hook = page.evaluate(
        "!!(window.__tool && typeof window.__tool.evaluate === 'function')"
    )
    checks.append({"name": "contract", "ok": bool(has_hook),
                   "detail": "window.__tool.evaluate"})
    if not has_hook:
        return checks

    mism = []
    for expr, exp in BATTERY:
        try:
            got = page.evaluate("(e) => window.__tool.evaluate(e)", expr)
        except Exception as ex:
            mism.append(f"{expr!r}: raised {str(ex)[:40]}")
            continue
        if got != exp:
            mism.append(f"{expr!r}: got {got}, expected {exp}")

    ok = not mism
    detail = (f"all {len(BATTERY)} cases correct" if ok
              else mism[0] + (f"  (+{len(mism)-1} more)" if len(mism) > 1 else ""))
    checks.append({"name": "calc_logic", "ok": ok, "detail": detail})
    return checks
