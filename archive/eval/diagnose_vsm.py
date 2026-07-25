"""Diagnose the VSM cascade failure: real interpreter bug, or gate false-reject?

For each model we run TWO checks on its generated code:
  FULL     -- exactly what the cascade gate did: run [code + tests] as a script
              (__name__ == "__main__"), so any bottom-of-file run_test_payload()
              call fires.
  ISOLATED -- import the code as a module (__name__ != "__main__", so a __main__
              guard does NOT fire) and run ONLY the run_vm test checks.

If FULL fails but ISOLATED passes, run_vm was fine and the gate was tripped by
the model's own required-but-buggy payload -> a false reject (gate blamed the
wrong part). If both fail the same run_vm assertion, it's a real bug.

    uv run --with anthropic python diagnose_vsm.py
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import anthropic

import tasks_vsm

MODELS = {"haiku": "claude-haiku-4-5", "opus": "claude-opus-4-8"}
TASK = tasks_vsm.TASKS[0]
TEST = tasks_vsm._TEST
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


def generate(model):
    resp = client.messages.create(
        model=model, max_tokens=8192, system=SYSTEM,
        messages=[{"role": "user", "content": TASK["prompt"]}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def run_script(src, cwd, timeout=20):
    p = Path(cwd) / "_run.py"
    p.write_text(src, encoding="utf-8")
    try:
        proc = subprocess.run([sys.executable, str(p)], capture_output=True,
                              text=True, timeout=timeout, cwd=cwd)
        return proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired:
        return None, "", "", True


def last_error(stderr):
    lines = [l for l in stderr.strip().splitlines() if l.strip()]
    return lines[-1] if lines else "(no stderr)"


def diagnose(name, code):
    print(f"\n########## {name} ##########")
    has_payload = "def run_test_payload" in code
    guard = re.search(r"if\s+__name__\s*==\s*['\"]__main__['\"]", code) is not None
    # bare top-level call to run_test_payload() (col 0, not under a def/guard)
    toplevel_call = bool(re.search(r"^run_test_payload\s*\(", code, re.MULTILINE))
    print(f"  defines run_test_payload: {has_payload} | "
          f"has __main__ guard: {guard} | bare top-level call: {toplevel_call}")

    tmp = tempfile.mkdtemp()

    # FULL: reproduce the cascade gate
    full_src = code + "\n\n" + TEST + "\nprint('GATE_OK')\n"
    rc, out, err, to = run_script(full_src, tmp)
    if to:
        full_ok, full_why = False, "TIMEOUT (something ran forever)"
    elif rc == 0 and out.strip().endswith("GATE_OK"):
        full_ok, full_why = True, "passed"
    else:
        full_ok, full_why = False, last_error(err)
    print(f"  FULL gate:      {'PASS' if full_ok else 'FAIL'}  -- {full_why}")

    # ISOLATED: import code as a module, test only run_vm
    Path(tmp, "vsm_candidate.py").write_text(code, encoding="utf-8")
    iso_src = ("from vsm_candidate import run_vm\n" + TEST + "\nprint('ISO_OK')\n")
    rc, out, err, to = run_script(iso_src, tmp)
    if to:
        iso_ok, iso_why = False, "TIMEOUT"
    elif rc == 0 and out.strip().endswith("ISO_OK"):
        iso_ok, iso_why = True, "passed"
    else:
        iso_ok, iso_why = False, last_error(err)
    print(f"  ISOLATED run_vm:{'PASS' if iso_ok else 'FAIL'}  -- {iso_why}")

    print("  VERDICT: ", end="")
    if full_ok:
        print("gate passed; no reject to explain.")
    elif iso_ok and not full_ok:
        print("FALSE REJECT -- run_vm is correct; the gate was tripped by the "
              "model's own\n           required payload / __main__ execution, not "
              "the interpreter.")
    else:
        print("TRUE REJECT -- run_vm itself fails the checks (real interpreter bug).")


def main():
    for name, model in MODELS.items():
        diagnose(f"{name} ({model})", generate(model))
    print("\n(If FALSE REJECT appears: the gatekeeper decided fail for the wrong "
          "reason.\nThe interpreter was fine; a buggy secondary component sank it. "
          "Gate design,\nnot model capability, caused the cascade to escalate and "
          "still 'fail'.)")


if __name__ == "__main__":
    main()
