"""Zero-credit regression for the public manifest and bundled demonstrations."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate.core.doctor import doctor_report
from gate.core.manifest import ManifestError, load_manifest, verify_manifest
from gate.cli import main as cli_main

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

        def quiet_cli(arguments: list[str]) -> int:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return cli_main(arguments)

        runtime_starter = root / "runtime-starter.json"
        assert quiet_cli([
            "init", str(artifact), "--output", str(runtime_starter), "--json",
        ]) == 0
        runtime_manifest = load_manifest(runtime_starter)
        assert runtime_manifest.runtime_only
        _, runtime_verdict = verify_manifest(runtime_starter)
        assert runtime_verdict.passed, runtime_verdict.summary()
        original_starter = runtime_starter.read_bytes()
        assert quiet_cli([
            "init", str(artifact), "--output", str(runtime_starter),
        ]) == 2
        assert runtime_starter.read_bytes() == original_starter
        assert quiet_cli([
            "init",
            str(artifact),
            "--output",
            str(runtime_starter),
            "--name",
            "replaced-starter",
            "--force",
        ]) == 0
        assert load_manifest(runtime_starter).name == "replaced-starter"

        functional_starter = root / "functional-starter.json"
        assert quiet_cli([
            "init",
            str(artifact),
            "--output",
            str(functional_starter),
            "--hook",
            "window.__turing.add",
            "--domain-schema",
            '{"args":[{"type":"number"},{"type":"number"}]}',
            "--number-tolerance",
            "0.000000001",
            "--case",
            '{"label":"integer sum","args":[2,3],"expected":5}',
            "--case",
            '{"label":"negative sum","args":[-2,1],"expected":-1}',
        ]) == 0
        generated_manifest, generated_verdict = verify_manifest(
            functional_starter
        )
        assert not generated_manifest.runtime_only
        assert len(generated_manifest.cases) == 2
        assert generated_verdict.passed, generated_verdict.summary()

        # Refuse ambiguous/unsafe generation and leave no partial output.
        missing_hook = root / "missing-hook.json"
        assert quiet_cli([
            "init",
            str(artifact),
            "--output",
            str(missing_hook),
            "--case",
            '{"args":[1,2],"expected":3}',
        ]) == 2
        assert not missing_hook.exists()

        invalid_case = root / "invalid-case.json"
        assert quiet_cli([
            "init",
            str(artifact),
            "--output",
            str(invalid_case),
            "--hook",
            "window.__turing.add",
            "--case",
            '{"args": [1, 2], "expected": NaN}',
        ]) == 2
        assert not invalid_case.exists()

        nested = root / "nested"
        nested.mkdir()
        escaped_output = nested / "turing.json"
        assert quiet_cli([
            "init",
            str(artifact),
            "--output",
            str(escaped_output),
        ]) == 2
        assert not escaped_output.exists()
        assert not list(root.glob(".turing-starter-*.json"))

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
        diagnostics = doctor_report("test")
        assert diagnostics["ready"], diagnostics
        assert {row["name"] for row in diagnostics["checks"]} >= {
            "local_state", "loopback", "playwright", "chromium", "browser_launch"
        }
        old_browser_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(root / "missing-browser")
        missing_browser = doctor_report("test")
        assert not missing_browser["ready"], missing_browser
        assert {
            row["name"] for row in missing_browser["checks"] if not row["ok"]
        } == {"chromium", "browser_launch"}
        if old_browser_path is None:
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        else:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = old_browser_path

    if previous is None:
        os.environ.pop("GATE_TELEMETRY_PATH", None)
    else:
        os.environ["GATE_TELEMETRY_PATH"] = previous
    print("OFFLINE PUBLIC MANIFEST: PASS")
    print("  valid user manifest accepted")
    print("  directory escape rejected")
    print("  malformed domain schema rejected")
    print("  init runtime-only starter created without overstating coverage")
    print("  init functional starter verified against explicit cases")
    print("  init overwrite, malformed JSON, and path escape rejected")
    print("  Wordle duplicate bug caught")
    print("  calculator negative-division bug caught")
    print("  four-vector exfiltration caught")
    print("  local-only telemetry override honored")
    print("  doctor environment diagnostics passed")
    print("  doctor missing-browser failure diagnosed")
    print("  API spend: $0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
