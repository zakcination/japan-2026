/* ---------- group API: Supabase over plain fetch — anonymous session, RPCs, outbox, polling ---------- */
const Api = (() => {
  const SES = 'japan2026.session.v1', ST = 'japan2026.group.v1', OUT = 'japan2026.outbox.v1';
  const get = k => { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } };
  const put = (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  let session = get(SES), state = get(ST), outbox = get(OUT) || [], flushing = null, timer = null;
  const status = { online: true, pending: outbox.length, at: state ? state._at || null : null, error: null };

  const cfg = () => (T && T.group && /^https:\/\/[a-z0-9-]+\.supabase\.co$/.test(T.group.url || '') && T.group.anon) ? T.group : null;
  const enabled = () => !!cfg() && !!T.id;
  const emit = () => window.dispatchEvent(new Event('japan2026:group'));

  async function http(path, body, auth, method = 'POST', raw = false, ctype) {
    const c = cfg();
    const res = await fetch(c.url + path, { method, headers: { apikey: c.anon, Authorization: 'Bearer ' + (auth || c.anon),
      'Content-Type': ctype || 'application/json' }, body: raw ? body : body == null ? undefined : JSON.stringify(body) });
    status.online = true;
    if (raw && method === 'GET') { if (!res.ok) throw Object.assign(new Error('HTTP ' + res.status), { status: res.status }); return res.blob(); }
    const j = await res.json().catch(() => null);
    if (!res.ok) throw Object.assign(new Error((j && (j.message || j.msg)) || 'HTTP ' + res.status), { status: res.status, body: j });
    return j;
  }
  async function ensureSession() {
    if (session && session.access_token) return session;
    const s = await http('/auth/v1/signup', {});
    session = { access_token: s.access_token, refresh_token: s.refresh_token }; put(SES, session);
    return session;
  }
  async function refreshToken() {
    if (!session || !session.refresh_token) throw Object.assign(new Error('login'), { status: 401 });
    const s = await http('/auth/v1/token?grant_type=refresh_token', { refresh_token: session.refresh_token });
    session = { ...session, access_token: s.access_token, refresh_token: s.refresh_token || session.refresh_token }; put(SES, session);
  }
  async function rpc(name, args, retried) {
    await ensureSession();
    try { return await http('/rest/v1/rpc/' + name, args || {}, session.access_token); }
    catch (e) {
      if (e.status === 401 && !retried) { await refreshToken(); return rpc(name, args, true); }
      throw e;
    }
  }
  const netErr = e => !e.status;            // fetch threw: no signal / blocked

  async function login(memberId, pin) {
    try {
      const r = await rpc('claim_member', { p_member: memberId, p_pin: pin });
      if (r && r.error) return { ok: false, error: r.error };
      session = { ...session, member: r }; put(SES, session);
      await refresh();
      return { ok: true };
    } catch (e) { return { ok: false, error: netErr(e) ? 'Нет сети' : e.message }; }
  }
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
      if (netErr(e)) status.online = false; else if (e.status === 401 || e.message === 'login') status.error = 'login'; else status.error = e.message;
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
          if (e.status === 401 || e.message === 'login') { status.error = 'login'; break; }
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
    timer = setInterval(() => { if (!document.hidden && session && session.member) { flush(); refresh(); } }, 30000);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden && enabled() && session && session.member) { flush(); refresh(); } });
  window.addEventListener('online', () => flush());

  async function upload(path, blob) {
    await ensureSession();
    await http('/storage/v1/object/tickets/' + path.split('/').map(encodeURIComponent).join('/'), blob, session.access_token, 'POST', true, blob.type || 'application/octet-stream');
    return path;
  }
  async function download(path) {
    await ensureSession();
    return http('/storage/v1/object/authenticated/tickets/' + path.split('/').map(encodeURIComponent).join('/'), null, session.access_token, 'GET', true);
  }

  if (enabled() && session && session.member) { poll(); setTimeout(() => { flush(); refresh(); }, 0); }
  return { enabled, me: () => (session && session.member) || null, state: () => state, status: () => ({ ...status }),
           login: (m, p) => login(m, p).then(r => { if (r.ok) poll(); return r; }), logout, memberNames, refresh, call, flush, upload, download };
})();
