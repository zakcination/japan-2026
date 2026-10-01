/* ---------- trips as files: ?trip=<id> picks one from trips/index.json (baked in) ----------
   The template is baked into the page. Any other trip comes from trips/<id>.json on the same site,
   network first; the last good copy is kept on the phone for offline. A local copy (edits made here,
   an imported file, a #trip= link) always wins until «Вернуться к общей версии». */
const Trips = (() => {
  const ID_KEY = 'japan2026.tripid.v1', SHARED_KEY = 'japan2026.shared.v2';
  const LIST = Array.isArray(DATA.trips) && DATA.trips.length ? DATA.trips : [{ id: 'template', name: TPL.name }];
  const known = id => typeof id === 'string' && /^[a-z0-9-]{1,40}$/.test(id) && LIST.some(t => t.id === id);
  const get = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const put = (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} };
  /* one offline copy per trip: {<id>: {at, trip}} */
  const copies = () => { try { const c = JSON.parse(get(SHARED_KEY) || '{}'); return c && typeof c === 'object' && !Array.isArray(c) ? c : {}; } catch (e) { return {}; } };
  function copyOf(tid) {
    if (tid === 'template') return { at: null, trip: clone(TPL) };
    const c = copies()[tid]; const t = c && Core.cleanTrip(c.trip);
    return t ? { at: c.at, trip: t } : null;
  }
  function keep(tid, trip) { const c = copies(); c[tid] = { at: Date.now(), trip }; put(SHARED_KEY, JSON.stringify(c)); }

  let id = known(get(ID_KEY)) ? get(ID_KEY) : 'template';
  let asked = null;                 // a ?trip= link that differs from the local copy being shown
  let net = 'none';                 // none | ok | offline
  const linkId = new URLSearchParams(location.search).get('trip');

  /* a different trip brings its own people, start date and currency; only the theme stays */
  function useSettingsOf() { const theme = SET.theme; put(SET_KEY, JSON.stringify({ theme })); loadSettings(); }
  function resetMarks() { S.done = {}; S.skip = {}; S.delay = {}; S.spent = {}; S.walked = {}; save(); }
  const base = () => (copyOf(id) || copyOf('template')).trip;

  /* runs once, before the first render */
  if (known(linkId) && linkId !== id) {
    if (isCustom() && T.id !== linkId) asked = linkId;
    else { id = linkId; put(ID_KEY, id); if (!isCustom()) { T = base(); useSettingsOf(); resetMarks(); } }
  } else if (known(linkId)) put(ID_KEY, id);
  if (!isCustom()) { T = base(); loadSettings(); }

  async function fetchTrip(tid) {
    if (tid === 'template') return clone(TPL);
    if (!/^https?:$/.test(location.protocol)) return null;
    try {
      const res = await fetch(`trips/${tid}.json`, { cache: 'no-cache' });
      if (!res.ok) throw new Error(res.status);
      const j = Core.cleanTrip(await res.json());
      if (!j) throw new Error('not a trip');
      keep(tid, j); net = 'ok';
      return j;
    } catch (e) { net = 'offline'; return null; }
  }

  /* fetch the chosen trip; apply it unless there is a local copy */
  async function refresh() {
    if (id === 'template') return false;
    const had = copyOf(id);
    const j = await fetchTrip(id);
    if (!j || isCustom()) return false;
    if (T.id === id && had && JSON.stringify(had.trip) === JSON.stringify(j)) return false;
    const first = T.id !== id;
    T = j; if (first) useSettingsOf(); else loadSettings();
    return true;
  }

  /* both need the target trip on the phone or the network; otherwise nothing changes */
  async function switchTo(next) {
    if (!known(next) || next === id) return true;
    const t = copyOf(next) ? (await fetchTrip(next)) || copyOf(next).trip : await fetchTrip(next);
    if (!t) return false;
    id = next; asked = null; put(ID_KEY, id); put(TRIP_KEY, null);
    T = t; useSettingsOf(); resetMarks();
    return true;
  }
  async function backToShared() {
    const target = asked || id;
    const t = (await fetchTrip(target)) || (copyOf(target) || {}).trip;
    if (!t) return false;
    put(TRIP_KEY, null);
    if (target !== id || T.id !== target) { id = target; asked = null; put(ID_KEY, id); T = t; useSettingsOf(); resetMarks(); }
    else { T = t; loadSettings(); }
    return true;
  }

  const two = n => String(n).padStart(2, '0');
  const dm = d => `${two(d.getDate())}.${two(d.getMonth() + 1)} ${two(d.getHours())}:${two(d.getMinutes())}`;
  function version() {
    if (isCustom()) return 'ваша версия на этом телефоне';
    const up = T.updated && !isNaN(Date.parse(T.updated)) ? dm(new Date(T.updated)) : null;
    if (id === 'template') return up ? `шаблон от ${up}` : 'шаблон';
    if (!copyOf(id) || T.id !== id) return 'шаблон — общая версия ещё не загружена';
    return (up ? `версия от ${up}` : 'общая версия') + (net === 'offline' ? ' · без сети, сохранённая копия' : '');
  }
  const nameOf = tid => (LIST.find(t => t.id === tid) || {}).name || tid;
  /* a published trip shares its own short page (its own link preview in WhatsApp); it forwards into the app with ?who=&code= and #links kept */
  const shareUrl = () => id === 'template' ? location.origin + location.pathname
    : LIST.some(t => t.id === id) ? location.origin + location.pathname.replace(/[^/]*$/, '') + `t/${id}.html` : location.origin + location.pathname + `?trip=${id}`;

  return { list: LIST, id: () => id, asked: () => asked, refresh, switchTo, backToShared, version, nameOf, shareUrl };
})();
