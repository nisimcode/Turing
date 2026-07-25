"""Decisive test: does the judge track CORRECTNESS, or just style/consistency?

Part 1: each model writes wordle_feedback(); we grade it objectively against a
        battery of duplicate-letter edge cases (ground truth = a trusted oracle).
Part 2: the real probe. A CORRECT implementation vs a subtly-BUGGY but clean,
        concise one (we control which is which and verify objectively). Judges
        compare them blind, both orderings, repeated. Does the judge pick the
        one that is actually correct -- or the prettier wrong one?

If the judge reliably picks correct over buggy, a cascade has a real quality
gate. If it gets fooled, the gate is an illusion.

    uv run --with anthropic python run_judge2.py
"""

import os
import re
import sys
from collections import Counter
from pathlib import Path

import anthropic

BUILDERS = {"haiku": "claude-haiku-4-5", "opus": "claude-opus-4-8"}
JUDGES = {"opus-judge": "claude-opus-4-8", "haiku-judge": "claude-haiku-4-5"}
REPEATS = 3
PRICING = {"claude-haiku-4-5": (1.0, 5.0), "claude-opus-4-8": (5.0, 25.0)}

# duplicate-letter-heavy battery
BATTERY = [
    ("PPPPP", "APPLE"), ("SPEED", "ERASE"), ("ALLOY", "LOLLY"),
    ("ABBEY", "KEBAB"), ("ROBOT", "OTTER"), ("CRANE", "CANAL"),
    ("LEVEL", "EAGLE"), ("APPLE", "PAPER"), ("EERIE", "THERE"),
    ("GEESE", "SIEGE"),
]

FUNC_PROMPT = (
    "Write a Python function `wordle_feedback(guess: str, answer: str) -> str`. "
    "Both inputs are uppercase 5-letter words. Return a 5-character string where "
    "position i is 'G' if guess[i] == answer[i]; 'Y' if guess[i] occurs in answer "
    "but in a wrong spot; 'B' otherwise -- with CORRECT duplicate-letter handling "
    "(a guessed letter must not be marked 'Y' more times than copies remain in the "
    "answer after greens are accounted for). Return only the function in one code "
    "block."
)

JUDGE_TMPL = (
    "Two Python implementations of a Wordle feedback function are labeled A and B. "
    "Each returns 5 chars of 'G'/'Y'/'B'. Decide which is the MORE CORRECT "
    "implementation, paying special attention to duplicate-letter edge cases. "
    "Reason briefly, then output exactly one final line: 'WINNER: A' or "
    "'WINNER: B'.\n\n=== Implementation A ===\n{a}\n\n=== Implementation B ===\n{b}\n"
)

# ---- ground-truth oracle ----
def oracle(guess, answer):
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


# ---- controlled pair (we know the truth) ----
CORRECT_SRC = '''\
def wordle_feedback(guess, answer):
    """Return G/Y/B feedback with proper duplicate-letter accounting."""
    res = ["B"] * 5
    remaining = {}
    for ch in answer:
        remaining[ch] = remaining.get(ch, 0) + 1
    for i in range(5):
        if guess[i] == answer[i]:
            res[i] = "G"
            remaining[guess[i]] -= 1
    for i in range(5):
        if res[i] == "B" and remaining.get(guess[i], 0) > 0:
            res[i] = "Y"
            remaining[guess[i]] -= 1
    return "".join(res)
'''

BUGGY_SRC = '''\
def wordle_feedback(guess, answer):
    """Return G/Y/B feedback for a Wordle guess."""
    return "".join(
        "G" if guess[i] == answer[i]
        else "Y" if guess[i] in answer
        else "B"
        for i in range(5)
    )
'''


def load_api_key() -> str:
    for var in ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
        if os.environ.get(var):
            return os.environ[var]
    here = Path(__file__).resolve().parent
    for env_path in (here / ".env", here.parent / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(("CLAUDE_API_KEY=", "ANTHROPIC_API_KEY=")):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("No API key found (set CLAUDE_API_KEY in E:\\Turing\\.env).")


client = anthropic.Anthropic(api_key=load_api_key())
_cost = 0.0


def call(model, prompt, max_tokens):
    global _cost
    resp = client.messages.create(
        model=model, max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    ip, op = PRICING[model]
    _cost += resp.usage.input_tokens / 1e6 * ip + resp.usage.output_tokens / 1e6 * op
    return "".join(b.text for b in resp.content if b.type == "text")


def extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def load_fn(src):
    ns = {}
    try:
        exec(src, ns)
    except Exception:
        return None
    return ns.get("wordle_feedback")


def grade(fn):
    if fn is None:
        return False, "no wordle_feedback defined"
    for g, a in BATTERY:
        try:
            got = fn(g, a)
        except Exception as e:
            return False, f"exception on ({g},{a}): {e!r}"
        if got != oracle(g, a):
            return False, f"wrong on ({g},{a}): got {got}, expected {oracle(g,a)}"
    return True, "passed all edge cases"


def parse_winner(text):
    m = re.findall(r"WINNER:\s*([AB])", text, re.IGNORECASE)
    return m[-1].upper() if m else None


def judge_pair(label_correct, src_correct, label_buggy, src_buggy):
    """Judge the correct-vs-buggy pair; return per-judge pick counts."""
    srcs = {label_correct: src_correct, label_buggy: src_buggy}
    orders = [(label_correct, label_buggy), (label_buggy, label_correct)]
    for jname, jmodel in JUDGES.items():
        calls = []
        for a_lbl, b_lbl in orders:
            prompt = JUDGE_TMPL.format(a=srcs[a_lbl], b=srcs[b_lbl])
            for _ in range(REPEATS):
                letter = parse_winner(call(jmodel, prompt, 1200))
                winner = a_lbl if letter == "A" else b_lbl if letter == "B" else None
                calls.append((f"{a_lbl}=A,{b_lbl}=B", letter, winner))
        print(f"--- {jname} ({jmodel}) ---")
        for order, letter, winner in calls:
            print(f"    [{order:24}] picked {letter} -> {winner}")
        wins = Counter(w for _, _, w in calls if w)
        picked_correct = wins.get(label_correct, 0)
        print(f"    picked CORRECT {picked_correct}/{len(calls)} times   {dict(wins)}")
        if picked_correct == len(calls):
            print("    => catches the bug every time. Trustworthy gate.")
        elif picked_correct == 0:
            print("    => FOOLED every time -- preferred the buggy one.")
        else:
            print("    => unreliable (mixed).")
        print()


def main():
    print("PART 1 -- objective grading of model-written wordle_feedback:\n")
    for name, model in BUILDERS.items():
        code = extract_code(call(model, FUNC_PROMPT, 2048))
        ok, detail = grade(load_fn(code))
        print(f"  {name:6} ({model}): {'CORRECT' if ok else 'WRONG'} -- {detail}")

    print("\nPART 2 -- can the judge tell correct from subtly-buggy-but-clean?\n")
    # sanity: confirm our controlled ground truth
    ok_c, _ = grade(load_fn(CORRECT_SRC))
    ok_b, _ = grade(load_fn(BUGGY_SRC))
    print(f"  ground truth check: CORRECT_SRC passes={ok_c}, BUGGY_SRC passes={ok_b}")
    assert ok_c and not ok_b, "controlled pair is not set up as intended"
    print("  (buggy one is shorter/cleaner -- a style temptation)\n")
    judge_pair("correct", CORRECT_SRC, "buggy", BUGGY_SRC)

    print(f"Total cost this run: ${_cost:.4f}")


if __name__ == "__main__":
    main()
