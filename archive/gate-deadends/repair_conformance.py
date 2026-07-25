"""Conformance repair: treat a missing contract hook as a PROTOCOL failure to fix,
not a quality rejection.

Re-gates the existing corpus (gate/corpus/gen_*.html). For any build missing the
`window.__wordle` hook, does ONE cheap follow-up call asking the model to add the
hook, then re-gates the repaired build. Reports conformance before vs after and
whether repaired builds pass the coloring logic.

    uv run --with anthropic --with playwright --with pillow python repair_conformance.py
"""

import os
import re
import sys
from pathlib import Path

import anthropic

from browser_gate import gate_html
import wordle_spec

MODEL = "claude-haiku-4-5"
HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"

REPAIR_INSTRUCTIONS = (
    "The following single-file Wordle HTML is missing (or has an incomplete) "
    "testable hook. It MUST expose on window:\n"
    "  window.__wordle = {\n"
    "    setAnswer(word),        // force the secret (5 letters, any case)\n"
    "    guess(word) -> string   // 5 chars of 'G'/'Y'/'B', correct duplicate handling\n"
    "  }\n"
    "where 'G'=right letter right spot, 'Y'=in word wrong spot (limited by "
    "remaining counts after greens), 'B'=absent, and guess() reflects the game's "
    "real logic. Return the COMPLETE corrected HTML with that hook added. Return "
    "ONLY the HTML in one code block."
)


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
_cost = 0.0


def repair(html: str) -> str:
    global _cost
    content = REPAIR_INSTRUCTIONS + "\n\n```html\n" + html + "\n```"
    resp = client.messages.create(
        model=MODEL, max_tokens=8192,
        messages=[{"role": "user", "content": content}],
    )
    _cost += resp.usage.input_tokens / 1e6 * 1.0 + resp.usage.output_tokens / 1e6 * 5.0
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"```(?:html)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def has_contract(v):
    c = next((c for c in v["checks"] if c["name"] == "contract"), None)
    return bool(c and c["ok"])


def logic_ok(v):
    c = next((c for c in v["checks"] if c["name"] == "wordle_logic"), None)
    return bool(c and c["ok"])


def main():
    files = sorted(p for p in CORPUS.glob("gen_*.html") if ".repaired" not in p.name)
    if not files:
        sys.exit("No corpus found. Run kill_check.py first.")

    before = after = after_logic = 0
    print(f"{'build':10} {'before':10} {'after repair':14} logic")
    print("-" * 48)
    for f in files:
        v = gate_html(f, functional=wordle_spec.functional_checks)
        if has_contract(v):
            before += 1
            after += 1
            after_logic += 1 if logic_ok(v) else 0
            print(f"{f.stem:10} {'conformant':10} {'-':14} "
                  f"{'ok' if logic_ok(v) else 'FAIL'}")
        else:
            rf = CORPUS / f"{f.stem}.repaired.html"
            rf.write_text(repair(f.read_text(encoding='utf-8')), encoding="utf-8")
            v2 = gate_html(rf, functional=wordle_spec.functional_checks)
            ok = has_contract(v2)
            after += 1 if ok else 0
            after_logic += 1 if (ok and logic_ok(v2)) else 0
            print(f"{f.stem:10} {'MISSING':10} "
                  f"{('conformant' if ok else 'still missing'):14} "
                  f"{('ok' if logic_ok(v2) else 'FAIL') if ok else '-'}")

    n = len(files)
    print(f"\n=== conformance: {before}/{n} -> {after}/{n} after repair ===")
    print(f"    repaired builds with correct coloring: contributes to {after_logic}/{n} logic-ok")
    print(f"    repair cost: ${_cost:.4f}")
    if after > before:
        print("  => Repair lifts conformance: a missing hook is a fixable protocol")
        print("     failure, not a reason to reject the build or escalate tiers.")


if __name__ == "__main__":
    main()
