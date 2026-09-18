"""Kazakh-Japanese fact layer: renders offline, on open, for every place, and the
   two tap affordances (expand / reveal) work under touch input.

   Run with Japan_Guide_2026.html next to this file, like the other suites."""
import asyncio, json, pathlib
from playwright.async_api import async_playwright

FILE = pathlib.Path("Japan_Guide_2026.html").resolve().as_uri()

# markercluster releases a marker only after zoomend, so moving and opening must be
# two separate steps with a settle in between — otherwise the previous popup lingers
# and the DOM read silently describes the wrong place.
GOTO = """(label) => {
  const i = DATA.places.findIndex(p => p.label === label);
  if (i < 0) return null;
  map.setView([DATA.places[i].lat, DATA.places[i].lng], 16);
  return i;
}"""
# the page's own way in: zoomToShowLayer expands the cluster (or spiderfies a shared
# point) and only then opens the card — the same path a tap on a route row takes
OPEN = """(i) => new Promise(res => {
  cluster.zoomToShowLayer(markers[i], () => { markers[i].openPopup(); setTimeout(res, 120); });
})"""
POPUP_TITLE = """() => {
  const h = document.querySelector('.leaflet-popup .pop h4');
  return h ? h.textContent.trim() : null;
}"""

# facts are counted from the payload, so the DOM is checked against the source of truth
COUNTS = """() => {
  const box = document.querySelector('.kzbox');
  if (!box) return null;
  const vis = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const items = [...box.querySelectorAll('.kzi, .kzg')];
  return {
    head: box.querySelector('.kzhead').textContent.trim(),
    badge: +box.querySelector('.kzhead i').textContent.trim(),
    total: items.length,
    visible: items.filter(vis).length,
    more_visible: vis(box.querySelector('.kzmore') || document.createElement('i')),
    games: box.querySelectorAll('.kzg').length,
    reveals_open: [...box.querySelectorAll('.kzrev')].filter(vis).length,
  };
}"""


async def main():
    r, errs = {}, []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                                  has_touch=True, device_scale_factor=3)
        # every external request dies: the layer must be fully baked into the file
        await ctx.route("**://**", lambda rt: rt.abort() if rt.request.url.startswith("http")
                        else rt.continue_())
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
        # blocked tiles/weather surface as console resource errors — expected offline,
        # and separate from a pageerror, which is a hard fail under the spec
        net = []
        pg.on("console", lambda m: (net if "Failed to load resource" in m.text else errs)
              .append("console." + m.type + ": " + m.text) if m.type == "error" else None)
        await pg.goto(FILE, wait_until="load")
        await pg.wait_for_timeout(1600)

        # 1. nothing is built at load — the card assembles on open
        r["1_kzbox_before_any_popup"] = await pg.locator(".kzbox").count()

        # 2. every place carries facts, and every popup renders them
        r["2_places_total"] = await pg.evaluate("DATA.places.length")
        r["2_places_with_facts"] = await pg.evaluate(
            "DATA.places.filter(p => (p.kz||[]).length).length")
        r["2_facts_total"] = await pg.evaluate(
            "DATA.places.reduce((n,p) => n + (p.kz||[]).length, 0)")

        # 3. a nine-fact anchor point: header, badge, and only two items shown up front
        r["3_opened"] = await pg.evaluate(GOTO, "Ginza")
        await pg.wait_for_timeout(600)
        await pg.evaluate(OPEN, r["3_opened"])
        await pg.wait_for_timeout(400)
        r["3_popup_title"] = await pg.evaluate(POPUP_TITLE)
        c0 = await pg.evaluate(COUNTS)
        r["3_collapsed"] = c0
        await pg.screenshot(path="kz_1_collapsed.png")

        # 4. tap "ещё N" with a finger, not a mouse
        await pg.locator("[data-kzmore]").tap()
        await pg.wait_for_timeout(400)
        r["4_expanded"] = await pg.evaluate(COUNTS)
        await pg.screenshot(path="kz_2_expanded.png")

        # 5. tap a game's reveal
        r["5_games_on_card"] = await pg.locator(".kzbox .kzg").count()
        if r["5_games_on_card"]:
            await pg.locator(".kzbox [data-kzrev]").first.tap()
            await pg.wait_for_timeout(400)
            r["5_after_reveal"] = await pg.evaluate(COUNTS)
            r["5_reveal_text"] = (await pg.locator(".kzbox .kzrev").first.inner_text())[:90]
        await pg.screenshot(path="kz_3_revealed.png")

        # 6. the card must not slide under the top bar once it grows
        r["6_popup_clears_topbar"] = await pg.evaluate("""() => {
          const pop = document.querySelector('.leaflet-popup');
          const bar = document.querySelector('.topbar');
          if (!pop || !bar) return null;
          return Math.round(pop.getBoundingClientRect().top
                          - bar.getBoundingClientRect().bottom);
        }""")

        # 7. open every single place and make sure each one renders its own box
        bad = []
        labels = await pg.evaluate("DATA.places.map(p => p.label)")
        for lb in labels:
            i = await pg.evaluate(GOTO, lb)
            await pg.wait_for_timeout(200)
            await pg.evaluate(OPEN, i)
            await pg.wait_for_timeout(120)
            got = await pg.evaluate("""() => {
              const b = document.querySelector('.kzbox');
              return b ? +b.querySelector('.kzhead i').textContent.trim() : 0;
            }""")
            title = await pg.evaluate(POPUP_TITLE)
            want = await pg.evaluate(
                "(l) => (DATA.places.find(p => p.label === l).kz || []).length", lb)
            # the title guard proves the count belongs to this place and not a stale card
            if got != want or not title or lb not in title:
                bad.append({"place": lb, "dom": got, "data": want, "card": title})
        r["7_places_checked"] = len(labels)
        r["7_mismatches"] = bad

        # 8. honesty glyphs: a joke must never be able to render as a verified fact
        r["8_glyph_map"] = await pg.evaluate("JSON.stringify(KZ_GLYPH)")
        r["8_levels_used"] = await pg.evaluate("""() => {
          const s = {};
          DATA.places.forEach(p => (p.kz||[]).forEach(f => {
            if (!f.game) s[f.level] = (s[f.level]||0) + 1; }));
          return s;
        }""")
        r["8_levels_without_glyph"] = await pg.evaluate("""() => {
          const out = new Set();
          DATA.places.forEach(p => (p.kz||[]).forEach(f => {
            if (!f.game && !KZ_GLYPH[f.level]) out.add(f.level); }));
          return [...out];
        }""")

        # 9. the tick list: one row per spot task, counter agrees with the payload
        await pg.evaluate("showPanel(legendEl, true)")
        await pg.wait_for_timeout(300)
        r["9_spots_in_payload"] = await pg.evaluate("DATA.kzSpots")
        r["9_rows_rendered"] = await pg.locator("#bingoList .bingo-row").count()
        r["9_counter"] = await pg.locator("#bingoCount").inner_text()
        r["9_storage_ok"] = await pg.evaluate("KZ_STORAGE_OK")
        await pg.screenshot(path="kz_4_tasks.png")

        # 10. tick two tasks in the panel, then reload — the ticks must come back
        await pg.locator("#bingoList .bingo-tick").nth(0).tap()
        await pg.locator("#bingoList .bingo-tick").nth(1).tap()
        await pg.wait_for_timeout(200)
        r["10_counter_after_tick"] = await pg.locator("#bingoCount").inner_text()
        r["10_done_rows"] = await pg.locator("#bingoList .bingo-row.done").count()
        saved = await pg.evaluate("Object.keys(KZ_DONE).length")

        await pg.reload(wait_until="load"); await pg.wait_for_timeout(1500)
        await pg.evaluate("showPanel(legendEl, true)"); await pg.wait_for_timeout(300)
        r["10_after_reload_counter"] = await pg.locator("#bingoCount").inner_text()
        r["10_after_reload_done"] = await pg.locator("#bingoList .bingo-row.done").count()
        r["10_keys_saved"] = saved

        # 11. a tick made in the panel shows up inside that place's card
        first = await pg.evaluate("""() => {
          const t = kzSpotTasks().find(t => KZ_DONE[t.g.id]);
          return t ? { i: t.i, label: t.p.label } : null;
        }""")
        r["11_checked_place"] = first
        if first:
            await pg.evaluate("showPanel(legendEl, false)"); await pg.wait_for_timeout(200)
            await pg.evaluate(GOTO, first["label"]); await pg.wait_for_timeout(500)
            await pg.evaluate(OPEN, first["i"]); await pg.wait_for_timeout(300)
            if await pg.locator("[data-kzmore]").count():
                await pg.locator("[data-kzmore]").tap(); await pg.wait_for_timeout(250)
            r["11_popup_button"] = await pg.locator(".kzbox .kzdone").first.inner_text()
            r["11_popup_button_on"] = await pg.locator(".kzbox .kzdone.on").count()

            # 12. untick from the card — the panel counter must follow
            await pg.locator(".kzbox .kzdone").first.tap(); await pg.wait_for_timeout(250)
            r["12_button_after_untick"] = await pg.locator(".kzbox .kzdone").first.inner_text()
            await pg.evaluate("showPanel(legendEl, true)"); await pg.wait_for_timeout(250)
            r["12_counter_after_untick"] = await pg.locator("#bingoCount").inner_text()

        # 13. the jump arrow opens the place and, on a phone, closes the panel behind it
        await pg.evaluate("showPanel(legendEl, true)"); await pg.wait_for_timeout(250)
        await pg.locator("#bingoList .bingo-go").nth(3).tap(); await pg.wait_for_timeout(1400)
        r["13_panel_open_after_jump"] = await pg.evaluate("legendEl.classList.contains('open')")
        r["13_popup_after_jump"] = await pg.evaluate(POPUP_TITLE)

        r["errors"] = errs
        r["blocked_requests"] = len(net)   # expected offline: tiles + weather
        await b.close()
    print(json.dumps(r, ensure_ascii=False, indent=1))


asyncio.run(main())
