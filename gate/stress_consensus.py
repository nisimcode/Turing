"""Q16: try to BREAK oracle consensus on purpose (correlated / unanimous-wrong).

Consensus can only catch UNCORRELATED errors. All these models share training
data, so the fatal scenario is all oracles being confidently, identically wrong.
Canonical tasks (Luhn, Roman, competition ranking) are where that's least likely
-- so this file uses specs that deliberately CONTRADICT the famous convention:

  * additive Roman numerals    (4 = IIII, not IV)
  * Luhn doubling from the LEFT
  * MODIFIED competition ranking (1,3,3,4 -- ties take the highest rank)
  * leap years with NO 400-year exception (1900 IS a leap year here)
  * round-half-to-EVEN to the nearest ten (25 -> 20)

Each rule is stated explicitly in the prompt, so a wrong answer means the model
overrode a clear spec with its prior -- which is exactly how a real customer's
non-standard business rules would get silently mis-verified.

    uv run --with anthropic python stress_consensus.py
"""

import json
from collections import Counter

from oracle_consensus import VOTERS, ask_oracle, key, _cost


# ---------------- ground truth (deliberately non-canonical) ----------------
def luhn_left(s):
    total = 0
    for i, ch in enumerate(s):          # i=0 is the 1st (leftmost) position
        d = ord(ch) - 48
        if i % 2 == 0:                  # double 1st, 3rd, 5th ... from the LEFT
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def to_roman_additive(n):
    vals = [1000, 500, 100, 50, 10, 5, 1]
    syms = ["M", "D", "C", "L", "X", "V", "I"]
    out = ""
    for v, s in zip(vals, syms):
        while n >= v:
            out += s
            n -= v
    return out


def rank_modified(scores):
    srt = sorted(scores, reverse=True)
    rev = srt[::-1]
    return [len(srt) - rev.index(s) for s in scores]


def is_leap_custom(y):
    return y % 4 == 0                   # no 100/400 exceptions at all


def round_half_even_ten(n):
    q, r = divmod(n, 10)
    if r > 5:
        q += 1
    elif r == 5 and q % 2 == 1:
        q += 1
    return q * 10


TASKS = [
    {
        "id": "roman_additive",
        "desc": "Convert an integer (1..3999) to a Roman numeral using ADDITIVE "
                "notation ONLY. This system does NOT use subtractive forms: "
                "4 is IIII (not IV), 9 is VIIII (not IX), 40 is XXXX, 90 is "
                "LXXXX, 400 is CCCC, 900 is DCCCC. Build the numeral by "
                "repeatedly taking the largest of M(1000), D(500), C(100), "
                "L(50), X(10), V(5), I(1) that fits.",
        "signature": "function toRomanAdditive(n) -> uppercase string",
        "inputs": [4, 9, 14, 40, 90, 400, 900, 1994, 3999, 8, 49, 2024],
        "truth": to_roman_additive,
    },
    {
        "id": "luhn_left",
        "desc": "A checksum like Luhn but MIRRORED: double the digits at ODD "
                "positions counting from the LEFT (the 1st, 3rd, 5th, ... "
                "characters of the string), NOT from the right. If a doubled "
                "value exceeds 9, subtract 9. Sum all resulting digits; the "
                "number is valid if the sum is divisible by 10.",
        "signature": "function luhnLeft(cardNumber) -> boolean  "
                     "// string of digits",
        "inputs": ["4532015112830366", "4111111111111111", "18", "10", "1234",
                   "0000", "12345678", "79927398713", "55555555555555", "9"],
        "truth": luhn_left,
    },
    {
        "id": "rank_modified",
        "desc": "Rank players by score (higher is better) using MODIFIED "
                "competition ranking: every member of a tie group receives the "
                "HIGHEST (numerically largest) rank of that group. So "
                "[100,90,90,80] -> [1,3,3,4]  (NOT [1,2,2,4]). Return ranks in "
                "the input order.",
        "signature": "function rankModified(scores) -> array of numbers",
        "inputs": [[100, 90, 90, 80], [50], [10, 10, 10], [5, 3, 1],
                   [7, 7, 5, 5, 5, 1], [1, 1, 2, 2], [3, 1, 3]],
        "truth": rank_modified,
    },
    {
        "id": "leap_custom",
        "desc": "In THIS calendar system a year is a leap year if and only if it "
                "is divisible by 4. There is NO 100-year exception and NO "
                "400-year exception -- so 1900 IS a leap year here, and 2100 IS "
                "a leap year here.",
        "signature": "function isLeapCustom(year) -> boolean",
        "inputs": [1900, 2000, 2100, 2024, 2023, 1800, 4, 2200, 1996, 2001],
        "truth": is_leap_custom,
    },
    {
        "id": "round_half_even",
        "desc": "Round a non-negative integer to the nearest multiple of 10. When "
                "the value is exactly halfway (it ends in 5), round to the EVEN "
                "multiple of ten (banker's rounding). So 15 -> 20, 25 -> 20, "
                "35 -> 40, 45 -> 40, 55 -> 60.",
        "signature": "function roundToTen(n) -> number",
        "inputs": [15, 25, 35, 45, 55, 5, 10, 14, 16, 105, 0, 95],
        "truth": round_half_even_ten,
    },
]


def main():
    per_correct, per_total = Counter(), Counter()
    unanimous_wrong, flagged_wrong, total_wrong, flagged = [], 0, 0, 0
    cons_correct = cons_total = 0
    cheap_correct = 0

    for task in TASKS:
        truths = [task["truth"](x) for x in task["inputs"]]
        votes = {name: ask_oracle(model, task) for name, model in VOTERS}
        print(f"\n=== {task['id']} ===")
        for i, inp in enumerate(task["inputs"]):
            truth = truths[i]
            vals = [votes[n][i] for n, _ in VOTERS]
            for (name, _), v in zip(VOTERS, vals):
                per_total[name] += 1
                if key(v) == key(truth):
                    per_correct[name] += 1

            tally = Counter(key(v) for v in vals)
            top, _ = tally.most_common(1)[0]
            disagree = len(tally) > 1
            n_wrong = sum(1 for v in vals if key(v) != key(truth))
            total_wrong += n_wrong
            cons_total += 1
            cons_ok = top == key(truth)
            cons_correct += 1 if cons_ok else 0

            cheap = [votes[n][i] for n in ("haiku#1", "haiku#2", "haiku#3")]
            ctop, _ = Counter(key(v) for v in cheap).most_common(1)[0]
            cheap_correct += 1 if ctop == key(truth) else 0

            if disagree:
                flagged += 1
                flagged_wrong += n_wrong
            elif n_wrong:
                unanimous_wrong.append((task["id"], inp, vals[0], truth))

            if n_wrong:
                marks = " ".join(f"{n}={'ok' if key(v) == key(truth) else 'X'}"
                                 for (n, _), v in zip(VOTERS, vals))
                tag = "DISAGREE" if disagree else "UNANIMOUS-WRONG"
                print(f"  {json.dumps(inp)[:26]:28} truth={json.dumps(truth)[:18]:20}"
                      f" {tag:16} {marks}")

    print("\n=== per-oracle accuracy (adversarial specs) ===")
    for name, _ in VOTERS:
        c, t = per_correct[name], per_total[name]
        print(f"  {name:9} {c}/{t}  ({100*c/t:.0f}%)")

    print("\n=== the Q16 question: does consensus survive? ===")
    print(f"  inputs flagged by disagreement:  {flagged}/{cons_total}")
    print(f"  wrong values on flagged inputs:  {flagged_wrong}/{total_wrong}")
    print(f"  UNANIMOUS-WRONG (undetectable):  {len(unanimous_wrong)}")
    for tid, inp, got, truth in unanimous_wrong:
        print(f"     {tid}: {json.dumps(inp)} -> ALL said {got!r}, truth {truth!r}")

    print("\n=== consensus vs single oracle ===")
    print(f"  5-oracle majority: {cons_correct}/{cons_total}")
    print(f"  3x Haiku majority: {cheap_correct}/{cons_total}")
    print(f"  1x Opus alone:     {per_correct['opus']}/{per_total['opus']}")
    print(f"  cost: {dict((k.split('-')[1], round(v,4)) for k, v in _cost.items())}")

    print("\n=== read ===")
    if unanimous_wrong:
        print(f"  BROKEN: {len(unanimous_wrong)} input(s) where every oracle agreed on a")
        print("  WRONG value. Consensus cannot see correlated failure. Auto-generated")
        print("  gates on non-standard business rules need a human spot-check, or a")
        print("  differential check (oracle vs an independently-written reference).")
    else:
        print("  Consensus held even against specs that fight the training prior.")


if __name__ == "__main__":
    main()
