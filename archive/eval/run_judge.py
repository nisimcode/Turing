"""Does an automated judge reliably pick the better build -- or is it just biased?

The load-bearing question for a model cascade: you can only route "use the
cheapest model that's good enough" if you can *tell* what's good enough. For
open-ended work there's no oracle, so you need a judge. This tests whether a
judge is trustworthy:

  1. Haiku and Opus each build a single-file Wordle.
  2. Two judges (Opus, Haiku) compare them PAIRWISE, in BOTH orderings, repeated.
  3. We check: does each judge pick the same underlying build regardless of which
     slot (A/B) it's shown in? If the verdict flips with position, the judge is
     measuring order, not quality -- and the cascade has no spine.

    uv run --with anthropic python run_judge.py
"""

import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import anthropic

BUILDERS = {"haiku": "claude-haiku-4-5", "opus": "claude-opus-4-8"}
JUDGES = {"opus-judge": "claude-opus-4-8", "haiku-judge": "claude-haiku-4-5"}
REPEATS = 2
ART = Path(__file__).resolve().parent / "artifacts"

BUILD_PROMPT = (
    "Build a complete, working Wordle game as a SINGLE self-contained HTML file "
    "(inline CSS and JavaScript, no external assets). Requirements: a fixed "
    "5-letter secret word; up to 6 guesses; after each guess color every letter "
    "green (right letter, right spot), yellow (in the word, wrong spot), or gray "
    "(not in the word), with CORRECT handling of duplicate letters; detect win and "
    "loss. It must run by opening the file in a browser. Return ONLY the HTML in a "
    "single code block."
)

JUDGE_TMPL = (
    "You are judging two single-file HTML implementations of Wordle, labeled A and "
    "B. Evaluate on, in priority order: (1) correctness of the letter-coloring "
    "logic, especially duplicate-letter edge cases; (2) completeness / would it "
    "actually run and be playable; (3) code quality; (4) UX. Reason briefly, then "
    "output exactly one final line: 'WINNER: A' or 'WINNER: B'.\n\n"
    "=== Implementation A ===\n{a}\n\n=== Implementation B ===\n{b}\n"
)


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
PRICING = {"claude-haiku-4-5": (1.0, 5.0), "claude-opus-4-8": (5.0, 25.0)}


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
    m = re.search(r"```(?:html)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def parse_winner(text):
    m = re.findall(r"WINNER:\s*([AB])", text, re.IGNORECASE)
    return m[-1].upper() if m else None


def main():
    ART.mkdir(exist_ok=True)
    builds = {}
    for name, model in BUILDERS.items():
        print(f"Building Wordle with {name} ({model})...")
        code = extract_code(call(model, BUILD_PROMPT, 8192))
        (ART / f"wordle_{name}.html").write_text(code, encoding="utf-8")
        builds[name] = code
        print(f"  -> {len(code)} chars saved to artifacts/wordle_{name}.html")

    print("\nJudging (2 orderings x "
          f"{REPEATS} repeats per judge)...\n")
    # orderings: (slotA_builder, slotB_builder)
    orders = [("haiku", "opus"), ("opus", "haiku")]

    for jname, jmodel in JUDGES.items():
        calls = []  # (order_str, winner_builder or None)
        for a_builder, b_builder in orders:
            prompt = JUDGE_TMPL.format(a=builds[a_builder], b=builds[b_builder])
            for _ in range(REPEATS):
                letter = parse_winner(call(jmodel, prompt, 1500))
                winner = None
                if letter == "A":
                    winner = a_builder
                elif letter == "B":
                    winner = b_builder
                calls.append((f"{a_builder}=A,{b_builder}=B", letter, winner))

        print(f"--- {jname} ({jmodel}) ---")
        for order, letter, winner in calls:
            print(f"    [{order:20}] picked {letter}  -> {winner}")
        wins = Counter(w for _, _, w in calls if w)
        letters = Counter(l for _, l, _ in calls if l)
        # position bias: how often the first slot (A) was chosen
        a_rate = letters.get("A", 0) / max(1, sum(letters.values()))
        # consistency: did one builder win regardless of position?
        consistent = len(wins) == 1 and sum(wins.values()) == len(calls)
        print(f"    build wins: {dict(wins)}   slot-A chosen: {a_rate*100:.0f}%")
        if consistent:
            print(f"    => CONSISTENT: always preferred '{list(wins)[0]}' "
                  "regardless of position. Judge looks trustworthy.")
        elif a_rate >= 0.75 or a_rate <= 0.25:
            print("    => POSITION BIAS: verdict tracks the slot, not the build. "
                  "Judge is unreliable.")
        else:
            print("    => INCONSISTENT: no stable preference. Judge is noisy.")
        print()

    print(f"Total cost this run: ${_cost:.4f}")
    print("\nInterpretation: a cascade needs a judge that is CONSISTENT (same "
          "winner\nregardless of slot). Position bias or noise means you cannot "
          "trust it to\ndecide 'good enough', and the routing idea has no reliable "
          "gate.")


if __name__ == "__main__":
    main()
