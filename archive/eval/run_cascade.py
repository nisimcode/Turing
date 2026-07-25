"""End-to-end model-cascade prototype with an OBJECTIVE gate.

For each task, start at the cheapest tier and run its generated code against the
task's test suite (the gate). Escalate to the next tier only when the gate fails.
Compare the cascade's total cost and success against two baselines: always-cheap
and always-top.

Tiers (cheap -> capable):  Haiku 4.5  ->  Sonnet 5  ->  Opus 4.8
(To add Fable as a 4th tier, append ("fable", "claude-fable-5") to TIERS -- note
it is pricier, may be access-gated, and needs 30-day data retention.)

    uv run --with anthropic python run_cascade.py
"""

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import anthropic

import tasks
import tasks_contest
import tasks_vsm

TIERS = [
    ("haiku", "claude-haiku-4-5"),
    ("sonnet", "claude-sonnet-5"),
    ("opus", "claude-opus-4-8"),
]
# price per 1M tokens (input, output). Sonnet 5 shown at standard; intro is $2/$10.
PRICING = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-4-8": (5.00, 25.00),
}
MAX_TOKENS = 8192

SYSTEM = (
    "You are a precise Python coding assistant. Implement exactly what is asked. "
    "Respond with a single ```python code block containing the complete solution "
    "and nothing else -- no prose, no example usage, no extra tests."
)

# curated spread of difficulty; all have objective test gates
SELECTED = [
    "e1_reverse_words", "m1_merge_intervals", "h1_word_break", "h2_lru_cache",
    "c2_alt_sum_product", "c3_max_subarray_swaps", "c5_balanced_swap",
    "v1_vsm_interpreter",
]


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

ALL_TASKS = {t["id"]: t for t in (tasks.TASKS + tasks_contest.TASKS + tasks_vsm.TASKS)}


def extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def run_tests(code, test_code):
    program = code + "\n\n" + test_code + "\nprint('OK')\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        path = f.name
        f.write(program)
    try:
        proc = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=20)
        return proc.returncode == 0 and proc.stdout.strip().endswith("OK")
    except subprocess.TimeoutExpired:
        return False
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


_memo = {}  # (model, task_id) -> {passed, cost}


def attempt(model, task):
    """Generate with `model`, grade against the task gate. Memoized. Never raises."""
    key = (model, task["id"])
    if key in _memo:
        return _memo[key]
    try:
        resp = client.messages.create(
            model=model, max_tokens=MAX_TOKENS, system=SYSTEM,
            messages=[{"role": "user", "content": task["prompt"]}],
        )
        ip, op = PRICING[model]
        cost = resp.usage.input_tokens / 1e6 * ip + resp.usage.output_tokens / 1e6 * op
        code = extract_code("".join(b.text for b in resp.content if b.type == "text"))
        passed = run_tests(code, task["test_code"])
        res = {"passed": passed, "cost": cost, "error": None}
    except Exception as e:  # missing model access, etc. -> treat as a failed tier
        res = {"passed": False, "cost": 0.0, "error": str(e)[:80]}
    _memo[key] = res
    return res


def main():
    cheap_model = TIERS[0][1]
    top_model = TIERS[-1][1]
    rows = []

    print("task                  | " + " ".join(f"{n:>6}" for n, _ in TIERS)
          + " | cascade -> tier   cost")
    print("-" * 78)

    for tid in SELECTED:
        task = ALL_TASKS[tid]

        # cascade: walk tiers until the gate passes
        settled_tier, cascade_cost = None, 0.0
        tier_marks = []
        for name, model in TIERS:
            r = attempt(model, task)
            cascade_cost += r["cost"]
            mark = "P" if r["passed"] else ("E" if r["error"] else "F")
            tier_marks.append(mark)
            if r["passed"]:
                settled_tier = name
                break
        # fill remaining tier marks we didn't need to run (cascade stopped early)
        while len(tier_marks) < len(TIERS):
            tier_marks.append("-")

        # ensure top-tier attempt exists for the always-top baseline
        attempt(top_model, task)

        rows.append({
            "id": tid,
            "cheap_pass": _memo[(cheap_model, tid)]["passed"],
            "cheap_cost": _memo[(cheap_model, tid)]["cost"],
            "top_pass": _memo[(top_model, tid)]["passed"],
            "top_cost": _memo[(top_model, tid)]["cost"],
            "settled": settled_tier,
            "cascade_cost": cascade_cost,
            "cascade_pass": settled_tier is not None,
        })
        print(f"{tid:21} | " + " ".join(f"{m:>6}" for m in tier_marks)
              + f" | {str(settled_tier):8} ${cascade_cost:.4f}")

    n = len(rows)
    ch_pass = sum(r["cheap_pass"] for r in rows)
    ch_cost = sum(r["cheap_cost"] for r in rows)
    tp_pass = sum(r["top_pass"] for r in rows)
    tp_cost = sum(r["top_cost"] for r in rows)
    cas_pass = sum(r["cascade_pass"] for r in rows)
    cas_cost = sum(r["cascade_cost"] for r in rows)

    print("\n=== strategy comparison (P = passed the objective gate) ===")
    print(f"  always cheap (Haiku): {ch_pass}/{n} passed   ${ch_cost:.4f}")
    print(f"  always top   (Opus):  {tp_pass}/{n} passed   ${tp_cost:.4f}")
    print(f"  CASCADE:              {cas_pass}/{n} passed   ${cas_cost:.4f}")

    if tp_cost:
        vs_top = 100 * (tp_cost - cas_cost) / tp_cost
        print(f"\n  cascade cost vs always-top: {vs_top:+.0f}%  "
              f"(${tp_cost - cas_cost:.4f} saved)")
    settled = [r["settled"] for r in rows]
    from collections import Counter
    print(f"  where tasks settled: {dict(Counter(settled))}")

    escalated = [r["id"] for r in rows if r["settled"] not in (TIERS[0][0], None)]
    failed = [r["id"] for r in rows if not r["cascade_pass"]]
    print(f"  escalated beyond cheap: {escalated or 'none'}")
    print(f"  unsolved by any tier:   {failed or 'none'}")

    print("\n=== read ===")
    if cas_pass >= tp_pass and cas_cost < tp_cost:
        print("  Cascade matched (or beat) always-top quality at lower cost. The")
        print("  objective gate escalated only when a cheaper tier actually failed.")
    if not escalated:
        print("  Note: the cheap tier cleared everything here, so higher tiers never")
        print("  fired. For THIS workload a cascade ~= 'use the cheap model', and the")
        print("  only real overhead is running the gate. Escalation earns its keep")
        print("  only on a workload where the cheap tier fails the gate at a real rate.")


if __name__ == "__main__":
    main()
