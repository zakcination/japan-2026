"""Stage 2: turning notifications on in ⚙ stores the phone's push subscription; off removes it. The push service is mocked."""
from conftest import until, IPHONE_UA
from fake_supabase import FakeSupabase
from test_group_join import logged

MOCK = """(() => {
  window.PushManager = function () {};
  window.__perm = 'default';
  Notification.requestPermission = async () => (window.__perm = 'granted');
  Object.defineProperty(Notification, 'permission', { get: () => window.__perm, configurable: true });
  let sub = null;
  const pm = { subscribe: async o => (sub = { endpoint: 'https://push.example/abc', key: o.applicationServerKey,
                 toJSON() { return { endpoint: this.endpoint, keys: { p256dh: 'k', auth: 'a' } }; }, unsubscribe: async () => { sub = null; return true; } }),
               getSubscription: async () => sub };
  Object.defineProperty(navigator, 'serviceWorker', { value: { ready: Promise.resolve({ pushManager: pm }), controller: null }, configurable: true });
})()"""


def test_notifications_on_and_off_store_and_drop_the_subscription(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = logged(app, fake, san, "4821")
    g.page.evaluate(MOCK)
    g.page.click("#tcGear")
    g.page.click("#grPushOn")
    until(g.page, "!!document.getElementById('grPushOff')")
    assert fake.push_subs["https://push.example/abc"]["member"] == san
    assert g.page.evaluate("localStorage.getItem('japan2026.push.v1')") == "https://push.example/abc"
    assert g.page.evaluate("document.getElementById('grPushOff').getBoundingClientRect().height") >= 44
    g.page.click("#grPushOff")
    until(g.page, "!!document.getElementById('grPushOn') && Api.status().pending === 0")
    assert fake.push_subs == {}


def test_iphone_safari_says_add_to_home_screen_first(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = logged(app, fake, san, "4821", ua=IPHONE_UA)
    g.page.evaluate("delete window.PushManager")
    g.page.click("#tcGear")
    assert "На экран „Домой“" in g.page.inner_text("#grPush") and g.page.locator("#grPushOn").count() == 0
