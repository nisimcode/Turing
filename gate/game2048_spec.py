"""2048 acceptance spec: oracle + functional checks for the slideRow logic slot.

Second vertical, same pattern as wordle_spec.py -- proves the gate approach
generalizes to a different kind of logic (array transform, not string matching).
"""

# (row -> expected) battery; 0 = empty. Covers the merge-once edge cases.
BATTERY = [
    [2, 2, 2, 2],   # -> [4,4,0,0]  (NOT [8,...])
    [2, 2, 4, 0],   # -> [4,4,0,0]
    [4, 4, 4, 4],   # -> [8,8,0,0]
    [2, 0, 2, 0],   # -> [4,0,0,0]
    [0, 0, 0, 2],   # -> [2,0,0,0]
    [2, 4, 2, 4],   # -> [2,4,2,4]  (no merges)
    [4, 4, 8, 0],   # -> [8,8,0,0]  (merged 8 does NOT merge with existing 8)
    [2, 2, 2, 0],   # -> [4,2,0,0]
    [8, 8, 8, 8],   # -> [16,16,0,0]
    [0, 2, 2, 2],   # -> [4,2,0,0]
]


def slide_left(row):
    """Correct 2048 single-row slide-left + merge-once."""
    nums = [x for x in row if x != 0]
    out = []
    i = 0
    while i < len(nums):
        if i + 1 < len(nums) and nums[i] == nums[i + 1]:
            out.append(nums[i] * 2)
            i += 2
        else:
            out.append(nums[i])
            i += 1
    return out + [0] * (4 - len(out))


def functional_checks(page):
    checks = []
    has_hook = page.evaluate(
        "!!(window.__game2048 && typeof window.__game2048.slide === 'function')"
    )
    checks.append({"name": "contract", "ok": bool(has_hook),
                   "detail": "window.__game2048.slide"})
    if not has_hook:
        return checks

    mism = []
    for row in BATTERY:
        got = page.evaluate("(r) => window.__game2048.slide(r)", row)
        got = list(got) if got is not None else None
        exp = slide_left(row)
        if got != exp:
            mism.append(f"{row}: got {got}, expected {exp}")

    ok = not mism
    detail = (f"all {len(BATTERY)} cases correct" if ok
              else mism[0] + (f"  (+{len(mism)-1} more)" if len(mism) > 1 else ""))
    checks.append({"name": "game2048_logic", "ok": ok, "detail": detail})
    return checks
