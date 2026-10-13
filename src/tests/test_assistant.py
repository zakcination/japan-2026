"""The assistant chat (ui/assistant.js) against FakeSupabase's scripted Edge Function: who sees it, a round trip,
«Применить» through the app's own paths, «Не надо», escaping, offline, photos, the voice translator."""
import base64, json, struct
from conftest import until
from fake_supabase import FakeSupabase
from test_group_api import GROUPED
from test_group_join import logged

PROFILE = {"name": "Саня", "lang": "ru", "tone": "calm", "energy": "mid", "interests": "", "food": "халяль", "notify": {}, "at": 1}


def guest(app, fake, profile=True, **kw):
    san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "kyoto", "mode": "in"})
    a = logged(app, fake, san, "4821", state={"prevDay": 3, "prevTime": "06:00"}, **kw)
    a.page.evaluate("localStorage.setItem('japan2026.assistant.server', 'all')")       # the owner switched the server assistant on
    if profile:
        a.page.evaluate(f"localStorage.setItem('japan2026.assistant.profile.v1', {json.dumps(json.dumps(PROFILE))})")
    return a, san


def ask(pg, text):
    pg.fill("#asText", text)
    pg.click("#asSend")
    until(pg, "!document.getElementById('asWait') && document.querySelectorAll('#asLog .as-msg.ai, #asLog .as-note').length > 0")


def test_hidden_until_signed_in_then_profile_first_and_a_round_trip(app):
    fake = FakeSupabase.seeded()
    a = app(trip=GROUPED, state={"prevDay": 3, "prevTime": "06:00"}, supabase=fake)
    a.page.evaluate("localStorage.setItem('japan2026.assistant.server', 'all'); renderShell()")
    assert a.page.locator("#tcAsk").count() == 0                                   # signed out: no assistant
    san = fake._add("Сания", "guest")
    a.page.evaluate("localStorage.setItem('japan2026.loginasked.v1', '1')")
    if a.page.locator("#grJustLook").count() and a.page.locator("#grJustLook").is_visible(): a.page.click("#grJustLook")
    assert a.page.evaluate(f"Api.login('{san}', '4821', {json.dumps(fake.invite(san))})")["ok"]
    a.page.evaluate("renderShell()")
    pg = a.page
    pg.click("#tcAsk")
    assert pg.locator("#asProfSave").is_visible()                                  # first open asks the profile
    pg.fill("#asName", "Саня"); pg.click("[data-seg='lang'] [data-v='kk']"); pg.fill("#asFood", "без свинины")
    pg.click("#asProfSave")
    fake.assistant_reply = {"reply": "Сегодня Киото.\nПервым — бамбуковая роща.", "actions": [], "cards": [],
                            "sources": [{"title": "JNTO", "url": "https://www.japan.travel/"}]}
    ask(pg, "Что у меня сегодня?")
    body = fake.assistant_requests[-1]
    assert body["trip"] == "miras-aikosh" and body["messages"][-1] == {"role": "user", "text": "Что у меня сегодня?"}
    assert body["profile"]["name"] == "Саня" and body["profile"]["lang"] == "kk" and body["profile"]["food"] == "без свинины"
    assert body["rates"]["KZT"] > 0 and "images" not in body["messages"][-1]
    msg = pg.locator("#asLog .as-msg.ai").last
    assert "Первым — бамбуковая роща." in msg.inner_text() and msg.locator("br").count() == 1
    assert msg.locator("a[href='https://www.japan.travel/']").count() == 1
    fake.assistant_reply = {"reply": "Да.", "actions": []}
    ask(pg, "А завтра?")
    hist = fake.assistant_requests[-1]["messages"]                                 # the conversation goes back
    assert [m["role"] for m in hist] == ["user", "assistant", "user"] and hist[1]["text"].startswith("Сегодня Киото")
    pg.click("#tcSheetX"); pg.click("#tcAsk")
    assert pg.locator("#asLog .as-msg.ai").count() == 2                            # kept for the session
    assert not a.errors


def test_reply_markup_and_bad_links_stay_text(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    fake.assistant_reply = {"reply": "<img src=x onerror=window.pwned=1><b>жирно</b>", "actions": [],
                            "cards": [{"kind": "place", "name": "<i>Место</i>", "url": "javascript:window.pwned=1"},
                                      {"kind": "ja", "ja": "<b>トイレ</b>", "reading": "", "meaning": "Где туалет?"}],
                            "sources": [{"title": "x", "url": "javascript:alert(1)"}]}
    pg.click("#tcAsk"); ask(pg, "<script>window.pwned=1</script>")
    msg = pg.locator("#asLog .as-msg.ai").last
    assert "<img src=x" in msg.inner_text() and "<b>жирно</b>" in msg.inner_text() and "<i>Место</i>" in msg.inner_text()
    assert msg.locator("img, i, script, p > b").count() == 0 and msg.locator("a[href^='javascript']").count() == 0
    assert "<script>" in pg.locator("#asLog .as-msg.me").last.inner_text()
    pg.click("[data-jafull]")
    assert pg.locator("#asLocal .tc-local-name").inner_text() == "<b>トイレ</b>"
    assert pg.evaluate("window.pwned") is None and not a.errors


def test_apply_move_on_my_own_stop_and_dismiss_does_nothing(app):
    fake = FakeSupabase.seeded(); a, san = guest(app, fake); pg = a.page
    fake.my_stops["m-lunch"] = {"id": "m-lunch", "member": san, "day": 3, "shared": False, "ev": {"s": "12:00", "e": "13:00", "t": "Обед"}}
    pg.evaluate("Api.refresh()")
    fake.assistant_reply = {"reply": "Предлагаю сдвинуть обед.", "actions": [
        {"id": "a1", "kind": "move", "stop_id": "m-lunch", "day_n": 3, "title": "Обед", "from_s": "12:00", "from_e": "13:00",
         "start": "14:00", "end": "15:00", "reason": "дождь", "scope": "mine", "how": "save"},
        {"id": "a2", "kind": "skip", "stop_id": "d3e3", "day_n": 3, "title": "Тэнрю-дзи", "reason": "", "scope": "group"}]}
    pg.click("#tcAsk"); ask(pg, "Дождь, что поменять?")
    assert "12:00–13:00 → 14:00–15:00" in pg.locator("[data-act='1:a1']").inner_text()
    joins0 = list(fake.joins)
    pg.click("[data-dismiss='1:a2']")
    assert "Не надо" in pg.locator("[data-act='1:a2']").inner_text() and fake.joins == joins0
    assert fake.my_stops["m-lunch"]["ev"]["s"] == "12:00"                          # nothing until «Применить»
    pg.click("[data-apply='1:a1']")
    until(pg, "Api.status().pending === 0")
    assert fake.my_stops["m-lunch"]["ev"]["s"] == "14:00" and fake.my_stops["m-lunch"]["ev"]["e"] == "15:00"
    assert "Применено" in pg.locator("[data-act='1:a1']").inner_text() and "Перенёс «Обед»" in pg.inner_text("#asLog")
    assert fake.joins == joins0 and not a.errors


def test_guest_move_on_a_group_stop_becomes_a_proposal_host_move_changes_the_plan(app):
    move = {"id": "a1", "kind": "move", "stop_id": "d3e3", "day_n": 3, "title": "Тэнрю-дзи, сад дзен", "from_s": "08:30", "from_e": "09:30",
            "start": "11:00", "end": "12:00", "reason": "выспаться", "scope": "group"}
    fake = FakeSupabase.seeded(); a, san = guest(app, fake); pg = a.page
    fake.assistant_reply = {"reply": "Можно позже.", "actions": [dict(move, how="propose")]}
    v = fake.plan["version"]
    pg.click("#tcAsk"); ask(pg, "Хочу поспать подольше")
    assert "станет предложением хозяевам" in pg.inner_text("[data-act='1:a1']")
    pg.click("[data-apply='1:a1']")
    until(pg, "Api.status().pending === 0")
    p = fake.proposals[0]
    assert len(fake.proposals) == 1 and p["kind"] == "time" and p["ref"] == "d3e3" and p["payload"] == {"s": "11:00", "e": "12:00"}
    assert p["member"] == san and p["note"] == "выспаться" and fake.plan["version"] == v      # the plan itself is untouched

    h = logged(app, fake, fake.host_id, fake.host_pin, state={"prevDay": 3, "prevTime": "06:00"})
    h.page.evaluate(f"localStorage.setItem('japan2026.assistant.profile.v1', {json.dumps(json.dumps(PROFILE))}); localStorage.setItem('japan2026.assistant.server', 'all'); renderShell()")
    fake.assistant_reply = {"reply": "Переношу.", "actions": [dict(move, how="plan")]}
    h.page.click("#tcAsk"); ask(h.page, "Перенеси Тэнрю-дзи")
    h.page.click("[data-apply='1:a1']")
    until(h.page, "Api.status().pending === 0")
    assert fake.plan["version"] == v + 1
    assert next(e for d in fake.plan["doc"]["days"] for e in d["ev"] if e["id"] == "d3e3")["s"] == "11:00"


def test_expense_card_opens_the_prefilled_expense_sheet(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    fake.assistant_reply = {"reply": "Записать?", "actions": [{"id": "a1", "kind": "expense", "amount": 1200, "currency": "JPY", "category": "food", "title": "Рамен"}]}
    pg.click("#tcAsk"); ask(pg, "Потратил 1200 на рамен")
    pg.click("[data-apply='1:a1']")
    assert pg.input_value("#exAmt") == "1200" and pg.locator(".ex-cat[data-cat='food'][aria-pressed='true']").count() == 1
    assert not fake.expenses                                                        # the traveller still confirms
    pg.click("#tcSheetX"); pg.click("#tcAsk")
    assert "Применено" in pg.inner_text("[data-act='1:a1']")


def test_offline_says_internet_is_needed_and_sends_nothing(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    pg.click("#tcAsk")
    pg.context.set_offline(True)
    pg.fill("#asText", "Что сегодня?"); pg.click("#asSend")
    until(pg, "/Нужен интернет/.test(document.getElementById('asLog').textContent)")
    assert not fake.assistant_requests
    pg.context.set_offline(False)


def test_server_refusal_for_non_members_is_explained(app):
    fake = FakeSupabase.seeded(); a, san = guest(app, fake); pg = a.page
    fake.assistant_reply = lambda body: (503, {"error": "Ассистент ещё не настроен."})
    pg.click("#tcAsk"); ask(pg, "Привет")
    assert "Ассистент ещё не настроен." in pg.inner_text("#asLog")


def _jpeg_size(b):
    i = 2
    while i < len(b):
        marker, ln = b[i + 1], struct.unpack(">H", b[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC2):
            h, w = struct.unpack(">HH", b[i + 5:i + 9]); return w, h
        i += 2 + ln
    return None


def test_a_photo_is_shrunk_to_1568_and_sent_once(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    pg.evaluate("localStorage.setItem('japan2026.assistant.photos', '1'); renderShell()")   # a trip whose model reads photos
    png = pg.evaluate("""(() => { const c = document.createElement('canvas'); c.width = 3000; c.height = 1500;
      const x = c.getContext('2d'); x.fillStyle = '#c00'; x.fillRect(0, 0, 3000, 1500); return c.toDataURL('image/png').split(',')[1]; })()""")
    pg.click("#tcAsk")
    pg.set_input_files("#asPhoto", files=[{"name": "menu.png", "mimeType": "image/png", "buffer": base64.b64decode(png)}])
    until(pg, "document.querySelectorAll('#asPics img').length === 1")
    fake.assistant_reply = {"reply": "Это меню: рамен со свининой.", "actions": []}
    ask(pg, "Что тут?")
    last = fake.assistant_requests[-1]["messages"][-1]
    img = last["images"][0]
    assert img["media_type"] == "image/jpeg" and _jpeg_size(base64.b64decode(img["data"])) == (1568, 784)
    assert pg.locator("#asLog .as-msg.me img.as-thumb").count() == 1
    ask(pg, "А это острое?")
    assert all("images" not in m for m in fake.assistant_requests[-1]["messages"])   # photos go once


SPEECH = """(() => {
window.__said = [];
window.speechSynthesis.speak = u => window.__said.push([u.lang, u.text]);
window.webkitSpeechRecognition = window.SpeechRecognition = class { start() { const r = this; window.__lang = r.lang;
  setTimeout(() => r.onresult({ results: [[{ transcript: window.__heard }]] }), 10); setTimeout(() => r.onend && r.onend(), 20); } abort() {} };
})()"""


def test_voice_translator_speaks_japanese_and_back(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    pg.evaluate(SPEECH)
    fake.assistant_reply = lambda b: (200, {"text": "トイレはどこですか" if b.get("to") == "ja" else "Прямо и налево"})
    pg.click("#tcAsk"); pg.click("#asToTr")
    pg.evaluate("window.__heard = 'Где туалет?'"); pg.click("#trMe")
    until(pg, "window.__said.length === 1")
    body = fake.assistant_requests[-1]
    assert body["mode"] == "translate" and body["text"] == "Где туалет?" and body["from"] == "ru" and body["to"] == "ja"
    assert pg.evaluate("window.__said[0]") == ["ja-JP", "トイレはどこですか"] and pg.evaluate("window.__lang") == "ru-RU"
    pg.evaluate("window.__heard = 'まっすぐ行って左です'"); pg.click("#trThem")
    until(pg, "window.__said.length === 2")
    assert fake.assistant_requests[-1]["from"] == "ja" and pg.evaluate("window.__lang") == "ja-JP"
    assert pg.evaluate("window.__said[1]") == ["ru-RU", "Прямо и налево"] and "Прямо и налево" in pg.inner_text("#trOut")


def test_dictation_without_speech_recognition_points_to_the_keyboard(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    pg.evaluate("delete window.webkitSpeechRecognition; delete window.SpeechRecognition")
    pg.click("#tcAsk"); pg.click("#asMic")
    assert "клавиатуре iPhone" in pg.inner_text("#asLog")


# ---------- P1 behind its flag: profile on the server, ratings, the assistant's messages, #rate= / #briefing links ----------
P1 = "localStorage.setItem('japan2026.assistant.p1', '1')"


def test_ratings_and_messages_stay_off_when_a_phone_turns_them_off(app):
    fake = FakeSupabase.seeded(); a, san = guest(app, fake, now="2026-10-19T10:00:00+09:00"); pg = a.page
    pg.evaluate("localStorage.setItem('japan2026.assistant.p1', '0'); renderShell()")
    assert pg.locator("#tcAsk .as-dot").count() == 0
    pg.click("#tcAsk")
    assert pg.inner_text("#asRate") == "" and pg.locator("[data-notify]").count() == 0
    until(pg, "Api.status().pending === 0")
    assert not fake.ai_profiles                                                     # nothing goes to the server either


def test_with_the_flag_places_that_ended_are_rated_privately_and_the_profile_syncs(app):
    fake = FakeSupabase.seeded(); a, san = guest(app, fake, now="2026-10-19T10:00:00+09:00"); pg = a.page
    fake.ai_sent.append({"member": san, "key": "morning:2026-10-19", "day": "2026-10-19", "kind": "morning", "ref": "day:3",
                         "title": "Доброе утро, <Саня>!", "body": "Сегодня Киото"})
    pg.evaluate(P1); pg.evaluate("renderShell()")
    assert pg.inner_text("#tcAsk .as-dot") == "3"                                   # d3e1, d3e2, d3e3 have ended by 10:00
    pg.click("#tcAsk")
    until(pg, "Api.status().pending === 0 && /Доброе утро/.test(document.getElementById('asRate').textContent)")
    assert fake.ai_profiles[san]["name"] == "Саня" and fake.ai_profiles[san]["food"] == "халяль"
    assert "Доброе утро, <Саня>!" in pg.inner_text("#asRate")                       # the inbox is text, not markup
    card = pg.locator("[data-rate='d3e3']")
    assert "Тэнрю-дзи" in card.inner_text() and card.locator("[data-rate-save]").is_disabled()
    card.locator("[data-star='4']").click()
    card.locator("input").fill("Тихо и красиво")
    card.locator("[data-rate-save]").click()
    until(pg, "Api.status().pending === 0")
    assert fake.ai_feedback[(san, "d3e3")] == {"ref": "d3e3", "kind": "place", "day": 3, "stars": 4, "comment": "Тихо и красиво"}
    assert pg.locator("[data-rate='d3e3']").count() == 0 and "видите только вы" in pg.inner_text("#asLog")
    assert pg.evaluate("Api.run('feedback_averages', {})") == []                   # one rating is never shown to the group


def test_a_rate_link_opens_the_assistant_on_that_place(app):
    fake = FakeSupabase.seeded()
    a, san = guest(app, fake, now="2026-10-19T10:00:00+09:00", url_suffix="#rate=d3e9")
    pg = a.page
    pg.evaluate(P1)
    until(pg, "!!document.querySelector('#asWrap')")                               # opened by the link once signed in
    if pg.locator("#asProfLater").count(): pg.click("#asProfLater")                # a first run asks the profile first
    until(pg, "!!document.querySelector('#asRate [data-rate=\"d3e9\"]')")
    assert "Гион" in pg.inner_text("[data-rate='d3e9']") and "#rate" not in pg.url


def test_questionnaire_seed_prefills_the_profile_to_confirm(app):
    fake = FakeSupabase.seeded()
    a, san = guest(app, fake, profile=False)
    fake.ai_profiles[san] = {"lang": "ru", "tone": "calm", "energy": "low", "interests": "винтаж, фото",
                             "food": "без свинины", "notes": "встаю в 9–10; <b>не</b> люблю долго ходить", "seed": True}
    pg = a.page
    pg.evaluate("renderShell()")
    pg.click("#tcAsk")
    until(pg, "!!document.getElementById('asSeed')")
    assert pg.locator("#asInterests").input_value() == "винтаж, фото" and pg.locator("#asFood").input_value() == "без свинины"
    assert pg.locator("#asNotes").input_value() == "встаю в 9–10; <b>не</b> люблю долго ходить"      # text, never markup
    assert pg.locator("[data-seg='energy'] [aria-checked='true']").get_attribute("data-v") == "low"
    assert pg.evaluate("localStorage.getItem('japan2026.assistant.profile.v1')") is None              # nothing applied silently
    pg.fill("#asName", "Саня"); pg.click("#asProfSave")
    saved = json.loads(pg.evaluate("localStorage.getItem('japan2026.assistant.profile.v1')"))
    assert saved["name"] == "Саня" and saved["notes"].startswith("встаю") and "seed" not in saved
    assert not a.errors


def test_every_member_gets_the_chat_and_no_camera_when_photos_are_off(app):
    fake = FakeSupabase.seeded()
    a, san = guest(app, fake)
    a.page.evaluate("localStorage.removeItem('japan2026.assistant.server'); renderShell()")
    a.page.click("#tcAsk")                                                                     # Сания: the in-app chat
    assert a.page.locator("#asText").is_visible() and a.page.locator("#asPhoto").count() == 0  # DeepSeek: no photos
    assert not a.errors


def test_tools_mark_a_task_done_and_edit_a_stop_and_the_journal_is_for_hosts(app):
    fake = FakeSupabase.seeded(); a, san = guest(app, fake); pg = a.page
    fake.assistant_reply = {"reply": "Готово к применению.", "actions": [
        {"id": "a1", "kind": "task", "ref": "bk:sky", "title": "Shibuya Sky", "done": True},
        {"id": "a2", "kind": "edit", "stop_id": "d3e3", "day_n": 3, "title": "Тэнрю-дзи, сад дзен", "changes": {"note": "Взять зонт"}, "how": "propose", "scope": "group"}]}
    pg.click("#tcAsk"); ask(pg, "Отметь билет и добавь заметку")
    assert "Отметить сделанным" in pg.inner_text("[data-act='1:a1']") and "заметка → Взять зонт" in pg.inner_text("[data-act='1:a2']")
    pg.click("[data-apply='1:a1']"); pg.click("[data-apply='1:a2']")
    until(pg, "Api.status().pending === 0")
    assert fake.task_state[(san, "bk:sky")]["done"] is True
    p = fake.proposals[-1]
    assert p["kind"] == "comment" and p["ref"] == "d3e3" and "Взять зонт" in p["note"]
    assert pg.locator("#asJournal").count() == 0                                   # a guest has no journal
    h = logged(app, fake, fake.host_id, fake.host_pin, state={"prevDay": 3, "prevTime": "06:00"})
    fake.ai_log = [{"at": "2026-10-19T01:00:00Z", "who": "Сания", "q": "где поесть халяль в Гионе", "kind": "chat", "model": "deepseek", "in": 3000, "out": 200, "ok": True}]
    h.page.evaluate(f"localStorage.setItem('japan2026.assistant.profile.v1', {json.dumps(json.dumps(PROFILE))}); localStorage.setItem('japan2026.assistant.server', 'all'); renderShell()")
    h.page.click("#tcAsk"); h.page.click("#asJournal")
    until(h.page, "!!document.querySelector('#asWrap .tc-group')")
    txt = h.page.inner_text("#asWrap")
    assert "1 вопрос" in txt and "Сания — 1" in txt and "где поесть халяль в Гионе" in txt and "халяль (1)" in txt
    assert not a.errors and not h.errors
