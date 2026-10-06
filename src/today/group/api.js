/* ---------- group API: Supabase over plain fetch — anonymous session, RPCs, outbox, polling ---------- */
const Api = (() => {
  const SES = 'japan2026.session.v1', ST = 'japan2026.group.v1', OUT = 'japan2026.outbox.v1';
  const get = k => { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } };
  const put = (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  let session = get(SES), state = get(ST), outbox = get(OUT) || [], flushing = null, timer = null, refreshing = null;
  const status = { online: true, pending: outbox.length, at: state ? state._at || null : null, error: null };

  /* The Supabase project is baked into the page per trip (DATA.groups), never taken from a trip file or link:
     an imported trip must not be able to point the app — and a PIN — at someone else's project.
     Local tests (file:, 127.0.0.1) may use the trip's own `group` to reach the fake. */
  const TEST_HOST = location.protocol === 'file:' || location.hostname === '127.0.0.1';
  const valid = g => g && /^https:\/\/[a-z0-9-]+\.supabase\.co$/.test(g.url || '') && typeof g.anon === 'string' && g.anon ? g : null;
  const cfg = () => {
    if (!T || !T.id) return null;
    return valid((DATA.groups || {})[T.id]) || (TEST_HOST ? valid(T.group) : null);
  };
  // a saved session belongs to one project
  if (session && (!cfg() || session.url !== cfg().url)) { session = null; put(SES, null); }
  const enabled = () => !!cfg() && !!T.id;
  const emit = () => window.dispatchEvent(new Event('japan2026:group'));

  async function http(path, body, auth, method = 'POST', raw = false, ctype) {
    const c = cfg();
    /* a stalled request (bad signal) must not hold the queue forever: give up after 15 s, like no signal */
    const ac = typeof AbortController === 'function' ? new AbortController() : null, tm = ac && setTimeout(() => ac.abort(), 15000);
    let res;
    try {
      res = await fetch(c.url + path, { method, signal: ac ? ac.signal : undefined, headers: { apikey: c.anon, Authorization: 'Bearer ' + (auth || c.anon),
        'Content-Type': ctype || 'application/json' }, body: raw ? body : body == null ? undefined : JSON.stringify(body) });
    } finally { if (tm) clearTimeout(tm); }
    status.online = true;
    if (raw && method === 'GET') { if (!res.ok) throw Object.assign(new Error('HTTP ' + res.status), { status: res.status }); return res.blob(); }
    const j = await res.json().catch(() => null);
    if (!res.ok) throw Object.assign(new Error((j && (j.message || j.msg)) || 'HTTP ' + res.status), { status: res.status, body: j });
    return j;
  }
  async function ensureSession() {
    if (session && session.access_token) return session;
    const s = await http('/auth/v1/signup', {});
    session = { url: cfg().url, access_token: s.access_token, refresh_token: s.refresh_token }; put(SES, session);
    return session;
  }
  /* one refresh at a time; if the refresh token is dead too, drop the session so the next PIN signs in afresh */
  function refreshToken() {
    if (refreshing) return refreshing;
    refreshing = (async () => {
      if (!session || !session.refresh_token) { dropSession(); throw Object.assign(new Error('login'), { status: 401 }); }
      try {
        const s = await http('/auth/v1/token?grant_type=refresh_token', { refresh_token: session.refresh_token });
        session = { ...session, access_token: s.access_token, refresh_token: s.refresh_token || session.refresh_token }; put(SES, session);
      } catch (e) {
        if (!netErr(e)) { dropSession(); throw Object.assign(new Error('login'), { status: 401 }); }
        throw e;
      }
    })().finally(() => { refreshing = null; });
    return refreshing;
  }
  /* sign-in lost (tokens dead, device no longer bound): keep the cached state and the outbox, ask for the PIN again */
  function dropSession() { session = null; put(SES, null); status.error = 'login'; }
  const authErr = e => e.status === 401 || e.message === 'login' || /not a member/.test(e.message || '');
  async function rpc(name, args, retried) {
    await ensureSession();
    try { return await http('/rest/v1/rpc/' + name, args || {}, session.access_token); }
    catch (e) {
      if (e.status === 401 && !retried) { await refreshToken(); return rpc(name, args, true); }
      throw e;
    }
  }
  const netErr = e => !e.status;            // fetch threw: no signal / blocked

  async function login(memberId, pin, code) {
    try {
      const r = await rpc('claim_member', code ? { p_member: memberId, p_pin: pin, p_code: code } : { p_member: memberId, p_pin: pin });
      if (r && r.error) return { ok: false, error: r.error };
      session = { ...session, member: r }; put(SES, session);
      await refresh();
      return { ok: true };
    } catch (e) { return { ok: false, error: netErr(e) ? 'Нет сети' : e.message }; }
  }
  function reauth() { session = null; put(SES, null); emit(); }         // «Войти снова»: keeps state and outbox
  /* online-only calls whose answer the UI needs (e.g. a new member's invite code) */
  async function run(name, args) { const r = await rpc(name, args); refresh(); return r; }
  function logout() { session = null; state = null; outbox = []; put(SES, null); put(ST, null); put(OUT, null); status.pending = 0; emit(); }
  async function memberNames() { return rpc('member_names', { p_trip: T.id }); }

  async function refresh() {
    if (!enabled() || !session || !session.member) return false;
    try {
      const s = await rpc('group_state', { p_trip: T.id });
      // keep optimistic changes that are still waiting in the outbox
      const pend = outbox.slice(); const was = JSON.stringify(state && { ...state, _at: 0 });
      state = s; pend.forEach(p => { if (APPLY[p.id]) try { APPLY[p.id](state); } catch (e) {} });
      state._at = Date.now(); put(ST, state); status.at = state._at; status.error = status.error === 'login' ? null : status.error;
      const changed = was !== JSON.stringify({ ...state, _at: 0 });
      emit(); return changed;
    } catch (e) {
      if (netErr(e)) status.online = false; else if (authErr(e)) { if (session) dropSession(); else status.error = 'login'; } else status.error = e.message;
      emit(); return false;
    }
  }

  const APPLY = {};                         // outbox item id → optimistic change, replayed over refreshed state (this page load only)
  function call(name, args, apply) {
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
    if (state && apply) { try { apply(state); } catch (e) {} put(ST, state); APPLY[id] = apply; }
    outbox.push({ id, name, args }); put(OUT, outbox); status.pending = outbox.length; emit();
    flush();
  }
  function flush() {
    if (flushing || !outbox.length || !enabled()) return flushing || Promise.resolve();
    flushing = (async () => {
      while (outbox.length) {
        const it = outbox[0];
        try { await rpc(it.name, it.args); }
        catch (e) {
          if (netErr(e)) { status.online = false; setTimeout(flush, 15000); break; }
          if (authErr(e)) { if (session) dropSession(); else status.error = 'login'; break; }   // keep the outbox
          status.error = e.message;                        // rejected by the server: drop it, the refresh shows the truth
        }
        outbox.shift(); delete APPLY[it.id]; put(OUT, outbox); status.pending = outbox.length;
      }
      flushing = null; emit();
      if (!outbox.length) await refresh();
    })();
    return flushing;
  }
  function poll() {
    clearInterval(timer);
    timer = setInterval(() => { if (!document.hidden && session && session.member) { if (outbox.length) flush(); else refresh(); } }, 30000);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden && enabled() && session && session.member) { if (outbox.length) flush(); else refresh(); } });
  window.addEventListener('online', () => flush());

  const safePath = p => { const me = session && session.member && session.member.id; const parts = String(p).split('/');
    if (!me || parts[0] !== me || parts.some(x => !x || x === '.' || x === '..')) throw new Error('bad path'); return p; };
  async function upload(path, blob) {
    safePath(path);
    await ensureSession();
    await http('/storage/v1/object/tickets/' + path.split('/').map(encodeURIComponent).join('/'), blob, session.access_token, 'POST', true, blob.type || 'application/octet-stream');
    return path;
  }
  async function remove(path) {            // the file behind a deleted ticket; only one's own folder (the server enforces it too)
    safePath(path);
    await ensureSession();
    return http('/storage/v1/object/tickets', { prefixes: [path] }, session.access_token, 'DELETE');
  }
  async function download(path) {
    await ensureSession();
    return http('/storage/v1/object/authenticated/tickets/' + path.split('/').map(encodeURIComponent).join('/'), null, session.access_token, 'GET', true);
  }

  if (enabled() && session && session.member) { poll(); setTimeout(() => { flush(); refresh(); }, 0); }
  return { enabled, me: () => (session && session.member) || null, state: () => state, status: () => ({ ...status }),
           login: (m, p, c) => login(m, p, c).then(r => { if (r.ok) { status.error = null; poll(); flush(); } return r; }), logout, reauth, run, memberNames, refresh, call, flush, upload, download, remove };
})();
