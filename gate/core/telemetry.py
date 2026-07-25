"""Telemetry: durable record of every verdict, plus the alarms from
`docs/gate-operations.md` §3.

Flag rate is not just a cost line -- it is the live spec-difficulty signal
(D24). Measured baselines: ~3% on canonical specs, ~50% on prior-fighting ones.
Excursions in EITHER direction matter; a suspiciously low rate on a new vertical
usually means the ensemble lacks tier diversity and literally cannot disagree.
"""

from __future__ import annotations

import json
import time
from collections import Counter

from .config import ROOT, get_logger

log = get_logger("gate.telemetry")
LOG_PATH = ROOT / "gate" / "telemetry.jsonl"

# Baselines from archive/gate-experiments/{stress,oracle}_consensus.py
FLAG_RATE_CEILING = 0.60      # above this the spec is fighting the models
FLAG_RATE_FLOOR = 0.005       # below this on a NEW vertical: suspicious


def record(event: str, **fields) -> dict:
    """Append one event. Never raises -- telemetry must not break the gate."""
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **fields}
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except OSError as exc:
        log.warning("telemetry write failed: %s", exc)
    return row


def read(vertical: str | None = None, event: str | None = None) -> list[dict]:
    if not LOG_PATH.exists():
        return []
    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if vertical and r.get("vertical") != vertical:
            continue
        if event and r.get("event") != event:
            continue
        rows.append(r)
    return rows


def stats(vertical: str | None = None) -> dict:
    rows = read(vertical=vertical, event="verify")
    n = len(rows)
    passed = sum(1 for r in rows if r.get("passed"))
    oracle_rows = read(vertical=vertical, event="oracle")
    drafted = sum(r.get("drafted", 0) for r in oracle_rows)
    disputed = sum(r.get("disputed", 0) for r in oracle_rows)
    fails = Counter()
    for r in rows:
        for c in r.get("failed", []):
            fails[c] += 1
    return {
        "verifications": n,
        "pass_rate": (passed / n) if n else None,
        "oracle_cases": drafted,
        "flag_rate": (disputed / drafted) if drafted else None,
        "top_failures": fails.most_common(5),
    }


def alarms(vertical: str | None = None, is_new: bool = False) -> list[str]:
    """Ops-doc §3 excursions. Returns human-readable alarm strings."""
    s = stats(vertical)
    out = []
    fr = s["flag_rate"]
    if fr is None:
        return out
    if fr > FLAG_RATE_CEILING:
        out.append(f"flag rate {fr:.0%} exceeds {FLAG_RATE_CEILING:.0%}: the spec "
                   f"is fighting the models -- rewrite it, or pin this vertical "
                   f"to the strong tier and drop the cheap pre-filter")
    if is_new and fr < FLAG_RATE_FLOOR:
        out.append(f"flag rate {fr:.1%} is suspiciously low for a NEW vertical: "
                   f"check the oracle ensemble is tier-diverse (N samples of one "
                   f"model is one opinion, not N)")
    if s["pass_rate"] is not None and s["verifications"] >= 10 \
            and s["pass_rate"] < 0.5:
        out.append(f"pass rate {s['pass_rate']:.0%} over "
                   f"{s['verifications']} runs: the cheap tier may not be viable "
                   f"for this vertical")
    return out
