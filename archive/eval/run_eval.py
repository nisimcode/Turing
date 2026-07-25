"""Low-cost dry run: does cheap->expensive escalation actually pay off?

Runs three approaches over the coding tasks in tasks.py and measures each:

  1. cheap only      -- Haiku 4.5 handles every task
  2. expensive only  -- Opus 4.8 handles every task (the baseline to beat)
  3. escalation      -- Haiku first; if its code fails the tests, retry with Opus

Success is objective: the model's code is executed against the task's tests.
For each approach we report tasks passed, total cost, and -- the number that
matters -- cost per PASSED task. That last figure exposes a cheap approach
that only looks cheap because it's quietly shipping failures.

Usage:
    pip install -r requirements.txt
    python run_eval.py

The API key is read from ../.env (CLAUDE_API_KEY=...) or from the
ANTHROPIC_API_KEY / CLAUDE_API_KEY environment variables.

This is a smoke test (one attempt per task), not a statistically powered study.
"""

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import importlib

import anthropic

# Task set defaults to tasks.py; override with e.g. `python run_eval.py tasks_contest`
_task_module = sys.argv[1] if len(sys.argv) > 1 else "tasks"
TASKS = importlib.import_module(_task_module).TASKS


def load_api_key() -> str:
    """Find the key from env vars, or parse it out of a nearby .env file."""
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
    sys.exit(
        "No API key found. Set CLAUDE_API_KEY in E:\\Turing\\.env "
        "or export ANTHROPIC_API_KEY."
    )

# --- models under test -------------------------------------------------------
CHEAP = "claude-haiku-4-5"
EXPENSIVE = "claude-opus-4-8"

# price per 1M tokens (input, output), USD -- from the model catalog
PRICING = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-4-8": (5.00, 25.00),
}

MAX_TOKENS = 8192

SYSTEM = (
    "You are a precise Python coding assistant. Implement exactly what is asked. "
    "Respond with a single ```python code block containing the complete solution "
    "(the required functions/classes and nothing else) -- no explanation, no "
    "commentary outside the code block, no example usage or tests beyond what the "
    "task explicitly requires."
)

client = anthropic.Anthropic(api_key=load_api_key())


def call_model(model: str, prompt: str):
    """Return (code_text, cost_usd, latency_s)."""
    t0 = time.time()
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    latency = time.time() - t0
    in_price, out_price = PRICING[model]
    cost = (
        resp.usage.input_tokens / 1e6 * in_price
        + resp.usage.output_tokens / 1e6 * out_price
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return extract_code(text), cost, latency


def extract_code(text: str) -> str:
    """Pull the code out of a ```python ... ``` fence, falling back to raw text."""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def run_tests(code: str, test_code: str) -> bool:
    """Execute the model's code + the task tests in a subprocess. True == passed."""
    program = code + "\n\n" + test_code + "\nprint('OK')\n"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        path = f.name
        f.write(program)
    try:
        proc = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0 and proc.stdout.strip().endswith("OK")
    except subprocess.TimeoutExpired:
        return False
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def summarize(name: str, results: list[dict]):
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    cost = sum(r["cost"] for r in results)
    latency = sum(r["latency"] for r in results) / total
    per_success = cost / passed if passed else float("inf")
    print(f"\n=== {name} ===")
    print(f"  passed:            {passed}/{total}")
    print(f"  total cost:        ${cost:.4f}")
    print(f"  avg latency:       {latency:.1f}s")
    cps = f"${per_success:.4f}" if passed else "n/a (0 passed)"
    print(f"  cost per success:  {cps}")
    return {
        "name": name,
        "passed": passed,
        "total": total,
        "cost": cost,
        "cost_per_success": per_success,
    }


def main():
    cheap_results, exp_results, esc_results = [], [], []

    print(f"Running {len(TASKS)} tasks x 3 approaches...\n")
    for task in TASKS:
        tid, level = task["id"], task["level"]

        # --- cheap only ---
        code, cost, lat = call_model(CHEAP, task["prompt"])
        cheap_pass = run_tests(code, task["test_code"])
        cheap_results.append({"passed": cheap_pass, "cost": cost, "latency": lat})

        # --- expensive only ---
        ecode, ecost, elat = call_model(EXPENSIVE, task["prompt"])
        exp_pass = run_tests(ecode, task["test_code"])
        exp_results.append({"passed": exp_pass, "cost": ecost, "latency": elat})

        # --- escalation: reuse the cheap attempt; only pay for Opus if it failed ---
        if cheap_pass:
            esc_results.append({"passed": True, "cost": cost, "latency": lat})
            escalated = False
        else:
            esc_results.append(
                {"passed": exp_pass, "cost": cost + ecost, "latency": lat + elat}
            )
            escalated = True

        flag = "  ->ESCALATED" if escalated else ""
        print(
            f"[{level:6}] {tid:18} "
            f"cheap={'P' if cheap_pass else 'F'} "
            f"exp={'P' if exp_pass else 'F'}{flag}"
        )

    rows = [
        summarize("Cheap only (Haiku 4.5)", cheap_results),
        summarize("Expensive only (Opus 4.8)", exp_results),
        summarize("Escalation (Haiku -> Opus on failure)", esc_results),
    ]

    # --- verdict ---
    baseline = rows[1]  # expensive only
    esc = rows[2]
    print("\n=== verdict ===")
    if esc["passed"] >= baseline["passed"] and esc["cost"] < baseline["cost"]:
        pct = 100 * (baseline["cost"] - esc["cost"]) / baseline["cost"]
        print(
            f"  Escalation matched the expensive baseline's pass rate "
            f"at {pct:.0f}% lower cost. Worth pursuing."
        )
    elif esc["passed"] < baseline["passed"]:
        print(
            "  Escalation passed fewer tasks than the expensive baseline -- "
            "the cheap model's failures aren't all being caught/fixed. "
            "Look at which tasks it dropped before pursuing."
        )
    else:
        print(
            "  Escalation didn't beat the expensive baseline on cost. "
            "On this sample it's not yet worth the added complexity."
        )
    print("\n(Smoke test: one attempt per task. Treat as directional, not proof.)")


if __name__ == "__main__":
    main()
