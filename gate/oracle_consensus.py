"""Q15: can we detect a BAD ORACLE without ground truth?

In production a wrong oracle is invisible: it looks exactly like bad code
(correct code "fails" -> needless escalation -> good work rejected). The only
defense available without a reference is cross-checking oracles against each
other.

Experiment: pin a fixed input set per task (including the exact cases Haiku got
wrong in auto_gate.py). Ask 5 INDEPENDENT oracles for the expected values:
3x Haiku, 1x Sonnet, 1x Opus. We hold real ground truth in Python.

Measured:
  * per-oracle accuracy vs truth
  * DETECTION: do wrong values coincide with cross-oracle disagreement?
  * UNANIMOUS-WRONG: inputs where all 5 agreed on a WRONG value -- correlated
    failure, undetectable by consensus. The dangerous case.
  * consensus (majority) accuracy vs single-model accuracy
  * economics: 3x cheap oracles (majority) vs 1x expensive oracle

    uv run --with anthropic python oracle_consensus.py
"""

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import anthropic

HERE = Path(__file__).resolve().parent
PRICING = {"claude-haiku-4-5": (1.0, 5.0), "claude-sonnet-5": (3.0, 15.0),
           "claude-opus-4-8": (5.0, 25.0)}
# 5 independent oracles (odd count avoids majority ties)
VOTERS = [("haiku#1", "claude-haiku-4-5"), ("haiku#2", "claude-haiku-4-5"),
          ("haiku#3", "claude-haiku-4-5"), ("sonnet", "claude-sonnet-5"),
          ("opus", "claude-opus-4-8")]


# ---------------- ground truth (hand-verified reference implementations) -------
def luhn_valid(s):
    total, dbl = 0, False
    for ch in reversed(s):
        d = ord(ch) - 48
        if dbl:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        dbl = not dbl
    return total % 10 == 0


def rank_scores(scores):
    srt = sorted(scores, reverse=True)
    return [srt.index(s) + 1 for s in scores]


def to_roman(n):
    vals = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    out = ""
    for v, s in zip(vals, syms):
        while n >= v:
            out += s
            n -= v
    return out


TASKS = [
    {
        "id": "luhn",
        "desc": "Validate a credit card number with the Luhn algorithm: starting "
                "from the rightmost digit moving left, double every second digit; "
                "if a doubled value exceeds 9 subtract 9; the number is valid if "
                "the total sum is divisible by 10.",
        "signature": "function luhnValid(cardNumber) -> boolean  "
                     "// cardNumber: string of digits",
        "inputs": ["4532015112830366", "10", "00", "0", "18", "79927398713",
                   "79927398710", "4111111111111111", "1234567812345678", "59"],
        "truth": lambda x: luhn_valid(x),
    },
    {
        "id": "ranking",
        "desc": "Rank players by score (higher is better) using STANDARD "
                "COMPETITION RANKING: tied entries share a rank and the next rank "
                "skips, e.g. [100,90,90,80] -> [1,2,2,4]. Return ranks in the same "
                "order as the input.",
        "signature": "function rankScores(scores) -> array of numbers",
        "inputs": [[100, 90, 90, 80], [100, 90, 80, 90, 100, 80], [50],
                   [10, 10, 10], [5, 3, 1], [1, 2, 3], [7, 7, 5, 5, 5, 1],
                   [0, -1, 0]],
        "truth": lambda x: rank_scores(x),
    },
    {
        "id": "roman",
        "desc": "Convert an integer (1..3999) to a Roman numeral using standard "
                "subtractive notation (4=IV, 9=IX, 40=XL, 90=XC, 400=CD, 900=CM).",
        "signature": "function toRoman(n) -> uppercase string",
        "inputs": [1, 4, 9, 14, 40, 90, 400, 900, 1994, 3999, 2024, 58],
        "truth": lambda x: to_roman(x),
    },
]

PROMPT = """You are producing the TEST ORACLE for this function:

  {sig}

Behavior: {desc}

For EACH input below, give the exact correct return value. Output JSON only, in a
single ```json code block, as:

  {{"expected": [v1, v2, ...]}}

with exactly {n} values in the SAME ORDER as the inputs. Be precise: a wrong
value here makes the test suite reject correct code.

Inputs (in order):
{inputs}"""


def load_api_key() -> str:
    for var in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    for env_path in (HERE / ".env", HERE.parent / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(("CLAUDE_API_KEY=", "ANTHROPIC_API_KEY=")):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("No API key found (set CLAUDE_API_KEY in E:\\Turing\\.env).")


client = anthropic.Anthropic(api_key=load_api_key())
_cost = Counter()


def ask_oracle(model, task):
    prompt = PROMPT.format(
        sig=task["signature"], desc=task["desc"], n=len(task["inputs"]),
        inputs="\n".join(f"  {i+1}. {json.dumps(x)}"
                         for i, x in enumerate(task["inputs"])),
    )
    resp = client.messages.create(
        model=model, max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    ip, op = PRICING[model]
    _cost[model] += (resp.usage.input_tokens / 1e6 * ip
                     + resp.usage.output_tokens / 1e6 * op)
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    try:
        vals = json.loads(m.group(1) if m else text).get("expected", [])
    except (json.JSONDecodeError, AttributeError):
        return [None] * len(task["inputs"])
    if len(vals) != len(task["inputs"]):
        vals = (vals + [None] * len(task["inputs"]))[:len(task["inputs"])]
    return vals


def key(v):
    return json.dumps(v, sort_keys=True)


def main():
    per_voter_correct = Counter()
    per_voter_total = Counter()
    flagged_wrong = flagged_total = 0
    unanimous_wrong = []
    consensus_correct = consensus_total = 0
    cheap_correct = 0

    for task in TASKS:
        truths = [task["truth"](x) for x in task["inputs"]]
        votes = {name: ask_oracle(model, task) for name, model in VOTERS}

        print(f"\n=== {task['id']} ({len(task['inputs'])} inputs) ===")
        for i, inp in enumerate(task["inputs"]):
            truth = truths[i]
            vals = [votes[name][i] for name, _ in VOTERS]
            for (name, _), v in zip(VOTERS, vals):
                per_voter_total[name] += 1
                if key(v) == key(truth):
                    per_voter_correct[name] += 1

            tally = Counter(key(v) for v in vals)
            top, cnt = tally.most_common(1)[0]
            disagree = len(tally) > 1
            cons_ok = top == key(truth)
            consensus_total += 1
            consensus_correct += 1 if cons_ok else 0

            cheap_vals = [votes[n][i] for n in ("haiku#1", "haiku#2", "haiku#3")]
            ctop, _ = Counter(key(v) for v in cheap_vals).most_common(1)[0]
            cheap_correct += 1 if ctop == key(truth) else 0

            n_wrong = sum(1 for v in vals if key(v) != key(truth))
            if disagree:
                flagged_total += 1
                flagged_wrong += n_wrong
            elif n_wrong:  # unanimous AND wrong -> undetectable
                unanimous_wrong.append((task["id"], inp, vals[0], truth))

            if disagree or n_wrong:
                marks = " ".join(
                    f"{name}={'ok' if key(v) == key(truth) else 'X'}"
                    for (name, _), v in zip(VOTERS, vals))
                print(f"  input {json.dumps(inp)[:34]:36} "
                      f"{'DISAGREE' if disagree else 'unanimous':10} "
                      f"consensus={'ok' if cons_ok else 'WRONG'}  {marks}")

    print("\n=== per-oracle accuracy vs ground truth ===")
    for name, _ in VOTERS:
        c, t = per_voter_correct[name], per_voter_total[name]
        print(f"  {name:9} {c}/{t}  ({100*c/t:.0f}%)")

    total_wrong = sum(per_voter_total[n] - per_voter_correct[n] for n, _ in VOTERS)
    print("\n=== detection (the Q15 question) ===")
    print(f"  inputs flagged by disagreement:      {flagged_total}/{consensus_total}")
    print(f"  wrong values on flagged inputs:      {flagged_wrong}/{total_wrong}"
          + ("  <-- all wrong values were flagged" if flagged_wrong == total_wrong
             else "  <-- some slipped through unanimous"))
    print(f"  UNANIMOUS-WRONG (undetectable):      {len(unanimous_wrong)}")
    for tid, inp, got, truth in unanimous_wrong:
        print(f"      {tid}: {json.dumps(inp)} -> all said {got!r}, truth {truth!r}")

    print("\n=== consensus vs single oracle ===")
    print(f"  5-oracle majority:  {consensus_correct}/{consensus_total} correct")
    print(f"  3x Haiku majority:  {cheap_correct}/{consensus_total} correct")
    print(f"  1x Opus alone:      {per_voter_correct['opus']}/{per_voter_total['opus']} correct")
    ch3 = _cost['claude-haiku-4-5'] * 3 / 3  # all haiku spend = the 3 cheap oracles
    print(f"  cost: 3x Haiku ${_cost['claude-haiku-4-5']:.4f}  "
          f"vs 1x Opus ${_cost['claude-opus-4-8']:.4f}")

    print("\n=== read ===")
    if not unanimous_wrong and flagged_wrong == total_wrong:
        print("  Every wrong oracle value coincided with cross-oracle disagreement.")
        print("  => Disagreement-flagging is a viable no-ground-truth defense:")
        print("     route flagged cases to a stronger model or a human, trust the rest.")
    elif unanimous_wrong:
        print("  Some oracles were unanimously WRONG -- correlated failure that")
        print("  consensus cannot see. Cross-checking alone is NOT sufficient;")
        print("  new verticals need human spot-checks on the oracle.")


if __name__ == "__main__":
    main()
