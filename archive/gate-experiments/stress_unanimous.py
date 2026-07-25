"""ARCHIVED EXPERIMENT: search for unanimous-wrong oracle cases.

Consensus survived Q16 only because at least one strong model always resisted the
training prior, which is what produced the disagreement signal. If a spec is
strong-prior enough that EVERY tier reverts, all oracles agree on a wrong value
and the gate is blind and confident -- the fatal case.

To maximize the chance of that, these specs fight very deeply held priors AND
state the deviation PLAINLY ONCE (no capitals, no "NOT", no repetition) -- unlike
stress_consensus.py, which emphasized deviations heavily. That is both a harder
test and closer to how a real customer writes a spec.

    uv run --with anthropic python stress_unanimous.py
"""

import json
from collections import Counter

from oracle_consensus import VOTERS, ask_oracle, key, _cost


# ---------------- ground truth ----------------
def fizzbuzz_swapped(n):
    out = []
    for i in range(1, n + 1):
        if i % 15 == 0:
            out.append("BuzzFizz")
        elif i % 3 == 0:
            out.append("Buzz")
        elif i % 5 == 0:
            out.append("Fizz")
        else:
            out.append(str(i))
    return out


def sort_desc_ascending(arr):
    return sorted(arr)


def is_even_zero_odd(n):
    if n == 0:
        return False
    return n % 2 == 0


def count_vowels_no_e(s):
    return sum(1 for ch in s.lower() if ch in "aiouy")


def reverse_tail(s):
    return s[0] + s[:0:-1] if s else s


TASKS = [
    {
        "id": "fizzbuzz_swapped",
        "desc": "Returns an array of strings for the integers 1 through n. If a "
                "number is a multiple of 3, the entry is 'Buzz'. If it is a "
                "multiple of 5, the entry is 'Fizz'. If it is a multiple of both, "
                "the entry is 'BuzzFizz'. Otherwise the entry is the number as a "
                "string.",
        "signature": "function fizzBuzz(n) -> array of strings",
        "inputs": [5, 15, 20, 3, 10],
        "truth": fizzbuzz_swapped,
    },
    {
        "id": "sortDesc_ascending",
        "desc": "Returns the array of numbers sorted in ascending order. The "
                "function name is historical and its behaviour should not be "
                "changed.",
        "signature": "function sortDesc(numbers) -> array of numbers",
        "inputs": [[3, 1, 2], [5, 5, 1], [10, -2, 7, 0], [9, 8, 7, 6, 5], [1],
                   [2, 2, 2]],
        "truth": sort_desc_ascending,
    },
    {
        "id": "isEven_zero_odd",
        "desc": "Returns whether the integer n is even. In this system zero is "
                "treated as odd.",
        "signature": "function isEven(n) -> boolean",
        "inputs": [0, 1, 2, -4, 7, 100, -1, 10],
        "truth": is_even_zero_odd,
    },
    {
        "id": "countVowels_no_e",
        "desc": "Counts the vowels in a string, case-insensitively. The vowels in "
                "this system are a, i, o, u and y. The letter e is a consonant "
                "here.",
        "signature": "function countVowels(s) -> number",
        "inputs": ["hello", "system", "beautiful", "eee", "rhythm", "AEIOUY",
                   "queue"],
        "truth": count_vowels_no_e,
    },
    {
        "id": "reverseTail",
        "desc": "Reverses the characters of the string except the first "
                "character, which stays in position 1.",
        "signature": "function reverseTail(s) -> string",
        "inputs": ["abcdef", "hello", "ab", "a", "racecar", "12345"],
        "truth": reverse_tail,
    },
]


def main():
    per_correct, per_total = Counter(), Counter()
    unanimous_wrong, flagged, flagged_wrong, total_wrong = [], 0, 0, 0
    cons_total = 0
    strong_correct = 0   # inputs where sonnet OR opus was right

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
            disagree = len(tally) > 1
            n_wrong = sum(1 for v in vals if key(v) != key(truth))
            total_wrong += n_wrong
            cons_total += 1
            if key(votes["sonnet"][i]) == key(truth) or key(votes["opus"][i]) == key(truth):
                strong_correct += 1

            if disagree:
                flagged += 1
                flagged_wrong += n_wrong
            elif n_wrong:
                unanimous_wrong.append((task["id"], inp, vals[0], truth))

            if n_wrong:
                marks = " ".join(f"{n}={'ok' if key(v) == key(truth) else 'X'}"
                                 for (n, _), v in zip(VOTERS, vals))
                tag = "disagree" if disagree else "UNANIMOUS-WRONG"
                print(f"  {json.dumps(inp)[:24]:26} {tag:16} {marks}")

    print("\n=== per-oracle accuracy (plainly-stated deviations) ===")
    for name, _ in VOTERS:
        c, t = per_correct[name], per_total[name]
        print(f"  {name:9} {c}/{t}  ({100*c/t:.0f}%)")

    print("\n=== Q17: did unanimity break? ===")
    print(f"  total inputs:                    {cons_total}")
    print(f"  flagged by disagreement:         {flagged}")
    print(f"  wrong values on flagged inputs:  {flagged_wrong}/{total_wrong}")
    print(f"  UNANIMOUS-WRONG (blind spot):    {len(unanimous_wrong)}")
    for tid, inp, got, truth in unanimous_wrong:
        print(f"     {tid}: {json.dumps(inp)}")
        print(f"        all oracles said : {json.dumps(got)[:90]}")
        print(f"        truth            : {json.dumps(truth)[:90]}")
    print(f"  inputs where a STRONG tier was right: {strong_correct}/{cons_total}")
    print(f"  cost: {dict((k.split('-')[1], round(v, 4)) for k, v in _cost.items())}")

    print("\n=== read ===")
    if unanimous_wrong:
        print("  BLIND SPOT CONFIRMED: every oracle agreed on a wrong value.")
        print("  Consensus cannot detect this. Auto-generated gates therefore need")
        print("  a human spot-check when a vertical's spec deviates from convention")
        print("  -- unanimity is NOT proof of correctness.")
    else:
        print("  Unanimity held again: no case where all tiers reverted together.")
        print("  Consensus + escalate-on-disagreement survives even plainly-stated,")
        print("  strong-prior deviations (still not a guarantee -- absence of")
        print("  evidence at this n).")


if __name__ == "__main__":
    main()
