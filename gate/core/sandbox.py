"""Isolated execution of untrusted, model-generated HTML/JS.

Until now every experiment loaded generated code straight off `file://` in a
browser on the host. That was fine for prompts we wrote ourselves and unsafe as
an architecture. Docker isn't available here, so isolation is built from the
controls the browser actually gives us. For *browser-executed* content this is a
real boundary, not a fig leaf -- the renderer is already a sandbox; what it
lacks by default is network and origin containment.

| Threat                                   | Mitigation                          |
|------------------------------------------|-------------------------------------|
| exfiltrating data (fetch/XHR/img/beacon) | every non-artifact request aborted  |
| reading host files via `file://` origin  | served over ephemeral 127.0.0.1 HTTP|
|                                          | rooted in a temp dir                |
| persisting state between artifacts       | fresh browser context per run       |
| infinite loops / resource exhaustion     | hard navigation + execution timeouts|
| modal dialogs wedging the run            | auto-dismissed                      |
| navigating away to a live site           | cross-origin navigation blocked     |
| downloads writing to disk                | downloads refused                   |

NOT covered: a browser-engine escape, or anything outside the renderer. For
untrusted code beyond single-file HTML/JS (a build step, a server, native deps)
use a container -- this module is deliberately scoped to what it can actually
contain.
"""

from __future__ import annotations

import contextlib
import functools
import http.server
import shutil
import socket
import tempfile
import threading
from pathlib import Path

from .config import PAGE_TIMEOUT_MS, SETTLE_MS, get_logger

log = get_logger("gate.sandbox")


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):        # keep the server silent
        pass


@contextlib.contextmanager
def _serve(directory: Path):
    """Serve `directory` on an ephemeral loopback port; yield the base URL."""
    handler = functools.partial(_QuietHandler, directory=str(directory))
    with socket.socket() as s:            # ask the OS for a free port
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()
        srv.server_close()


@contextlib.contextmanager
def sandboxed_page(html_path, extra_files=None):
    """Yield a Playwright Page showing `html_path`, network-isolated.

    The file is copied into a throwaway directory which becomes the entire
    visible filesystem for the page. Only requests to that origin are served;
    everything else is aborted.
    """
    # Keep Playwright out of package import time. Queue/policy/config commands
    # do not execute artifacts and must work in a minimal Python environment.
    from playwright.sync_api import sync_playwright

    html_path = Path(html_path).resolve()
    tmp = Path(tempfile.mkdtemp(prefix="gate-sbx-"))
    try:
        target = tmp / "index.html"
        shutil.copyfile(html_path, target)
        for extra in (extra_files or []):
            shutil.copyfile(extra, tmp / Path(extra).name)

        with _serve(tmp) as base, sync_playwright() as p:
            browser = p.chromium.launch(args=["--disable-dev-shm-usage"])
            # Fresh context => no shared cookies/storage between artifacts.
            ctx = browser.new_context(accept_downloads=False,
                                      service_workers="block")
            ctx.set_default_timeout(PAGE_TIMEOUT_MS)

            blocked: list[str] = []

            def _route(route, request):
                if request.url.startswith(base):
                    route.continue_()
                else:
                    blocked.append(request.url)
                    route.abort()

            ctx.route("**/*", _route)
            page = ctx.new_page()
            page.on("dialog", lambda d: d.dismiss())
            page.on("download", lambda d: d.cancel())

            page.goto(f"{base}/index.html", wait_until="load",
                      timeout=PAGE_TIMEOUT_MS)
            page.wait_for_timeout(SETTLE_MS)
            page.blocked_requests = blocked          # attach for inspection
            try:
                yield page
            finally:
                if blocked:
                    log.warning("blocked %d outbound request(s) from %s: %s",
                                len(blocked), html_path.name, blocked[:3])
                with contextlib.suppress(Exception):
                    ctx.close()
                    browser.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
