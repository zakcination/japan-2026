/* ---------- trips as files: ?trip=<id> picks one from trips/index.json (baked in) ----------
   The template is baked into the page. Any other trip comes from trips/<id>.json on the same site,
   network first; the last good copy is kept on the phone for offline. A local copy (edits made here,
   an imported file, a #trip= link) always wins until «Вернуться к общей версии». */
const Trips = (() => {
  const ID_KEY = 'japan2026.tripid.v1', SHARED_KEY = 'japan2026.shared.v1';
  const LIST = Array.isArray(DATA.trips) && DATA.trips.length ? DATA.trips : [{ id: 'template', name: TPL.name }];
  const known = id => typeof id === 'string' && /^[a-z0-9-]{1,40}$/.test(id) && LIST.some(t => t.id === id);
  const get = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const put = (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} };
  const readShared = () => { try { const c = JSON.parse(get(SHARED_KEY) || 'null'); const t = c && Core.cleanTrip(c.trip); return t ? { ...c, trip: t } : null; } catch (e) { return null; } };

  let id = known(get(ID_KEY)) ? get(ID_KEY) : 'template';
  let asked = null;                 // a ?trip= link that differs from the local copy being shown
  let net = 'none';                 // none | ok | offline
  const linkId = new URLSearchParams(location.search).get('trip');

  function useSettingsOf(trip) {   // a different trip brings its own people, start date and currency
    const theme = SET.theme;
    put(SET_KEY, null); loadSettings(); SET.theme = theme; saveSettings();
  }
  function resetMarks() { S.done = {}; S.skip = {}; S.delay = {}; S.spent = {}; S.walked = {}; save(); }
  function base() {
    if (id === 'template') return clone(TPL);
    const c = readShared();
    return c && c.id === id ? clone(c.trip) : clone(TPL);
  }

  /* runs once, before the first render */
  if (known(linkId) && linkId !== id) {
    if (isCustom() && T.id !== linkId) asked = linkId;
    else { id = linkId; put(ID_KEY, id); if (!isCustom()) { T = base(); useSettingsOf(T); resetMarks(); } }
  } else if (known(linkId)) put(ID_KEY, id);
  if (!isCustom()) { T = base(); loadSettings(); }

  /* fetch the chosen trip; apply it unless there is a local copy */
  async function refresh() {
    if (id === 'template' || !/^https?:$/.test(location.protocol)) return false;
    try {
      const res = await fetch(`trips/${id}.json`, { cache: 'no-cache' });
      if (!res.ok) throw new Error(res.status);
      const j = Core.cleanTrip(await res.json());
      if (!j) throw new Error('not a trip');
      const old = readShared();
      put(SHARED_KEY, JSON.stringify({ id, at: Date.now(), trip: j }));
      net = 'ok';
      if (isCustom()) return false;
      if (old && old.id === id && JSON.stringify(old.trip) === JSON.stringify(j) && T.id === id) return false;
      const first = !(old && old.id === id);
      T = j; if (first) useSettingsOf(T); else loadSettings();
      return true;
    } catch (e) { net = 'offline'; return false; }
  }

  function switchTo(next) {
    if (!known(next) || next === id) return;
    id = next; asked = null; put(ID_KEY, id);
    put(TRIP_KEY, null);
    T = base(); useSettingsOf(T); resetMarks();
  }
  function backToShared() {
    put(TRIP_KEY, null);
    if (asked) { id = asked; asked = null; put(ID_KEY, id); T = base(); useSettingsOf(T); resetMarks(); return; }
    T = base(); loadSettings();
  }

  const two = n => String(n).padStart(2, '0');
  const dm = d => `${two(d.getDate())}.${two(d.getMonth() + 1)} ${two(d.getHours())}:${two(d.getMinutes())}`;
  function version() {
    if (isCustom()) return 'ваша версия на этом телефоне';
    const up = T.updated && !isNaN(Date.parse(T.updated)) ? dm(new Date(T.updated)) : null;
    if (id === 'template') return up ? `шаблон от ${up}` : 'шаблон';
    const c = readShared();
    if (!c || c.id !== id) return 'шаблон — общая версия ещё не загружена';
    return (up ? `версия от ${up}` : 'общая версия') + (net === 'offline' ? ' · без сети, сохранённая копия' : '');
  }
  const nameOf = tid => (LIST.find(t => t.id === tid) || {}).name || tid;
  const shareUrl = () => location.origin + location.pathname + (id === 'template' ? '' : `?trip=${id}`);

  return { list: LIST, id: () => id, asked: () => asked, refresh, switchTo, backToShared, version, nameOf, shareUrl };
})();
