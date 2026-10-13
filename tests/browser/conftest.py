"""Serve Food4Thought's real application for Chromium tests with per-test browser
contexts and the root fixtures' isolated storage. Missing Playwright or Chromium
skips locally but fails when REQUIRE_BROWSER_TESTS=1, so CI cannot silently omit
frontend verification.
"""

import os
import socket
import threading
import time

import pytest
import uvicorn

from app.main import app

REQUIRED = os.environ.get("REQUIRE_BROWSER_TESTS") == "1"


def _skip_or_fail(reason: str) -> None:
    if REQUIRED:
        pytest.fail(reason)
    pytest.skip(reason)


@pytest.fixture(scope="session")
def live_server():
    """Serve the real app on a free local port for the whole browser session.

    The root conftest's autouse fixture points RESTAURANTS_DATA_PATH at a
    per-test temporary copy, and the repository reads that variable on every
    request, so each test still sees its own isolated data.
    """
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            pytest.fail("Test server did not start")
        time.sleep(0.05)

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        _skip_or_fail("Playwright is not installed (pip install -r requirements-dev.txt)")

    with sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(
                executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None
            )
        except Error as exc:
            _skip_or_fail(f"Chromium is not available (python -m playwright install chromium): {exc}")
        yield launched
        launched.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1100, "height": 720})
    new_page = context.new_page()
    errors: list[str] = []
    new_page.on("pageerror", lambda error: errors.append(str(error)))
    new_page.page_errors = errors
    yield new_page
    context.close()
