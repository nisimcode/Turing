"""Q26: paired cost-versus-correctness experiment for the gate cascade.

Each trial generates one cheap and one strong candidate for the same fixed
task. Both candidates are checked against a visible gate battery and a larger,
disjoint holdout. The three policies are then replayed from those same samples:

* always cheap
* always strong
* cheap first, escalating to strong only when the gate rejects

Local response caching, an exact paid-call cap, and an atomic result checkpoint
make the experiment safe to resume. A cache replay preserves the response's
original price for counterfactual policy accounting while spending $0 now.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import random
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.billsplit_spec import BATTERY as BILL_GATE
from gate.billsplit_spec import split_bill
from gate.calc_spec import BATTERY as CALC_GATE
from gate.core import (
    CHEAP,
    STRONG,
    LLMCallBlocked,
    call,
    cost_report,
    extract_code,
    last_response_cost,
    reset_cost,
    verify,
)
from gate.game2048_spec import BATTERY as GAME_GATE
from gate.game2048_spec import slide_left
from gate.wordle_spec import BATTERY as WORDLE_GATE
from gate.wordle_spec import oracle as wordle_oracle

HERE = Path(__file__).resolve().parent
SLOT = "/*__LOGIC_SLOT__*/"
RUNTIME_NAMES = {
    "loads",
    "no_page_errors",
    "no_console_err",
    "has_dom",
    "non_blank",
    "interactive",
    "no_outbound_requests",
}


@dataclass(frozen=True)
class Task:
    name: str
    prompt: str
    scaffold: str
    hook_test: str
    invoke: str
    gate_cases: tuple[tuple[tuple[Any, ...], Any], ...]
    audit_cases: tuple[tuple[tuple[Any, ...], Any], ...]
    correct_js: str
    bad_js: str


def _case(args: Any, expected: Any) -> tuple[tuple[Any, ...], Any]:
    if not isinstance(args, tuple):
        args = (args,)
    return args, expected


def _without_gate(cases, gate):
    gate_keys = {json.dumps(args, sort_keys=True) for args, _ in gate}
    return tuple(
        (args, expected)
        for args, expected in cases
        if json.dumps(args, sort_keys=True) not in gate_keys
    )


def _tool_scaffold(title: str, slot_comment: str, hook: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:sans-serif;background:#18212b;color:#eef;text-align:center;padding:24px}}
main{{max-width:560px;margin:auto;background:#243447;padding:24px;border-radius:12px}}
input,button{{padding:9px;margin:4px}} output{{display:block;margin:16px}}
</style></head><body><main><h1>{title}</h1><p>{slot_comment}</p>
<input id="value" value="demo"><button id="run">Run</button>
<output id="out">Ready</output></main><script>
{SLOT}
{hook}
document.getElementById("run").onclick=()=>{{document.getElementById("out").textContent="Ready"}};
</script></body></html>"""


def _roman(n: int) -> str:
    out = ""
    for value, token in (
        (1000, "M"), (500, "D"), (100, "C"), (50, "L"),
        (10, "X"), (5, "V"), (1, "I"),
    ):
        count, n = divmod(n, value)
        out += token * count
    return out


def _luhn_left(number: str) -> bool:
    total = 0
    for index, char in enumerate(number):
        value = int(char)
        if index % 2 == 0:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _rank_modified(scores: list[int]) -> list[int]:
    ordered = sorted(scores, reverse=True)
    return [max(i + 1 for i, value in enumerate(ordered) if value == score)
            for score in scores]


def _trunc_div(a: int, b: int) -> int:
    if b == 0:
        raise ZeroDivisionError
    return (-1 if (a < 0) ^ (b < 0) else 1) * (abs(a) // abs(b))


def _calculate(expr: str) -> int:
    """Small independent reference parser for the calculator holdout."""
    tokens = re.findall(r"\d+|[()+\-*/]", expr.replace(" ", ""))
    if "".join(tokens) != expr.replace(" ", ""):
        raise ValueError("invalid token")
    pos = 0

    def expression() -> int:
        nonlocal pos
        value = term()
        while pos < len(tokens) and tokens[pos] in {"+", "-"}:
            op = tokens[pos]
            pos += 1
            rhs = term()
            value = value + rhs if op == "+" else value - rhs
        return value

    def term() -> int:
        nonlocal pos
        value = factor()
        while pos < len(tokens) and tokens[pos] in {"*", "/"}:
            op = tokens[pos]
            pos += 1
            rhs = factor()
            value = value * rhs if op == "*" else _trunc_div(value, rhs)
        return value

    def factor() -> int:
        nonlocal pos
        if pos < len(tokens) and tokens[pos] == "-":
            pos += 1
            return -factor()
        if pos < len(tokens) and tokens[pos] == "(":
            pos += 1
            value = expression()
            if pos >= len(tokens) or tokens[pos] != ")":
                raise ValueError("missing close")
            pos += 1
            return value
        if pos >= len(tokens) or not tokens[pos].isdigit():
            raise ValueError("expected integer")
        value = int(tokens[pos])
        pos += 1
        return value

    result = expression()
    if pos != len(tokens):
        raise ValueError("trailing token")
    return result


WORDLE_CORRECT = r"""
function computeFeedback(guess, answer) {
  const out = Array(5).fill("B"), counts = {};
  for (const c of answer) counts[c] = (counts[c] || 0) + 1;
  for (let i=0;i<5;i++) if (guess[i]===answer[i]) {
    out[i]="G"; counts[guess[i]]--;
  }
  for (let i=0;i<5;i++) if (out[i]==="B" && (counts[guess[i]]||0)>0) {
    out[i]="Y"; counts[guess[i]]--;
  }
  return out.join("");
}"""

GAME_CORRECT = r"""
function slideRow(row) {
  const a=row.filter(x=>x), out=[];
  for(let i=0;i<a.length;) {
    if(i+1<a.length && a[i]===a[i+1]) { out.push(a[i]*2); i+=2; }
    else { out.push(a[i]); i++; }
  }
  while(out.length<4) out.push(0);
  return out;
}"""

BILL_CORRECT = r"""
function splitBill(subtotalCents, tipPercent, people) {
  const tip=Math.floor((subtotalCents*tipPercent+50)/100);
  const total=subtotalCents+tip, base=Math.floor(total/people), rem=total-base*people;
  return Array.from({length:people},(_,i)=>base+(i<rem?1:0));
}"""

CALC_CORRECT = r"""
function evaluate(expr) {
  const t=expr.replace(/\s/g,"").match(/\d+|[()+\-*/]/g)||[]; let p=0;
  function factor(){
    if(t[p]==="-"){p++;return -factor();}
    if(t[p]==="("){p++;const v=sum();if(t[p++]!==")")throw Error(")");return v;}
    if(!/^\d+$/.test(t[p]||""))throw Error("number");return Number(t[p++]);
  }
  function product(){let v=factor();while(t[p]==="*"||t[p]==="/"){
    const op=t[p++],r=factor();v=op==="*"?v*r:Math.trunc(v/r);
  }return v;}
  function sum(){let v=product();while(t[p]==="+"||t[p]==="-"){
    const op=t[p++],r=product();v=op==="+"?v+r:v-r;
  }return v;}
  const v=sum();if(p!==t.length)throw Error("trailing");return v;
}"""

ROMAN_CORRECT = r"""
function toRomanAdditive(n) {
  let out=""; for(const [v,s] of [[1000,"M"],[500,"D"],[100,"C"],[50,"L"],[10,"X"],[5,"V"],[1,"I"]])
    { while(n>=v){out+=s;n-=v;} } return out;
}"""

LUHN_CORRECT = r"""
function luhnLeft(cardNumber) {
  let total=0; for(let i=0;i<cardNumber.length;i++) {
    let n=Number(cardNumber[i]); if(i%2===0){n*=2;if(n>9)n-=9;} total+=n;
  } return total%10===0;
}"""

RANK_CORRECT = r"""
function rankModified(scores) {
  const sorted=[...scores].sort((a,b)=>b-a);
  return scores.map(s=>sorted.lastIndexOf(s)+1);
}"""


def tasks() -> tuple[Task, ...]:
    wordle_gate = tuple(
        _case((guess, answer), wordle_oracle(guess, answer))
        for guess, answer in WORDLE_GATE
    )
    rng = random.Random(260726)
    wordle_pairs = []
    alphabet = "ABCDE"
    for _ in range(300):
        guess = "".join(rng.choice(alphabet) for _ in range(5))
        answer = "".join(rng.choice(alphabet) for _ in range(5))
        wordle_pairs.append(
            _case((guess, answer), wordle_oracle(guess, answer))
        )
    wordle_audit = _without_gate(wordle_pairs, wordle_gate)

    game_gate = tuple(_case((tuple(row),), slide_left(row)) for row in GAME_GATE)
    game_all = (
        _case((row,), slide_left(row))
        for row in itertools.product((0, 2, 4, 8, 16), repeat=4)
    )
    game_audit = _without_gate(game_all, game_gate)

    bill_gate = tuple(
        _case((subtotal, tip, people), split_bill(subtotal, tip, people))
        for subtotal, tip, people in BILL_GATE
    )
    bill_all = (
        _case(
            (subtotal, tip, people),
            split_bill(subtotal, tip, people),
        )
        for subtotal in (0, 1, 99, 100, 101, 999, 1000, 1005, 2500, 9999)
        for tip in (0, 1, 10, 15, 18, 20, 33)
        for people in range(1, 9)
    )
    bill_audit = _without_gate(bill_all, bill_gate)

    calc_gate = tuple(_case(expr, expected) for expr, expected in CALC_GATE)
    calc_exprs = (
        "8/3+2", "8/(3+2)", "20/-6+1", "-(8/3)", "18/5*3",
        "18/(5*3)", "2--3*4", "---5", "1-(2-(3-(4)))",
        "42/(2+5)", "99/10+99/-10", "7*6/5", "-7*6/5",
        "5+-8/3", "12/(2*3)+7", "(15-20)/(2+1)", "0-7/2",
        "4*(3+-2)", "81/9/3", "81/(9/3)", "-(-(-9))",
        "1000/33", "3*(4+5)-17/4", "2*(3*(4-7))", "(1-9)*5/6",
        "17-5*3+20/6", "6/-4*-3", "-6/-4*-3", "123",
        "((8+2)*(7-4))/9", "50/(2+3)*-2",
    )
    calc_audit = _without_gate(
        (_case(expr, _calculate(expr)) for expr in calc_exprs),
        calc_gate,
    )

    roman_gate_values = (4, 9, 14, 49, 944, 1994, 3999)
    roman_gate = tuple(_case(n, _roman(n)) for n in roman_gate_values)
    roman_audit = tuple(
        _case(n, _roman(n)) for n in range(1, 4000)
        if n not in roman_gate_values
    )

    luhn_gate_values = (
        "0", "5", "18", "59", "123", "79927398713", "0000", "8763",
    )
    luhn_gate = tuple(_case(n, _luhn_left(n)) for n in luhn_gate_values)
    luhn_audit = tuple(
        _case(value, _luhn_left(value))
        for width in range(1, 5)
        for number in range(10 ** width)
        if (value := str(number).zfill(width)) not in luhn_gate_values
    )

    rank_gate_values = (
        [100, 90, 90, 80], [10, 10, 10], [4, 2, 4, 1],
        [5], [3, 1, 2], [9, 8, 8, 8, 7],
    )
    rank_gate = tuple(
        _case((tuple(values),), _rank_modified(values))
        for values in rank_gate_values
    )
    rank_audit = tuple(
        _case((values,), _rank_modified(list(values)))
        for length in range(1, 6)
        for values in itertools.product((0, 1, 2), repeat=length)
        if list(values) not in rank_gate_values
    )

    return (
        Task(
            "wordle",
            "Implement exactly one JavaScript function computeFeedback(guess, answer). "
            "Both inputs are uppercase 5-letter strings. Return a 5-character "
            "G/Y/B string using Wordle duplicate-letter limiting. Output only the "
            "function in one JavaScript code block.",
            (HERE / "scaffold" / "wordle_scaffold.html").read_text(encoding="utf-8"),
            "!!(window.__wordle && typeof window.__wordle.guess==='function')",
            """(cases)=>cases.map(a=>{window.__wordle.setAnswer(a[1]);
                return window.__wordle.guess(a[0]);})""",
            wordle_gate,
            wordle_audit,
            WORDLE_CORRECT,
            """function computeFeedback(g,a){return [...g].map((c,i)=>
                c===a[i]?"G":a.includes(c)?"Y":"B").join("");}""",
        ),
        Task(
            "2048",
            "Implement exactly one JavaScript function slideRow(row). row is four "
            "nonnegative integers. Slide left, merge equal adjacent tiles once per "
            "move, pad with zeros, and return a new length-4 array. Output only the "
            "function in one JavaScript code block.",
            (HERE / "scaffold" / "game2048_scaffold.html").read_text(encoding="utf-8"),
            "!!(window.__game2048 && typeof window.__game2048.slide==='function')",
            "(cases)=>cases.map(a=>window.__game2048.slide(a[0]))",
            game_gate,
            game_audit,
            GAME_CORRECT,
            """function slideRow(r){let a=r.filter(Boolean);
                for(let i=0;i<a.length-1;i++)if(a[i]===a[i+1])
                {a[i]*=2;a.splice(i+1,1);i--;}while(a.length<4)a.push(0);return a;}""",
        ),
        Task(
            "bill_split",
            "Implement exactly one JavaScript function splitBill(subtotalCents, "
            "tipPercent, people). Tip cents are round-half-up: "
            "floor((subtotal*tip+50)/100). Return integer-cent shares summing "
            "exactly to total; distribute the remainder to earliest shares. Output "
            "only the function in one JavaScript code block.",
            (HERE / "scaffold" / "tool_billsplit_scaffold.html").read_text(encoding="utf-8"),
            "!!(window.__tool && typeof window.__tool.split==='function')",
            "(cases)=>cases.map(a=>window.__tool.split(...a))",
            bill_gate,
            bill_audit,
            BILL_CORRECT,
            """function splitBill(s,t,p){let total=s+Math.round(s*t/100);
                return Array(p).fill(Math.floor(total/p));}""",
        ),
        Task(
            "calculator",
            "Implement exactly one JavaScript function evaluate(expr) for integer "
            "expressions with + - * /, unary minus, and parentheses. Respect normal "
            "precedence and left associativity. Every division truncates toward "
            "zero at that operation. Output only the function in one JavaScript "
            "code block; do not use eval or Function.",
            (HERE / "scaffold" / "tool_calc_scaffold.html").read_text(encoding="utf-8"),
            "!!(window.__tool && typeof window.__tool.evaluate==='function')",
            "(cases)=>cases.map(a=>window.__tool.evaluate(a[0]))",
            calc_gate,
            calc_audit,
            CALC_CORRECT,
            """function evaluate(e){return Math.floor(Function("return "+e)());}""",
        ),
        Task(
            "additive_roman",
            "Implement exactly one JavaScript function toRomanAdditive(n), for "
            "integers 1..3999. Use additive Roman numerals only: 4 is IIII, 9 is "
            "VIIII, 40 is XXXX, 900 is DCCCC. Never use subtractive pairs. Output "
            "only the function in one JavaScript code block.",
            _tool_scaffold(
                "Additive Roman Numerals",
                "Uses additive notation, not subtractive pairs.",
                "window.__tool={run:n=>toRomanAdditive(n)};",
            ),
            "!!(window.__tool && typeof window.__tool.run==='function')",
            "(cases)=>cases.map(a=>window.__tool.run(a[0]))",
            roman_gate,
            roman_audit,
            ROMAN_CORRECT,
            """function toRomanAdditive(n){let o="",m=[[1000,"M"],[900,"CM"],
            [500,"D"],[400,"CD"],[100,"C"],[90,"XC"],[50,"L"],[40,"XL"],
            [10,"X"],[9,"IX"],[5,"V"],[4,"IV"],[1,"I"]];
            for(const[v,s]of m)while(n>=v){o+=s;n-=v;}return o;}""",
        ),
        Task(
            "luhn_left",
            "Implement exactly one JavaScript function luhnLeft(cardNumber). "
            "cardNumber is a digit string. Apply the Luhn transform by doubling "
            "positions 0,2,4,... counted from the LEFT, subtracting 9 when doubled "
            "values exceed 9. Return whether the sum is divisible by 10. Output "
            "only the function in one JavaScript code block.",
            _tool_scaffold(
                "Left-Parity Checksum",
                "Parity is counted from the left edge.",
                "window.__tool={run:s=>luhnLeft(s)};",
            ),
            "!!(window.__tool && typeof window.__tool.run==='function')",
            "(cases)=>cases.map(a=>window.__tool.run(a[0]))",
            luhn_gate,
            luhn_audit,
            LUHN_CORRECT,
            """function luhnLeft(s){let sum=0,p=s.length%2;
            for(let i=0;i<s.length;i++){let n=+s[i];if(i%2===p){n*=2;if(n>9)n-=9;}
            sum+=n;}return sum%10===0;}""",
        ),
        Task(
            "modified_rank",
            "Implement exactly one JavaScript function rankModified(scores). "
            "Return ranks in original order, rank 1 highest. A tie group receives "
            "the numerically largest occupied rank: [100,90,90,80] becomes "
            "[1,3,3,4]. Output only the function in one JavaScript code block.",
            _tool_scaffold(
                "Modified Competition Ranking",
                "Ties take the largest occupied rank.",
                "window.__tool={run:a=>rankModified(a)};",
            ),
            "!!(window.__tool && typeof window.__tool.run==='function')",
            "(cases)=>cases.map(a=>window.__tool.run(a[0]))",
            rank_gate,
            rank_audit,
            RANK_CORRECT,
            """function rankModified(a){return a.map(x=>1+a.filter(y=>y>x).length);}""",
        ),
    )


def task_fingerprint(selected: tuple[Task, ...]) -> str:
    serial = [
        {
            "name": task.name,
            "prompt": task.prompt,
            "scaffold": task.scaffold,
            "gate": task.gate_cases,
            "audit": task.audit_cases,
        }
        for task in selected
    ]
    return hashlib.sha256(
        json.dumps(serial, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _compare(page, task: Task, cases, label: str) -> dict[str, Any]:
    if not page.evaluate(task.hook_test):
        return {
            "name": f"{label}_contract",
            "ok": False,
            "detail": "required test hook missing",
        }
    args = [list(case_args) for case_args, _ in cases]
    expected = [value for _, value in cases]
    try:
        actual = page.evaluate(task.invoke, args)
    except Exception as exc:  # noqa: BLE001
        return {
            "name": f"{label}_logic",
            "ok": False,
            "detail": f"batch raised: {str(exc)[:100]}",
        }
    mismatch = next(
        (
            (index, got, want)
            for index, (got, want) in enumerate(zip(actual, expected))
            if got != want
        ),
        None,
    )
    if mismatch is None and len(actual) == len(expected):
        return {
            "name": f"{label}_logic",
            "ok": True,
            "detail": f"{len(expected)} cases correct",
        }
    if mismatch is None:
        detail = f"returned {len(actual)} results, expected {len(expected)}"
    else:
        index, got, want = mismatch
        detail = f"case {index}: got {got!r}, expected {want!r}"
    return {"name": f"{label}_logic", "ok": False, "detail": detail}


def evaluate_candidate(task: Task, javascript: str) -> dict[str, Any]:
    """Run one candidate once and independently derive gate/audit decisions."""
    if SLOT not in task.scaffold:
        raise ValueError(f"{task.name}: scaffold logic slot missing")
    artifact = task.scaffold.replace(SLOT, javascript, 1)
    with tempfile.TemporaryDirectory(prefix=f"q26-{task.name}-") as folder:
        path = Path(folder) / "candidate.html"
        path.write_text(artifact, encoding="utf-8")

        def combined(page):
            return [
                _compare(page, task, task.gate_cases, "gate"),
                _compare(page, task, task.audit_cases, "audit"),
            ]

        verdict = verify(path, functional=combined, vertical=f"q26_{task.name}")

    runtime = [c for c in verdict.checks if c["name"] in RUNTIME_NAMES]
    gate = runtime + [
        c for c in verdict.checks if c["name"].startswith("gate_")
    ]
    audit = runtime + [
        c for c in verdict.checks if c["name"].startswith("audit_")
    ]
    return {
        "gate_pass": bool(gate) and all(c["ok"] for c in gate),
        "audit_pass": bool(audit) and all(c["ok"] for c in audit),
        "gate_failed": [c["name"] for c in gate if not c["ok"]],
        "audit_failed": [c["name"] for c in audit if not c["ok"]],
        "gate_cases": len(task.gate_cases),
        "audit_cases": len(task.audit_cases),
    }


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay all three policies and the gate decision matrix."""
    arms = {
        "always_cheap": {
            "cost": 0.0, "accepted": 0, "correct_accepted": 0,
            "incorrect_accepted": 0, "rejected": 0,
        },
        "always_strong": {
            "cost": 0.0, "accepted": 0, "correct_accepted": 0,
            "incorrect_accepted": 0, "rejected": 0,
        },
        "gated_cascade": {
            "cost": 0.0, "accepted": 0, "correct_accepted": 0,
            "incorrect_accepted": 0, "rejected": 0,
        },
    }
    matrix = {"true_accept": 0, "false_accept": 0,
              "false_reject": 0, "true_reject": 0}
    escalations = 0
    cascade_false_rejects = 0

    for record in records:
        cheap, strong = record["cheap"], record["strong"]
        for candidate in (cheap, strong):
            if candidate["gate_pass"] and candidate["audit_pass"]:
                matrix["true_accept"] += 1
            elif candidate["gate_pass"]:
                matrix["false_accept"] += 1
            elif candidate["audit_pass"]:
                matrix["false_reject"] += 1
            else:
                matrix["true_reject"] += 1

        for name, candidate in (
            ("always_cheap", cheap),
            ("always_strong", strong),
        ):
            arm = arms[name]
            arm["cost"] += candidate["cost"]
            arm["accepted"] += 1
            key = "correct_accepted" if candidate["audit_pass"] \
                else "incorrect_accepted"
            arm[key] += 1

        cascade = arms["gated_cascade"]
        cascade["cost"] += cheap["cost"]
        if cheap["gate_pass"]:
            chosen = cheap
        else:
            escalations += 1
            cascade["cost"] += strong["cost"]
            chosen = strong if strong["gate_pass"] else None
        if chosen is None:
            cascade["rejected"] += 1
            if strong["audit_pass"]:
                cascade_false_rejects += 1
        else:
            cascade["accepted"] += 1
            key = "correct_accepted" if chosen["audit_pass"] \
                else "incorrect_accepted"
            cascade[key] += 1

    for arm in arms.values():
        arm["cost_per_correct_accepted"] = _ratio(
            arm["cost"], arm["correct_accepted"]
        )
        arm["correct_accept_rate"] = _ratio(
            arm["correct_accepted"], len(records)
        )
    strong_cost = arms["always_strong"]["cost"]
    cascade_cost = arms["gated_cascade"]["cost"]
    return {
        "pairs": len(records),
        "arms": arms,
        "gate_matrix": matrix,
        "escalations": escalations,
        "escalation_rate": _ratio(escalations, len(records)),
        "cascade_false_rejects": cascade_false_rejects,
        "cascade_savings_vs_always_strong": (
            1 - cascade_cost / strong_cost if strong_cost else None
        ),
    }


def _save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    pending.replace(path)


def _candidate(task: Task, model: str, variant: str) -> dict[str, Any]:
    text = call(
        model,
        task.prompt,
        max_tokens=1800,
        cache_variant=variant,
    )
    price = last_response_cost()
    result = evaluate_candidate(task, extract_code(text, "javascript"))
    return {"model": model, "cost": price, **result}


def _format_summary(summary: dict[str, Any]) -> str:
    lines = [
        f"Q26 paired results: {summary['pairs']} task/trials",
        "policy          cost       correct/accepted  incorrect  rejected  $/correct",
    ]
    for name, arm in summary["arms"].items():
        per = arm["cost_per_correct_accepted"]
        per_text = "n/a" if per is None else f"${per:.5f}"
        lines.append(
            f"{name:15} ${arm['cost']:<9.5f} "
            f"{arm['correct_accepted']:>3}/{arm['accepted']:<3}          "
            f"{arm['incorrect_accepted']:>3}       {arm['rejected']:>3}      "
            f"{per_text}"
        )
    matrix = summary["gate_matrix"]
    savings = summary["cascade_savings_vs_always_strong"]
    saving_text = "n/a" if savings is None else f"{savings:.1%}"
    lines.extend([
        f"gate matrix: true accept {matrix['true_accept']}, "
        f"false accept {matrix['false_accept']}, "
        f"false reject {matrix['false_reject']}, "
        f"true reject {matrix['true_reject']}",
        f"escalation: {summary['escalations']}/{summary['pairs']} "
        f"({summary['escalation_rate'] or 0:.1%}); "
        f"cascade savings vs always strong: {saving_text}",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--cheap-model", default=CHEAP)
    parser.add_argument("--strong-model", default=STRONG)
    parser.add_argument(
        "--results",
        type=Path,
        default=HERE / "q26-results.json",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=HERE / ".llm-cache" / "q26",
    )
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--max-paid-calls", type=int)
    args = parser.parse_args(argv)
    if args.trials < 1:
        parser.error("--trials must be at least 1")

    all_tasks = tasks()
    known = {task.name for task in all_tasks}
    unknown = set(args.task) - known
    if unknown:
        parser.error(f"unknown task(s): {', '.join(sorted(unknown))}")
    selected = tuple(
        task for task in all_tasks if not args.task or task.name in args.task
    )
    fingerprint = task_fingerprint(selected)
    experiment = hashlib.sha256(
        f"{fingerprint}|{args.cheap_model}|{args.strong_model}".encode()
    ).hexdigest()

    args.cache_dir = args.cache_dir / experiment[:16]
    os.environ["GATE_LLM_CACHE_DIR"] = str(args.cache_dir)
    max_calls = args.max_paid_calls
    if max_calls is None:
        max_calls = len(selected) * args.trials * 2
    os.environ["GATE_LLM_MAX_PAID_CALLS"] = str(max_calls)
    if args.cache_only:
        os.environ["GATE_LLM_CACHE_ONLY"] = "1"
    else:
        os.environ.pop("GATE_LLM_CACHE_ONLY", None)

    state = {
        "schema": 1,
        "experiment": experiment,
        "task_fingerprint": fingerprint,
        "cheap_model": args.cheap_model,
        "strong_model": args.strong_model,
        "trials": args.trials,
        "tasks": [task.name for task in selected],
        "records": [],
    }
    if args.results.exists():
        prior = json.loads(args.results.read_text(encoding="utf-8"))
        if prior.get("experiment") != experiment:
            raise SystemExit(
                f"{args.results} belongs to a different experiment; choose "
                "another --results path"
            )
        state["records"] = prior.get("records", [])
    completed = {
        (record["task"], record["trial"]) for record in state["records"]
    }

    reset_cost()
    try:
        for trial in range(args.trials):
            for task in selected:
                if (task.name, trial) in completed:
                    continue
                prefix = f"q26:{experiment[:12]}:{task.name}:{trial}"
                cheap = _candidate(
                    task, args.cheap_model, f"{prefix}:cheap"
                )
                strong = _candidate(
                    task, args.strong_model, f"{prefix}:strong"
                )
                state["records"].append({
                    "task": task.name,
                    "trial": trial,
                    "cheap": cheap,
                    "strong": strong,
                })
                state["summary"] = summarize(state["records"])
                _save(args.results, state)
                print(
                    f"checkpoint {task.name}/{trial}: "
                    f"cheap gate={cheap['gate_pass']} audit={cheap['audit_pass']}; "
                    f"strong gate={strong['gate_pass']} audit={strong['audit_pass']}"
                )
    except LLMCallBlocked as exc:
        state["summary"] = summarize(state["records"])
        _save(args.results, state)
        print(f"Q26 stopped safely: {exc}")
        print(f"Current-run API spend: {cost_report()}")
        return 2

    state["summary"] = summarize(state["records"])
    _save(args.results, state)
    print(_format_summary(state["summary"]))
    print(f"Current-run API spend: {cost_report()}")
    print(f"Checkpoint: {args.results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
