"""«Спросить в Claude»: ✦ for everyone until the owner turns the server assistant on; the question goes to claude.ai with the day as context."""
import json
from urllib.parse import urlparse, parse_qs
from test_kz_cards import OURS


def open_claude(app):
    a = app(trip=OURS, state={"prevDay": 3, "prevTime": "06:00"})
    a.page.evaluate("window.open = (u) => { window.__opened = u; }")
    a.page.click("#tcAsk")
    a.page.wait_for_selector("#clGo")
    return a


def test_question_opens_claude_with_the_day_and_profile(app):
    a = open_claude(app)
    pg = a.page
    pg.evaluate("localStorage.setItem('japan2026.assistant.profile.v1', JSON.stringify({name: 'Мирас', lang: 'ru', food: 'халяль', notes: '<b>x</b>', at: 1}))")
    pg.click("[data-cl-chip='1']")
    assert pg.locator("#clText").input_value().startswith("Где поесть халяль")
    pg.click("#clGo")
    url = pg.evaluate("window.__opened")
    assert url.startswith("https://claude.ai/new?q=")
    q = parse_qs(urlparse(url).query)["q"][0]
    assert "Вопрос: Где поесть халяль" in q and "День 3" in q and "Бамбуковая роща" in q and "嵐山" in q
    assert "Меня зовут Мирас" in q and "Еда: халяль" in q and "110" in q and len(q) <= 6000
    assert "<b>x</b>" in pg.locator("#clPre").text_content()                       # shown as text
    assert a.errors == []


def test_empty_question_asks_for_one_and_profile_comes_back(app):
    a = open_claude(app)
    pg = a.page
    pg.click("#clGo")
    assert pg.evaluate("window.__opened") is None and "Напишите вопрос" in pg.locator("#clMsg").inner_text()
    pg.click("#clProf")
    pg.fill("#asName", "Айкош"); pg.click("#asProfSave")
    pg.wait_for_selector("#clGo")                                                # back to «Спросить в Claude», not the server chat
    assert "Меня зовут Айкош" in pg.locator("#clPre").text_content()
    assert a.errors == []


def test_on_money_tab_no_button(app):
    a = app(trip=OURS, state={"prevDay": 3, "prevTime": "06:00"})
    a.page.click(".tc-tab[data-tab='stats']")
    assert a.page.locator("#tcAsk").count() == 0
