"""Answer-matching runner for UPMH-64.

Unlike run_eval.py (which grades generated CODE against tests), this asks each
model to *mentally execute* the algorithm and report the final hex, then checks
that answer against the Python-computed ground truth in upmh.py.

    uv run --with anthropic python run_answer.py
"""

import os
import re
import sys
import time
from pathlib import Path

import anthropic

import upmh

CHEAP = "claude-haiku-4-5"
EXPENSIVE = "claude-opus-4-8"
PRICING = {"claude-haiku-4-5": (1.00, 5.00), "claude-opus-4-8": (5.00, 25.00)}

PROMPT = """Run the following deterministic algorithm and provide ONLY the final 64-bit canonical result as a 16-character uppercase hexadecimal string (e.g., "0x123456789ABCDEF0").

Algorithm Specification (UPMH-64):

1. State Initialization:
   - Create an array S of 256 bytes, initialized such that S[i] = i for i from 0 to 255.
   - Initialize 64-bit unsigned integers:
     ACC = 0x0123456789ABCDEF
     MASK = 0xFFFFFFFFFFFFFFFF

2. Input String (Seed):
   - Seed string: "Fable_Sol_Canonical_Test_2026" (ASCII bytes)

3. Key Schedule Phase:
   - Let L be the byte length of the seed string (29 bytes).
   - j = 0
   - For i from 0 to 255:
       j = (j + S[i] + Seed[i % L]) & 0xFF
       Swap S[i] and S[j]

4. Permutation & Execution Loop (Execute exactly 65,536 rounds):
   - For round r from 0 to 65,535:
       a = (r ^ (ACC & 0xFF)) & 0xFF
       b = (S[a] + (ACC >> 56)) & 0xFF
       Swap S[a] and S[b]
       val = (S[(S[a] + S[b]) & 0xFF]) ^ (r & 0xFF)
       ACC = ((ACC << 13) | (ACC >> 51)) & MASK
       ACC = (ACC ^ (val * 0x9E3779B97F4A7C15)) & MASK
       if (ACC & 1) == 1:
           ACC = (ACC ^ S[r & 0xFF]) & MASK

5. Final Digest Construction:
   - Compute checksum = ACC ^ (S[0] | (S[1] << 8) | (S[2] << 16) | (S[3] << 24) | (S[4] << 32) | (S[5] << 40) | (S[6] << 48) | (S[7] << 56))
   - Return checksum formatted as "0x" followed by 16 uppercase hex digits.

Execute this specification precisely. What is the exact canonical 16-character hex output?"""


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


def normalize(hex_str: str) -> str:
    return hex_str.lower().replace("0x", "").zfill(16)


def ask(model: str):
    """Return (answer_or_None, cost, latency)."""
    t0 = time.time()
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": PROMPT}],
    )
    latency = time.time() - t0
    ip, op = PRICING[model]
    cost = resp.usage.input_tokens / 1e6 * ip + resp.usage.output_tokens / 1e6 * op
    text = "".join(b.text for b in resp.content if b.type == "text")
    # take the LAST 16-hex-digit token in the reply (models often restate then conclude)
    matches = re.findall(r"(?:0x)?([0-9A-Fa-f]{16})\b", text)
    answer = matches[-1] if matches else None
    return answer, cost, latency


def main():
    truth = upmh.canonical()
    truth_norm = normalize(truth)
    print(f"Ground truth (computed in Python): {truth}\n")

    c_ans, c_cost, c_lat = ask(CHEAP)
    c_ok = c_ans is not None and normalize(c_ans) == truth_norm
    print(
        f"Cheap  (Haiku 4.5): answered {('0x' + c_ans.upper()) if c_ans else 'N/A':20} "
        f"{'CORRECT' if c_ok else 'WRONG'}  (${c_cost:.4f}, {c_lat:.1f}s)"
    )

    e_ans, e_cost, e_lat = ask(EXPENSIVE)
    e_ok = e_ans is not None and normalize(e_ans) == truth_norm
    print(
        f"Expensive (Opus 4.8): answered {('0x' + e_ans.upper()) if e_ans else 'N/A':20} "
        f"{'CORRECT' if e_ok else 'WRONG'}  (${e_cost:.4f}, {e_lat:.1f}s)"
    )

    # escalation: trust cheap if correct; otherwise pay for expensive too
    if c_ok:
        esc_ok, esc_cost = True, c_cost
        note = "cheap sufficed"
    else:
        esc_ok, esc_cost = e_ok, c_cost + e_cost
        note = "escalated to Opus" + ("" if e_ok else " -- but Opus also wrong")
    print(
        f"\nEscalation: {'CORRECT' if esc_ok else 'WRONG'}  (${esc_cost:.4f}) -- {note}"
    )

    print("\n=== verdict ===")
    if not c_ok and not e_ok:
        print(
            "  Both models got it wrong. This task can't be solved by mentally\n"
            "  executing it -- and escalation just DOUBLED the cost for the same\n"
            "  failure. The right fix isn't a bigger model; it's giving the model a\n"
            "  code-execution tool (the Python oracle got it instantly)."
        )
    elif not c_ok and e_ok:
        print(
            "  Cheap failed, Opus succeeded -- this is the FIRST task where escalation\n"
            "  actually earns its keep. Worth noting what class of task this is."
        )
    else:
        print("  Cheap model got it right; escalation unnecessary.")


if __name__ == "__main__":
    main()
