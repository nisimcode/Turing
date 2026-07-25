"""Zero-credit regression for the optional PySide6 owner interface.

Run headlessly:

    QT_QPA_PLATFORM=offscreen uv run --extra gui python gate/offline_gui_check.py
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate import cli  # noqa: E402

assert "PySide6" not in sys.modules, "base CLI imported the optional GUI eagerly"

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gate.core.manifest import ManifestError, load_manifest  # noqa: E402
from gate.gui import GateWindow, discover_artifacts  # noqa: E402


HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Adder</title></head>
<body>
  <main>
    <h1>Adder</h1>
    <label>First number <input id="first" type="number"></label>
    <button id="add" type="button">Add</button>
    <output id="result">Ready</output>
  </main>
  <script>
    window.__turing = { add: (left, right) => left + right };
    document.getElementById("add").addEventListener("click", () => {
      document.getElementById("result").value = "Ready";
    });
  </script>
</body>
</html>
"""


def _set_cell(window: GateWindow, row: int, column: int, value: str) -> None:
    item = window.case_table.item(row, column)
    assert item is not None
    item.setText(value)


def _wait_for_verification(window: GateWindow) -> None:
    thread = window._thread
    assert thread is not None
    loop = QEventLoop()
    timed_out = {"value": False}

    def timeout() -> None:
        timed_out["value"] = True
        loop.quit()

    thread.finished.connect(loop.quit)
    QTimer.singleShot(30_000, timeout)
    loop.exec()
    QApplication.processEvents()
    assert not timed_out["value"], "GUI verification worker timed out"
    assert window._thread is None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", type=Path)
    args = parser.parse_args(argv)

    os.environ.setdefault("GATE_TELEMETRY_PATH", os.devnull)
    app = QApplication.instance() or QApplication(["turing-gate-gui-check"])
    if args.screenshot is not None and sys.platform == "win32":
        font_path = Path("C:/Windows/Fonts/segoeui.ttf")
        if font_path.is_file():
            QFontDatabase.addApplicationFont(str(font_path))
            app.setFont(QFont("Segoe UI", 9))

    with tempfile.TemporaryDirectory(prefix="turing-gui-") as folder:
        root = Path(folder)
        artifact = root / "adder.html"
        artifact.write_text(HTML, encoding="utf-8")
        ignored = root / "node_modules" / "decoy.html"
        ignored.parent.mkdir()
        ignored.write_text(HTML, encoding="utf-8")
        hidden = root / ".private" / "decoy.html"
        hidden.parent.mkdir()
        hidden.write_text(HTML, encoding="utf-8")

        assert discover_artifacts(root) == [artifact.resolve()]
        try:
            discover_artifacts(root / "missing")
        except ManifestError as exc:
            assert "not found" in str(exc)
        else:
            raise AssertionError("missing GUI project directory was accepted")

        window = GateWindow(root)
        assert window.artifact_combo.count() == 1
        assert window.artifact_combo.currentText() == "adder.html"
        window.name_edit.setText("adder-owner-check")
        window.description_edit.setText("Protect addition behavior.")
        window.hook_edit.setText("window.__turing.add")
        window.schema_edit.setPlainText(
            '{"args":[{"type":"number"},{"type":"number"}]}'
        )
        _set_cell(window, 0, 0, "positive integers")
        _set_cell(window, 0, 1, "[2, 3]")
        _set_cell(window, 0, 2, "5")
        window.add_case("negative value", "[-2, 5]", "3")

        manifest_path = window._save_manifest()
        assert manifest_path == root / "turing.json"
        manifest = load_manifest(manifest_path)
        assert manifest.hook == "window.__turing.add"
        assert len(manifest.cases) == 2

        _set_cell(window, 0, 1, '{"not":"an array"}')
        try:
            window.case_values()
        except ManifestError as exc:
            assert "JSON array" in str(exc)
        else:
            raise AssertionError("non-array GUI arguments were accepted")
        _set_cell(window, 0, 1, "[2, 3]")

        window.start_verification(manifest_path, runtime_only=False)
        _wait_for_verification(window)
        assert window.result_banner.text() == "ACCEPTED"
        assert window.result_table.rowCount() > 0

        if args.screenshot is not None:
            destination = args.screenshot.resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            window.show()
            app.processEvents()
            assert window.grab().save(str(destination))
            window.hide()

        window.close()
        app.processEvents()

    assert cli.main(["ui", "--check", "."]) == 0
    print("OPTIONAL GUI CHECK: PASS")
    print("  lazy base import + artifact discovery: PASS")
    print("  contract entry + safe manifest save: PASS")
    print("  background functional verification: PASS")
    print("  API spend: $0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
