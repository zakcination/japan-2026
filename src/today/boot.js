/* ---------- boot: title, open/close the screen, restore the tab, keep it fresh, install on a web host ---------- */
function setTitle() {
  const t = document.getElementById('tripTitle');
  if (t) t.textContent = '🇯🇵 ' + (T.name || 'Поездка');
  document.title = T.name || 'Поездка';
}

function openToday() { document.getElementById('today').hidden = false; S.open = true; save(); viewDay = null; renderShell(); }
function closeToday() { document.getElementById('today').hidden = true; S.open = false; save(); }
window.openToday = openToday;

document.getElementById('btnToday').addEventListener('click', openToday);
document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeTicket(); closeSheet(); } });
document.getElementById('today').addEventListener('click', e => { if (e.target.closest('[data-gear]')) openSettings(); });
setTitle();

tripFromHash().then(ok => { if (ok) { setTitle(); viewDay = null; renderShell(); } });
if (S.tab && TABS.some(t => t[0] === S.tab && t[0] !== 'map')) tab = S.tab;
refreshTickets().then(renderShell);
// '#map' in the link opens straight onto the map (also used by the map tests)
if (S.open === false || location.hash === '#map') document.getElementById('today').hidden = true; else renderShell();
setInterval(() => {
  const a = document.activeElement;
  if (document.getElementById('today').hidden) return;
  if (a && a.closest && a.closest('#today') && /INPUT|SELECT/.test(a.tagName)) return;   // don't wipe what is being typed
  renderShell();
}, 30000);

/* On a real web host (GitHub Pages) the guide installs as an app and keeps working offline. */
if (/^https?:$/.test(location.protocol) && /github\.io$|^localhost$|^127\.0\.0\.1$/.test(location.hostname)) {
  const add = (rel, href) => { const l = document.createElement('link'); l.rel = rel; l.href = href; document.head.appendChild(l); };
  add('manifest', 'manifest.webmanifest'); add('apple-touch-icon', 'icon-192.png');
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
}
window.addEventListener('japan2026:wx', renderShell);
window.addEventListener('japan2026:tick', renderShell);
document.addEventListener('visibilitychange', () => { if (!document.hidden) renderShell(); });
