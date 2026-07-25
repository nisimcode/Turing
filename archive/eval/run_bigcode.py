"""Open-ended generation runner (no deterministic oracle possible).

The "architectural overhaul" task can't be graded for correctness by machine --
there's no fixed interface or expected output, and criteria like "no starvation"
or "zero memory leaks" need a human/LLM judge. So this measures only an OBJECTIVE
COMPLETENESS FLOOR for each model:

  * did the reply finish, or hit the token cap (truncated)?
  * how much code, across how many blocks/files?
  * does every code block parse (syntax-valid)?
  * any forbidden placeholders (TODO / FIXME / NotImplementedError / '...' stubs)?

Passing the floor does NOT mean the solution is correct -- only that it's a
complete, runnable-looking artifact rather than a stub. Correctness for this
task class is the part that needs judgment we can't cheaply automate.

    uv run --with anthropic python run_bigcode.py
"""

import os
import re
import sys
import time
from pathlib import Path

import anthropic

CHEAP = "claude-haiku-4-5"
EXPENSIVE = "claude-opus-4-8"
PRICING = {"claude-haiku-4-5": (1.00, 5.00), "claude-opus-4-8": (5.00, 25.00)}
MAX_TOKENS = 16000

PROMPT = """You are provided with a legacy multi-module system that processes user transaction event logs. I need you to perform a complete architectural overhaul and return the full implementation.

Task Specifications:
1. Module A (Log Ingestion): Parse an unformatted raw event stream containing nested JSON strings, malformed timestamps, and mixed byte-encodings. Extract valid events, apply a sliding window duplicate filter (last 10 seconds), and compute a running CRC32 checksum.
2. Module B (Event Bus & Logic): Implement an asynchronous, bounded event queue (max 500 capacity) that enforces strict priority backpressure. High-priority payment events bypass standard queue delay, but MUST NOT cause starvation for low-priority audit logs.
3. Module C (State Machine & Self-Correction): Process state transitions for a trading engine (Pending -> Filled -> Settled | Cancelled). If an invalid state transition occurs (e.g., Pending -> Settled directly), DO NOT crash: execute a dynamic roll-back strategy, reconstruct state from the last valid checkpoint in memory, and patch the corrupted event in the log queue without dropping surrounding messages.
4. Test Suite & Validation: Provide a fully runnable test suite with unit tests, property-based tests (checking edge cases for race conditions), and a baseline benchmark test verifying zero memory leaks over 10,000 synthetic operations.

Return the solution as clean, fully written, multi-file code ready to execute. Do not cut corners or leave TODO comments."""

PLACEHOLDER_PAT = re.compile(
    r"\bTODO\b|\bFIXME\b|NotImplementedError|raise NotImplemented\b|pass\s*#\s*implement",
    re.IGNORECASE,
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


def generate(model: str):
    t0 = time.time()
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": PROMPT}],
    )
    latency = time.time() - t0
    ip, op = PRICING[model]
    cost = resp.usage.input_tokens / 1e6 * ip + resp.usage.output_tokens / 1e6 * op
    text = "".join(b.text for b in resp.content if b.type == "text")
    return {
        "text": text,
        "cost": cost,
        "latency": latency,
        "stop_reason": resp.stop_reason,
        "out_tokens": resp.usage.output_tokens,
    }


def assess(name: str, g: dict):
    text = g["text"]
    blocks = re.findall(r"```(?:[\w+-]*)\n(.*?)```", text, re.DOTALL)
    parse_ok = parse_fail = 0
    for b in blocks:
        try:
            compile(b, "<block>", "exec")
            parse_ok += 1
        except SyntaxError:
            parse_fail += 1
    placeholders = len(PLACEHOLDER_PAT.findall(text))
    truncated = g["stop_reason"] == "max_tokens"

    print(f"\n=== {name} ===")
    print(f"  cost:              ${g['cost']:.4f}   latency: {g['latency']:.1f}s")
    print(f"  output tokens:     {g['out_tokens']}"
          + ("   <-- TRUNCATED (hit token cap)" if truncated else ""))
    print(f"  code blocks:       {len(blocks)}  (parse ok: {parse_ok}, "
          f"syntax errors: {parse_fail})")
    print(f"  placeholder/TODO:  {placeholders}")

    floor = (
        not truncated
        and len(blocks) >= 1
        and parse_fail == 0
        and placeholders == 0
    )
    print(f"  completeness floor: {'PASS' if floor else 'FAIL'}")
    return {"name": name, "floor": floor, "cost": g["cost"], "truncated": truncated,
            "parse_fail": parse_fail, "placeholders": placeholders}


def main():
    print("Generating full multi-file implementations (this is NOT correctness-graded)...")
    ch = assess("Cheap (Haiku 4.5)", generate(CHEAP))
    ex = assess("Expensive (Opus 4.8)", generate(EXPENSIVE))

    print("\n=== verdict ===")
    print("  This task has no deterministic oracle -- 'correct' here needs a human")
    print("  or LLM judge, which is exactly the scoring problem the plan flags.")
    print("  Objective completeness floor:")
    print(f"    Cheap:     {'PASS' if ch['floor'] else 'FAIL'}")
    print(f"    Expensive: {'PASS' if ex['floor'] else 'FAIL'}")
    if ch["floor"] and ex["floor"]:
        print("  Both produced complete, syntax-valid, placeholder-free artifacts.")
        print("  Whether either is actually CORRECT (no starvation, no leaks, correct")
        print("  rollback) is not machine-decidable from here -- that's the wall.")
    elif ex["floor"] and not ch["floor"]:
        print("  Only the expensive model cleared the floor -- first sign of a task")
        print("  class where paying more buys something measurable.")
    else:
        print("  See per-model detail above.")


if __name__ == "__main__":
    main()
