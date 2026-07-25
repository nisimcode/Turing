"""Zero-API environment diagnostics for the public verifier."""

from __future__ import annotations

import contextlib
import importlib.metadata
import platform
import socket
import sys
import uuid
from pathlib import Path

from .telemetry import log_path


def _error(exc: Exception) -> str:
    return " ".join(str(exc).split())[:240] or type(exc).__name__


def _browser_fix() -> str:
    if platform.system() == "Linux":
        return "turing-gate install-browser --with-deps"
    return "turing-gate install-browser"


def doctor_report(package_version: str) -> dict:
    """Exercise setup surfaces and return a stable machine-readable report."""
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str, fix: str | None = None) -> None:
        row = {"name": name, "ok": ok, "detail": detail}
        if not ok and fix:
            row["fix"] = fix
        checks.append(row)

    python_ok = sys.version_info >= (3, 12)
    add(
        "python",
        python_ok,
        f"{platform.python_implementation()} {platform.python_version()}",
        "install Python 3.12 or newer",
    )
    add(
        "package",
        True,
        f"turing-gate {package_version}",
    )
    add(
        "platform",
        True,
        f"{platform.system()} {platform.release()} ({platform.machine()})",
    )

    target = log_path()
    probe: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        probe = target.parent / f".doctor-{uuid.uuid4().hex}.tmp"
        probe.write_text("ok", encoding="utf-8")
        add("local_state", True, f"writable: {target.parent.resolve()}")
    except OSError as exc:
        add(
            "local_state",
            False,
            _error(exc),
            "run from a writable project directory",
        )
    finally:
        if probe is not None:
            try:
                probe.unlink(missing_ok=True)
            except OSError:
                pass

    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        add("loopback", True, f"127.0.0.1:{port} available")
    except OSError as exc:
        add(
            "loopback",
            False,
            _error(exc),
            "allow local loopback sockets for the sandbox",
        )

    try:
        playwright_version = importlib.metadata.version("playwright")
        from playwright.sync_api import sync_playwright
    except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
        add(
            "playwright",
            False,
            _error(exc),
            "reinstall turing-gate",
        )
        add("chromium", False, "not checked", _browser_fix())
        add("browser_launch", False, "not checked", _browser_fix())
    else:
        add("playwright", True, playwright_version)
        try:
            with sync_playwright() as runtime:
                executable = Path(runtime.chromium.executable_path)
                installed = executable.is_file()
                add(
                    "chromium",
                    installed,
                    str(executable),
                    _browser_fix(),
                )
                if installed:
                    browser = None
                    try:
                        browser = runtime.chromium.launch(
                            args=["--disable-dev-shm-usage"]
                        )
                        page = browser.new_page()
                        page.set_content("<main>Turing Gate doctor</main>")
                        value = page.evaluate("6 * 7")
                        add(
                            "browser_launch",
                            value == 42,
                            "Chromium launched and executed JavaScript",
                            _browser_fix(),
                        )
                    except Exception as exc:  # noqa: BLE001
                        add(
                            "browser_launch",
                            False,
                            _error(exc),
                            _browser_fix(),
                        )
                    finally:
                        if browser is not None:
                            with contextlib.suppress(Exception):
                                browser.close()
                else:
                    add(
                        "browser_launch",
                        False,
                        "Chromium executable is not installed",
                        _browser_fix(),
                    )
        except Exception as exc:  # noqa: BLE001
            add("chromium", False, _error(exc), _browser_fix())
            add("browser_launch", False, "not checked", _browser_fix())

    return {
        "schema_version": 1,
        "ready": all(check["ok"] for check in checks),
        "checks": checks,
    }
