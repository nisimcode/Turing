"""Zero-credit regression for the public manifest and bundled demonstrations."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core.manifest import ManifestError, load_manifest, verify_manifest

HERE = Path(__file__).resolve().parent


def main() -> int:
    previous = os.environ.get("GATE_TELEMETRY_PATH")
    with tempfile.TemporaryDirectory(prefix="turing-manifest-") as folder:
        root = Path(folder)
        os.environ["GATE_TELEMETRY_PATH"] = str(root / "telemetry.jsonl")
        artifact = root / "adder.html"
        artifact.write_text(
            """<!doctype html><html><body><main><h1>Adder</h1>
            <input id="a"><button id="go">Add</button><div id="out">ready</div>
            </main><script>
            window.__turing={add:(a,b)=>a+b};
            document.getElementById('go').onclick=()=>{};
            </script></body></html>""",
            encoding="utf-8",
        )
        manifest_path = root / "turing.json"
        manifest_path.write_text(
            json.dumps({
                "schema_version": 1,
                "name": "adder",
                "artifact": "adder.html",
                "hook": "window.__turing.add",
                "domain_schema": {
                    "args": [{"type": "number"}, {"type": "number"}],
                },
                "number_tolerance": 1e-9,
                "cases": [
                    {"label": "integers", "args": [2, 3], "expected": 5},
                    {
                        "label": "floating point",
                        "args": [0.1, 0.2],
                        "expected": 0.3,
                    },
                ],
            }),
            encoding="utf-8",
        )

        manifest, good = verify_manifest(manifest_path)
        assert manifest.name == "adder"
        assert good.passed, good.summary()
        assert {check["name"] for check in good.checks} >= {
            "manifest_contract", "manifest_cases"
        }

        escape = root / "escape.json"
        escape.write_text(
            json.dumps({
                "schema_version": 1,
                "name": "escape",
                "artifact": "../outside.html",
            }),
            encoding="utf-8",
        )
        try:
            load_manifest(escape)
        except ManifestError as exc:
            assert "stay inside" in str(exc)
        else:
            raise AssertionError("manifest directory escape was accepted")

        malformed = root / "malformed-schema.json"
        malformed.write_text(
            json.dumps({
                "schema_version": 1,
                "name": "malformed-schema",
                "artifact": "adder.html",
                "hook": "window.__turing.add",
                "domain_schema": {
                    "args": [{"type": "number", "minimum": "zero"}],
                },
                "cases": [{"args": [1], "expected": 1}],
            }),
            encoding="utf-8",
        )
        try:
            load_manifest(malformed)
        except ManifestError as exc:
            assert "invalid domain_schema" in str(exc)
        else:
            raise AssertionError("malformed domain schema was accepted")

        expected = {
            "wordle": "manifest_cases",
            "calculator": "manifest_cases",
            "exfiltration": "no_outbound_requests",
        }
        for name, failed_check in expected.items():
            _, verdict = verify_manifest(HERE / "demos" / f"{name}.json")
            assert not verdict.passed, f"{name} known-bad demo unexpectedly passed"
            assert failed_check in verdict.failed_checks(), (
                name, verdict.failed_checks()
            )

        assert (root / "telemetry.jsonl").exists()

    if previous is None:
        os.environ.pop("GATE_TELEMETRY_PATH", None)
    else:
        os.environ["GATE_TELEMETRY_PATH"] = previous
    print("OFFLINE PUBLIC MANIFEST: PASS")
    print("  valid user manifest accepted")
    print("  directory escape rejected")
    print("  malformed domain schema rejected")
    print("  Wordle duplicate bug caught")
    print("  calculator negative-division bug caught")
    print("  four-vector exfiltration caught")
    print("  local-only telemetry override honored")
    print("  API spend: $0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
