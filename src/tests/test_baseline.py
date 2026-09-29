def test_today_screen_renders_before_refactor(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})
    assert a.page.locator("#today").is_visible()
    assert "Фудзи" in a.page.inner_text("#today")
    assert a.errors == []
