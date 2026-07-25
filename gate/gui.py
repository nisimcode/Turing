"""Optional PySide6 desktop interface for Turing Gate."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .core.manifest import ManifestError, load_manifest, verify_manifest
from .core.starter import create_starter_manifest
from .core.verify import verify

IGNORED_DIRECTORIES = {
    ".git",
    ".turing",
    ".venv",
    "__pycache__",
    "archive",
    "build",
    "dist",
    "node_modules",
}
MAX_ARTIFACTS = 500


def discover_artifacts(project_root: str | Path) -> list[Path]:
    """Return confined HTML files without descending into generated trees."""
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ManifestError(f"project directory not found: {root}")
    found: list[Path] = []
    for current, directories, files in os.walk(root):
        directories[:] = sorted(
            name for name in directories
            if name not in IGNORED_DIRECTORIES and not name.startswith(".")
        )
        for filename in sorted(files):
            if Path(filename).suffix.lower() not in {".html", ".htm"}:
                continue
            candidate = (Path(current) / filename).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                continue
            found.append(candidate)
            if len(found) >= MAX_ARTIFACTS:
                return found
    return found


def _decode_json(value: str, field: str):
    def reject(constant: str):
        raise ValueError(f"{field} cannot contain {constant}")

    try:
        return json.loads(value, parse_constant=reject)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{field}: invalid JSON at column {exc.colno}: {exc.msg}"
        ) from exc


class VerifyWorker(QObject):
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, target: Path, runtime_only: bool):
        super().__init__()
        self.target = target
        self.runtime_only = runtime_only

    @Slot()
    def run(self) -> None:
        try:
            if self.runtime_only:
                verdict = verify(self.target)
                result = {
                    "name": self.target.stem,
                    "runtime_only": True,
                    "passed": verdict.passed,
                    "checks": verdict.checks,
                }
            else:
                manifest, verdict = verify_manifest(self.target)
                result = {
                    "name": manifest.name,
                    "runtime_only": manifest.runtime_only,
                    "passed": verdict.passed,
                    "checks": verdict.checks,
                }
            self.completed.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(
                " ".join(str(exc).split()) or type(exc).__name__
            )


class GateWindow(QMainWindow):
    """One-window owner workflow: choose, describe, save, verify."""

    def __init__(self, project_root: str | Path):
        super().__init__()
        self.project_root = Path(project_root).resolve()
        if not self.project_root.is_dir():
            raise ManifestError(
                f"project directory not found: {self.project_root}"
            )
        self._artifacts: list[Path] = []
        self._thread: QThread | None = None
        self._worker: VerifyWorker | None = None
        self._confirmed_replace: Path | None = None

        self.setWindowTitle("Turing Gate")
        self.setMinimumSize(1040, 720)
        self.resize(1240, 820)
        self._build_ui()
        self._apply_style()
        self.refresh_artifacts()

    def _build_ui(self) -> None:
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(14)

        heading_row = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("Turing Gate")
        title.setObjectName("title")
        subtitle = QLabel(
            "Verify the critical behavior of a self-contained HTML tool."
        )
        subtitle.setObjectName("subtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        heading_row.addLayout(heading)
        heading_row.addStretch()
        self.project_button = QPushButton("Choose folder")
        self.project_button.clicked.connect(self.choose_project)
        heading_row.addWidget(self.project_button)
        outer.addLayout(heading_row)

        path_row = QHBoxLayout()
        path_label = QLabel("Project")
        path_label.setObjectName("fieldLabel")
        self.project_path = QLineEdit(str(self.project_root))
        self.project_path.setReadOnly(True)
        self.refresh_button = QPushButton("Refresh files")
        self.refresh_button.clicked.connect(self.refresh_artifacts)
        path_row.addWidget(path_label)
        path_row.addWidget(self.project_path, 1)
        path_row.addWidget(self.refresh_button)
        outer.addLayout(path_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_contract_panel())
        splitter.addWidget(self._build_results_panel())
        splitter.setSizes([700, 480])
        outer.addWidget(splitter, 1)

        self.setCentralWidget(container)

    def _panel(self, title_text: str, description: str) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = QLabel(title_text)
        title.setObjectName("panelTitle")
        detail = QLabel(description)
        detail.setWordWrap(True)
        detail.setObjectName("panelDetail")
        layout.addWidget(title)
        layout.addWidget(detail)
        return panel, layout

    def _build_contract_panel(self) -> QFrame:
        panel, layout = self._panel(
            "Verification contract",
            "Choose the HTML file, identify its browser function, and state "
            "the results you expect. Turing Gate will not invent these values.",
        )

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        artifact_row = QHBoxLayout()
        self.artifact_combo = QComboBox()
        self.artifact_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.artifact_combo.currentIndexChanged.connect(
            self.artifact_changed
        )
        artifact_row.addWidget(self.artifact_combo, 1)
        form.addRow("HTML artifact", artifact_row)

        self.manifest_path = QLabel("No artifact selected")
        self.manifest_path.setObjectName("pathHint")
        self.manifest_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow("Manifest", self.manifest_path)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Example: shipping-calculator")
        form.addRow("Name", self.name_edit)

        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText(
            "What behavior does this contract protect?"
        )
        form.addRow("Description", self.description_edit)

        self.hook_edit = QLineEdit()
        self.hook_edit.setPlaceholderText(
            "window.__turing.calculateShipping"
        )
        form.addRow("Browser hook", self.hook_edit)

        self.tolerance = QDoubleSpinBox()
        self.tolerance.setDecimals(12)
        self.tolerance.setRange(0.0, 1_000_000.0)
        self.tolerance.setSingleStep(0.000001)
        self.tolerance.setToolTip(
            "Absolute tolerance for floating-point comparisons."
        )
        form.addRow("Number tolerance", self.tolerance)
        layout.addLayout(form)

        schema_label = QLabel("Argument domain (optional JSON)")
        schema_label.setObjectName("sectionLabel")
        self.schema_edit = QPlainTextEdit()
        self.schema_edit.setPlaceholderText(
            '{"args":[{"type":"number","minimum":0}]}'
        )
        self.schema_edit.setMaximumHeight(88)
        self.schema_edit.setTabChangesFocus(True)
        layout.addWidget(schema_label)
        layout.addWidget(self.schema_edit)

        case_heading = QHBoxLayout()
        case_label = QLabel("Expected cases")
        case_label.setObjectName("sectionLabel")
        case_help = QLabel("Arguments and expected values use JSON.")
        case_help.setObjectName("pathHint")
        case_heading.addWidget(case_label)
        case_heading.addStretch()
        case_heading.addWidget(case_help)
        layout.addLayout(case_heading)

        self.case_table = QTableWidget(0, 3)
        self.case_table.setHorizontalHeaderLabels(
            ["Label", "Arguments JSON", "Expected JSON"]
        )
        self.case_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.case_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.case_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.case_table.verticalHeader().setVisible(False)
        self.case_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.case_table.setAlternatingRowColors(True)
        self.case_table.setMinimumHeight(190)
        layout.addWidget(self.case_table, 1)

        case_buttons = QHBoxLayout()
        self.add_case_button = QPushButton("Add case")
        self.add_case_button.clicked.connect(self.add_case)
        self.remove_case_button = QPushButton("Remove selected")
        self.remove_case_button.clicked.connect(self.remove_cases)
        self.load_button = QPushButton("Reload existing")
        self.load_button.clicked.connect(self.load_existing_manifest)
        case_buttons.addWidget(self.add_case_button)
        case_buttons.addWidget(self.remove_case_button)
        case_buttons.addStretch()
        case_buttons.addWidget(self.load_button)
        layout.addLayout(case_buttons)

        action_row = QHBoxLayout()
        self.page_button = QPushButton("Check page only")
        self.page_button.setToolTip(
            "Check loading, visible UI, errors, and outbound requests without "
            "claiming functional correctness."
        )
        self.page_button.clicked.connect(self.run_page_check)
        self.save_button = QPushButton("Save manifest")
        self.save_button.clicked.connect(self.save_manifest)
        self.verify_button = QPushButton("Save and verify")
        self.verify_button.setObjectName("primaryButton")
        self.verify_button.clicked.connect(self.save_and_verify)
        action_row.addWidget(self.page_button)
        action_row.addStretch()
        action_row.addWidget(self.save_button)
        action_row.addWidget(self.verify_button)
        layout.addLayout(action_row)
        return panel

    def _build_results_panel(self) -> QFrame:
        panel, layout = self._panel(
            "Result",
            "A functional acceptance requires every runtime, containment, "
            "contract, and expected-case check to pass.",
        )
        self.result_banner = QLabel("Ready")
        self.result_banner.setObjectName("resultIdle")
        self.result_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_banner.setMinimumHeight(58)
        layout.addWidget(self.result_banner)

        self.result_summary = QLabel(
            "Select an artifact and use “Save and verify.”"
        )
        self.result_summary.setWordWrap(True)
        self.result_summary.setObjectName("panelDetail")
        layout.addWidget(self.result_summary)

        self.result_table = QTableWidget(0, 3)
        self.result_table.setHorizontalHeaderLabels(
            ["Check", "Status", "Detail"]
        )
        self.result_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.result_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.result_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.result_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.result_table.setAlternatingRowColors(True)
        layout.addWidget(self.result_table, 1)

        note = QLabel(
            "Page-only checks are diagnostic. They do not establish that "
            "calculations, validators, or game rules are correct."
        )
        note.setObjectName("warningNote")
        note.setWordWrap(True)
        layout.addWidget(note)
        return panel

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #111827;
                color: #e5e7eb;
                font-family: "Segoe UI", "Inter", sans-serif;
                font-size: 13px;
            }
            QLabel#title {
                font-size: 28px;
                font-weight: 700;
                color: #f9fafb;
            }
            QLabel#subtitle, QLabel#panelDetail, QLabel#pathHint {
                color: #9ca3af;
            }
            QLabel#panelTitle {
                font-size: 18px;
                font-weight: 650;
                color: #f9fafb;
            }
            QLabel#sectionLabel, QLabel#fieldLabel {
                font-weight: 600;
                color: #d1d5db;
            }
            QFrame#panel {
                background: #172033;
                border: 1px solid #2b3850;
                border-radius: 12px;
            }
            QLineEdit, QPlainTextEdit, QComboBox, QDoubleSpinBox, QTableWidget {
                background: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f3f4f6;
                selection-background-color: #2563eb;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                min-height: 20px;
                padding: 3px 7px;
            }
            QPlainTextEdit {
                padding: 6px;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
            QDoubleSpinBox:focus, QTableWidget:focus {
                border: 1px solid #60a5fa;
            }
            QHeaderView::section {
                background: #202c42;
                color: #dbeafe;
                border: 0;
                border-bottom: 1px solid #334155;
                padding: 7px;
                font-weight: 600;
            }
            QTableWidget {
                gridline-color: #26344b;
                alternate-background-color: #131d30;
            }
            QPushButton {
                background: #25324a;
                border: 1px solid #3b4a66;
                border-radius: 7px;
                color: #e5e7eb;
                padding: 8px 13px;
                font-weight: 600;
            }
            QPushButton:hover { background: #31405c; }
            QPushButton:pressed { background: #1e293b; }
            QPushButton:disabled { color: #64748b; background: #1e293b; }
            QPushButton#primaryButton {
                background: #2563eb;
                border-color: #3b82f6;
                color: white;
            }
            QPushButton#primaryButton:hover { background: #1d4ed8; }
            QLabel#resultIdle, QLabel#resultBusy, QLabel#resultPass,
            QLabel#resultReject, QLabel#resultError {
                border-radius: 9px;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#resultIdle { background: #243047; color: #cbd5e1; }
            QLabel#resultBusy { background: #3b2f15; color: #fde68a; }
            QLabel#resultPass { background: #123b2a; color: #86efac; }
            QLabel#resultReject { background: #492021; color: #fca5a5; }
            QLabel#resultError { background: #492021; color: #fecaca; }
            QLabel#warningNote {
                background: #2c2617;
                border: 1px solid #5b4b20;
                border-radius: 7px;
                color: #fde68a;
                padding: 9px;
            }
            QSplitter::handle { background: transparent; width: 12px; }
            """
        )

    def selected_artifact(self) -> Path:
        index = self.artifact_combo.currentIndex()
        if index < 0 or index >= len(self._artifacts):
            raise ManifestError("select an HTML artifact")
        artifact = self._artifacts[index].resolve()
        try:
            artifact.relative_to(self.project_root)
        except ValueError as exc:
            raise ManifestError(
                "selected artifact left the project directory"
            ) from exc
        return artifact

    @Slot()
    def choose_project(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose project folder",
            str(self.project_root),
        )
        if not selected:
            return
        self.project_root = Path(selected).resolve()
        self.project_path.setText(str(self.project_root))
        self._confirmed_replace = None
        self.refresh_artifacts()

    @Slot()
    def refresh_artifacts(self) -> None:
        try:
            artifacts = discover_artifacts(self.project_root)
        except ManifestError as exc:
            self.show_error(str(exc))
            return
        previous = self.artifact_combo.currentText()
        self.artifact_combo.blockSignals(True)
        self.artifact_combo.clear()
        self._artifacts = artifacts
        for artifact in artifacts:
            self.artifact_combo.addItem(
                artifact.relative_to(self.project_root).as_posix()
            )
        self.artifact_combo.blockSignals(False)
        if previous:
            match = self.artifact_combo.findText(previous)
            if match >= 0:
                self.artifact_combo.setCurrentIndex(match)
        if artifacts:
            self.artifact_changed(self.artifact_combo.currentIndex())
        else:
            self.manifest_path.setText("No HTML files found in this folder")
            self.name_edit.clear()
            self.clear_cases()
            self.result_summary.setText(
                "Choose a folder containing a self-contained HTML file."
            )

    @Slot(int)
    def artifact_changed(self, _index: int) -> None:
        if not self._artifacts:
            return
        artifact = self.selected_artifact()
        manifest = artifact.parent / "turing.json"
        self.manifest_path.setText(str(manifest))
        self._confirmed_replace = None
        if manifest.is_file():
            try:
                loaded = load_manifest(manifest)
            except ManifestError:
                self.reset_form(artifact)
                self.result_summary.setText(
                    "An invalid turing.json exists beside this artifact. "
                    "Complete the fields and save to replace it."
                )
            else:
                if loaded.artifact == artifact:
                    self.populate_manifest(loaded)
                    self.result_summary.setText(
                        "Loaded the existing manifest. Review it, then verify."
                    )
                else:
                    self.reset_form(artifact)
        else:
            self.reset_form(artifact)

    def reset_form(self, artifact: Path) -> None:
        self.name_edit.setText(artifact.stem)
        self.description_edit.clear()
        self.hook_edit.clear()
        self.schema_edit.clear()
        self.tolerance.setValue(0.0)
        self.clear_cases()
        self.add_case()

    def populate_manifest(self, manifest) -> None:
        self.name_edit.setText(manifest.name)
        self.description_edit.setText(manifest.description)
        self.hook_edit.setText(manifest.hook or "")
        self.schema_edit.setPlainText(
            ""
            if manifest.domain_schema is None
            else json.dumps(
                manifest.domain_schema, ensure_ascii=False, indent=2
            )
        )
        self.tolerance.setValue(manifest.number_tolerance)
        self.clear_cases()
        for case in manifest.cases:
            self.add_case(
                case["label"],
                json.dumps(case["args"], ensure_ascii=False),
                json.dumps(case["expected"], ensure_ascii=False),
            )
        if not manifest.cases:
            self.add_case()

    @Slot()
    def load_existing_manifest(self) -> None:
        try:
            artifact = self.selected_artifact()
            manifest_path = artifact.parent / "turing.json"
            manifest = load_manifest(manifest_path)
            if manifest.artifact != artifact:
                raise ManifestError(
                    "turing.json points to a different HTML artifact"
                )
            self.populate_manifest(manifest)
            self.result_summary.setText("Existing manifest reloaded.")
        except ManifestError as exc:
            self.show_error(str(exc))

    def clear_cases(self) -> None:
        self.case_table.setRowCount(0)

    @Slot()
    def add_case(
        self,
        label: str = "",
        args: str = "",
        expected: str = "",
    ) -> None:
        row = self.case_table.rowCount()
        self.case_table.insertRow(row)
        for column, value in enumerate((label, args, expected)):
            item = QTableWidgetItem(value)
            if column == 1:
                item.setToolTip('JSON array, for example: [99]')
            elif column == 2:
                item.setToolTip('Any JSON value, for example: 8 or "free"')
            self.case_table.setItem(row, column, item)
        self.case_table.setCurrentCell(row, 0)

    @Slot()
    def remove_cases(self) -> None:
        rows = sorted(
            {index.row() for index in self.case_table.selectedIndexes()},
            reverse=True,
        )
        for row in rows:
            self.case_table.removeRow(row)
        if self.case_table.rowCount() == 0:
            self.add_case()

    def case_values(self) -> list[str]:
        values = []
        for row in range(self.case_table.rowCount()):
            cells = [
                self.case_table.item(row, column)
                for column in range(3)
            ]
            label, args_text, expected_text = [
                "" if item is None else item.text().strip()
                for item in cells
            ]
            if not any((label, args_text, expected_text)):
                continue
            if not args_text:
                raise ManifestError(f"case {row + 1}: arguments are required")
            if not expected_text:
                raise ManifestError(
                    f"case {row + 1}: expected value is required"
                )
            args = _decode_json(args_text, f"case {row + 1} arguments")
            if not isinstance(args, list):
                raise ManifestError(
                    f"case {row + 1}: arguments must be a JSON array"
                )
            expected = _decode_json(
                expected_text, f"case {row + 1} expected value"
            )
            case = {
                "label": label or f"case {row + 1}",
                "args": args,
                "expected": expected,
            }
            values.append(json.dumps(case, ensure_ascii=False))
        if not values:
            raise ManifestError("add at least one expected case")
        return values

    def _confirm_replace(self, manifest: Path) -> bool:
        if not manifest.exists() or self._confirmed_replace == manifest:
            return True
        answer = QMessageBox.question(
            self,
            "Replace existing manifest?",
            f"{manifest.name} already exists.\n\n"
            "Replace it with the values currently shown?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._confirmed_replace = manifest
            return True
        return False

    def _save_manifest(self) -> Path | None:
        artifact = self.selected_artifact()
        manifest = artifact.parent / "turing.json"
        if not self._confirm_replace(manifest):
            return None
        hook = self.hook_edit.text().strip()
        if not hook:
            raise ManifestError(
                "browser hook is required for functional verification"
            )
        schema_text = self.schema_edit.toPlainText().strip()
        result = create_starter_manifest(
            artifact,
            output_value=manifest,
            name=self.name_edit.text().strip(),
            description=self.description_edit.text().strip(),
            hook=hook,
            case_values=self.case_values(),
            domain_schema_value=schema_text or None,
            number_tolerance=self.tolerance.value(),
            force=manifest.exists(),
        )
        self._confirmed_replace = manifest
        self.manifest_path.setText(result["manifest"])
        self.result_summary.setText(
            f"Saved {result['cases']} functional case(s) to {manifest.name}."
        )
        return manifest

    @Slot()
    def save_manifest(self) -> None:
        try:
            self._save_manifest()
        except (ManifestError, ValueError, OSError) as exc:
            self.show_error(str(exc))

    @Slot()
    def save_and_verify(self) -> None:
        try:
            manifest = self._save_manifest()
        except (ManifestError, ValueError, OSError) as exc:
            self.show_error(str(exc))
            return
        if manifest is not None:
            self.start_verification(manifest, runtime_only=False)

    @Slot()
    def run_page_check(self) -> None:
        try:
            artifact = self.selected_artifact()
        except ManifestError as exc:
            self.show_error(str(exc))
            return
        self.start_verification(artifact, runtime_only=True)

    def start_verification(self, target: Path, runtime_only: bool) -> None:
        if self._thread is not None:
            return
        self.set_busy(True)
        self.result_table.setRowCount(0)
        self.result_banner.setObjectName("resultBusy")
        self.result_banner.setText("Checking…")
        self.result_banner.style().unpolish(self.result_banner)
        self.result_banner.style().polish(self.result_banner)
        self.result_summary.setText(
            "Running in an isolated Chromium context. This can take a moment."
        )

        thread = QThread(self)
        worker = VerifyWorker(target, runtime_only)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self.show_result)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.failed.connect(self.show_worker_error)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._verification_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot()
    def _verification_finished(self) -> None:
        self._thread = None
        self._worker = None
        self.set_busy(False)

    def set_busy(self, busy: bool) -> None:
        for widget in (
            self.project_button,
            self.refresh_button,
            self.artifact_combo,
            self.add_case_button,
            self.remove_case_button,
            self.load_button,
            self.page_button,
            self.save_button,
            self.verify_button,
        ):
            widget.setEnabled(not busy)

    @Slot(dict)
    def show_result(self, result: dict) -> None:
        passed = bool(result["passed"])
        runtime_only = bool(result["runtime_only"])
        if passed and not runtime_only:
            text = "ACCEPTED"
            object_name = "resultPass"
            summary = (
                f"{result['name']} passed every runtime, containment, "
                "contract, and expected-case check."
            )
        elif passed:
            text = "PAGE CHECK PASSED"
            object_name = "resultIdle"
            summary = (
                "The page passed runtime and containment checks. Functional "
                "correctness was not tested."
            )
        else:
            text = "REJECTED"
            object_name = "resultReject"
            failed = [
                check["name"] for check in result["checks"]
                if not check["ok"]
            ]
            summary = "Failed checks: " + ", ".join(failed)
        self.result_banner.setObjectName(object_name)
        self.result_banner.setText(text)
        self.result_banner.style().unpolish(self.result_banner)
        self.result_banner.style().polish(self.result_banner)
        self.result_summary.setText(summary)

        checks = result["checks"]
        self.result_table.setRowCount(len(checks))
        for row, check in enumerate(checks):
            name_item = QTableWidgetItem(str(check["name"]))
            status_item = QTableWidgetItem("PASS" if check["ok"] else "FAIL")
            detail_item = QTableWidgetItem(str(check.get("detail", "")))
            color = QColor("#86efac" if check["ok"] else "#fca5a5")
            status_item.setForeground(color)
            status_font = status_item.font()
            status_font.setBold(True)
            status_item.setFont(status_font)
            self.result_table.setItem(row, 0, name_item)
            self.result_table.setItem(row, 1, status_item)
            self.result_table.setItem(row, 2, detail_item)

    @Slot(str)
    def show_worker_error(self, message: str) -> None:
        self._set_error(message)

    def _set_error(self, message: str) -> None:
        message = " ".join(message.split()) or "Unknown error"
        self.result_table.setRowCount(0)
        self.result_banner.setObjectName("resultError")
        self.result_banner.setText("NEEDS ATTENTION")
        self.result_banner.style().unpolish(self.result_banner)
        self.result_banner.style().polish(self.result_banner)
        self.result_summary.setText(message)

    @Slot(str)
    def show_error(self, message: str) -> None:
        self._set_error(message)
        QMessageBox.warning(self, "Turing Gate", message)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(
                self,
                "Verification is running",
                "Wait for verification to finish before closing the window.",
            )
            event.ignore()
            return
        super().closeEvent(event)


def launch_gui(project_root: str | Path = ".") -> int:
    """Launch the optional native interface."""
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])
    app.setApplicationName("Turing Gate")
    app.setOrganizationName("Turing Gate")
    window = GateWindow(project_root)
    window.show()
    if owns_app:
        return app.exec()
    return 0
