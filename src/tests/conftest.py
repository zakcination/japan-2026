"""Shared fixtures: build the guide once, a bare page with the pure core, and the full app on a phone."""
import json
import pathlib
import subprocess
import sys
from datetime import datetime

import pytest
from playwright.sync_api import sync_playwright

SRC = pathlib.Path(__file__).resolve().parents[1]
ROOT = SRC.parent
PAGE = (SRC / "Japan_Guide_2026.html").resolve().as_uri()
IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
PHONE = {"width": 390, "height": 844}


def _build():
    subprocess.run([sys.executable, "build_guide.py"], cwd=SRC, check=True, capture_output=True)


def pytest_configure(config):
    # with pytest-xdist the page is built once, by the controller, before the workers start
    if not hasattr(config, "workerinput"):
        _build()


@pytest.fixture(scope="session", autouse=True)
def built():
    yield


@pytest.fixture(scope="session")
def site(built, tmp_path_factory):
    """The built page as index.html with trips/ next to it, over http (fetch doesn't work on file://).
    No sw.js here, so no service worker gets between the tests and the files."""
    import functools, http.server, shutil, threading
    root = tmp_path_factory.mktemp("site")
    shutil.copy(SRC / "Japan_Guide_2026.html", root / "index.html")
    shutil.copytree(ROOT / "trips", root / "trips")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/index.html"
    srv.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def core(browser):
    """about:blank with src/today/core.js (and optional extra modules) loaded; exposes window.Core."""
    pages = []

    def load(mods=("core.js",)):
        pg = browser.new_page()
        pg.goto("about:blank")
        code = "\n".join((SRC / "today" / m).read_text(encoding="utf-8") for m in mods)
        pg.add_script_tag(content=code + "\nwindow.Core = Core;" + ("\nwindow.Ios = Ios;" if "ios.js" in mods else "")
                           + ("\nwindow.Flights = Flights;" if "flights.js" in mods else "")
                           + ("\nwindow.Prep = Prep;" if "prep.js" in mods else ""))
        pages.append(pg)
        return pg

    yield load
    for p in pages:
        p.close()


def until(page, js, timeout=5000):
    """Poll a JS expression until it is truthy. The page's CSP forbids the string eval that
    page.wait_for_function relies on; page.evaluate goes through the debugger and is allowed."""
    import time
    end = time.time() + timeout / 1000
    while time.time() < end:
        if page.evaluate(js):
            return
        time.sleep(0.05)
    raise AssertionError("timed out waiting for " + js)


class App:
    def __init__(self, page, errors):
        self.page, self.errors = page, errors


@pytest.fixture
def app(browser):
    made = []

    def open_(state=None, settings=None, trip=None, size=PHONE, url_suffix="", now="2026-09-30T12:00:00+09:00",
              dark_os=False, ua=None, url=None, routes=None):
        extra = {"user_agent": ua} if ua else {}
        if state and "prevDay" in state and "preview" not in state:   # a preview clock means preview mode
            state = {**state, "preview": True}
        ctx = browser.new_context(viewport=size, device_scale_factor=2, has_touch=True, is_mobile=True,
                                  color_scheme="dark" if dark_os else "light", accept_downloads=True, **extra)
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        if now:
            pg.clock.set_fixed_time(datetime.fromisoformat(now))
        seed = {"japan2026.today.v1": state, "japan2026.settings.v1": settings, "japan2026.trip.v1": trip}
        pg.add_init_script(
            "(s => { if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded', '1');"
            " for (const [k, v] of Object.entries(s)) if (v) localStorage.setItem(k, JSON.stringify(v)); })("
            + json.dumps(seed) + ")")
        for pattern, handler in (routes or {}).items():
            pg.route(pattern, handler)
        pg.goto((url or PAGE) + url_suffix)
        pg.wait_for_selector("#today", state="attached")
        made.append(ctx)
        return App(pg, errors)

    yield open_
    for c in made:
        c.close()

# The older map suites are standalone scripts (they run on import): keep them out of pytest,
# run them with `python tests/<name>.py` from src/ as before.
collect_ignore = ["test_v3.py", "test_cluster.py", "test_kz.py", "test_overlap.py", "test_offline.py"]
