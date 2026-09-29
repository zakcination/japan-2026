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
PHONE = {"width": 390, "height": 844}


@pytest.fixture(scope="session", autouse=True)
def built():
    subprocess.run([sys.executable, "build_guide.py"], cwd=SRC, check=True, capture_output=True)


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
        pg.add_script_tag(content=code + "\nwindow.Core = Core;" + ("\nwindow.Ios = Ios;" if "ios.js" in mods else ""))
        pages.append(pg)
        return pg

    yield load
    for p in pages:
        p.close()


class App:
    def __init__(self, page, errors):
        self.page, self.errors = page, errors


@pytest.fixture
def app(browser):
    made = []

    def open_(state=None, settings=None, trip=None, size=PHONE, url_suffix="", now="2026-09-30T12:00:00+09:00",
              dark_os=False):
        ctx = browser.new_context(viewport=size, device_scale_factor=2, has_touch=True, is_mobile=True,
                                  color_scheme="dark" if dark_os else "light")
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
        pg.goto(PAGE + url_suffix)
        pg.wait_for_selector("#today", state="attached")
        made.append(ctx)
        return App(pg, errors)

    yield open_
    for c in made:
        c.close()

# The older map suites are standalone scripts (they run on import): keep them out of pytest,
# run them with `python tests/<name>.py` from src/ as before.
collect_ignore = ["test_v3.py", "test_cluster.py", "test_kz.py", "test_overlap.py", "test_offline.py"]
