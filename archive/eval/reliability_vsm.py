"""Quantify VSM reliability: pass RATE across repeated generations (pass@k).

The cascade run had the VSM task fail all tiers; the diagnosis run had it pass.
Same task, same gate -> the outcome is nondeterministic. This measures how often
each model's fresh generation clears the objective gate, so routing decisions can
be based on a rate, not a single coin flip.

    uv run --with anthropic python reliability_vsm.py
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import anthropic

import tasks_vsm

TASK = tasks_vsm.TASKS[0]
TEST = tasks_vsm._TEST
TRIALS = {"claude-haiku-4-5": 6, "claude-opus-4-8": 3}
SYSTEM = (
    "You are a precise Python coding assistant. Implement exactly what is asked. "
    "Respond with a single ```python code block containing the complete solution "
    "and nothing else."
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


def gen_and_gate(model):
    resp = client.messages.create(
        model=model, max_tokens=8192, system=SYSTEM,
        messages=[{"role": "user", "content": TASK["prompt"]}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    code = m.group(1) if m else text
    src = code + "\n\n" + TEST + "\nprint('GATE_OK')\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        path = f.name
        f.write(src)
    try:
        proc = subprocess.run([sys.executable, path], capture_output=True,
                              text=True, timeout=20)
        return proc.returncode == 0 and proc.stdout.strip().endswith("GATE_OK")
    except subprocess.TimeoutExpired:
        return False
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def main():
    for model, n in TRIALS.items():
        results = []
        for i in range(n):
            ok = gen_and_gate(model)
            results.append(ok)
            print(f"  {model:20} trial {i+1}/{n}: {'PASS' if ok else 'FAIL'}")
        rate = sum(results) / n
        print(f"  => {model}: pass rate {sum(results)}/{n} = {rate*100:.0f}%\n")

    print("Takeaway: a task can pass or fail the SAME gate run-to-run. A cascade "
          "must\nroute on the pass RATE (pass@k), never a single attempt -- and the "
          "gate's\nverdict flipping is model variance, not the gate being wrong.")


if __name__ == "__main__":
    main()
