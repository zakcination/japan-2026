/* ---------- boot: title, open/close the screen, restore the tab, keep it fresh, install on a web host ---------- */
function setTitle() {
  const t = document.getElementById('tripTitle');
  if (t) t.textContent = '🇯🇵 ' + (T.name || 'Поездка');
  document.title = T.name || 'Поездка';
}

function openToday() { document.getElementById('today').hidden = false; S.open = true; save(); viewDay = null; renderShell(); }
function closeToday() { document.getElementById('today').hidden = true; S.open = false; save(); Ios.keepAwake(false); }
window.openToday = openToday;

document.getElementById('btnToday').addEventListener('click', openToday);
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeTicket(); closeSheet(); const l = document.getElementById('tcLocal'); if (l && !l.hidden) l.click(); } });
document.getElementById('today').addEventListener('click', e => { if (e.target.closest('[data-gear]')) openSettings(); });
setTitle();

tripFromHash().then(ok => { if (ok) { setTitle(); viewDay = null; renderShell(); startGroup(); } });
if (S.tab && TABS.some(t => t[0] === S.tab && t[0] !== 'map')) tab = S.tab;
refreshTickets().then(renderShell);
Trips.refresh().then(changed => { if (changed) { setTitle(); viewDay = null; renderShell(); startGroup(); autoSyncPlan(); } });
// group: first open asks «Кто вы?» once; server updates re-render unless a sheet is open
if (Api.me() && Ios.standalone()) track('installed');
/* «Кто вы?»: once per phone (or whenever an invite link is opened) — also when the trip arrives after start,
   since a brand-new phone begins on the built-in template and fetches ?trip= a moment later */
function startGroup() {
  if (!Api.enabled() || Api.me()) return;
  const sh = document.getElementById('tcSheet'); if (sh && !sh.hidden) return;
  let asked = null; try { asked = localStorage.getItem(LOGIN_ASKED); } catch (e) {}
  if (!asked || INVITE) openLogin();
}
startGroup();
window.addEventListener('japan2026:group', () => { autoSyncPlan(); expSync(); const sh = document.getElementById('tcSheet'); if (!sh || sh.hidden) renderShell(); });
// installed on the Home Screen: ask Safari to keep the tickets and the trip copy
if (Ios.standalone() && navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
// '#map' in the link opens straight onto the map (also used by the map tests)
const DEEP = /^#(tab|prep|task|add)=/.test(location.hash);          // a deep link always opens the app screen
if ((S.open === false && !DEEP) || location.hash === '#map') document.getElementById('today').hidden = true; else { renderShell(); if (!expFromLink()) handleDeepLink(); }
/* expenses: read from the phone's database, then exchanged with the group whenever the group state changes */
ExpStore.load();
window.addEventListener('japan2026:exp', () => { expSync(); renderShell(); });
setInterval(() => {
  const a = document.activeElement;
  if (document.getElementById('today').hidden) return;
  if (a && a.closest && a.closest('#today') && /INPUT|SELECT/.test(a.tagName)) return;   // don't wipe what is being typed
  renderShell();
}, 30000);

/* On a real web host (GitHub Pages) the guide installs as an app and keeps working offline. */
if (/^https?:$/.test(location.protocol) && /github\.io$|^localhost$|^127\.0\.0\.1$/.test(location.hostname)) {
  const add = (rel, href) => { const l = document.createElement('link'); l.rel = rel; l.href = href; document.head.appendChild(l); };
  add('manifest', Trips.id() === 'template' ? 'manifest.webmanifest' : `manifest-${Trips.id()}.webmanifest`);
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
}
window.addEventListener('japan2026:wx', renderShell);
window.addEventListener('japan2026:tick', renderShell);
document.addEventListener('visibilitychange', () => { if (!document.hidden) { renderShell(); clearBadge(); } });
clearBadge();
if (location.protocol === 'file:' || location.hostname === '127.0.0.1') Object.assign(window, { renderShell, openPrep, Api, track, setJoin, openSettings, ExpStore, Exp });
