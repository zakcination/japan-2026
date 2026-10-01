/* ---------- notifications: Web Push from the group (iPhone: only once the app is on the Home Screen) ---------- */
const PUSH_KEY = 'japan2026.push.v1';
const vapidKey = () => ((DATA.groups || {})[T.id] || {}).vapid || (location.protocol === 'file:' || location.hostname === '127.0.0.1' ? (T.group || {}).vapid : '') || '';
const pushOn = () => { try { return localStorage.getItem(PUSH_KEY) || ''; } catch (e) { return ''; } };
const b64u = s => { const b = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - s.length % 4) % 4)); return Uint8Array.from(b, c => c.charCodeAt(0)); };
const pushable = () => 'serviceWorker' in navigator && 'PushManager' in window && typeof Notification !== 'undefined';

function pushHTML() {
  if (!Api.me() || !vapidKey()) return '';
  let row;
  if (!pushable()) row = Ios.isIOS() && !Ios.standalone()
    ? '<span>Уведомления<small>сначала «Поделиться» → «На экран „Домой“» — на iPhone они работают только так</small></span>' : '';
  else if (Notification.permission === 'denied') row = '<span>Уведомления выключены<small>включите в Настройках iPhone → Уведомления → Япония</small></span>';
  else if (pushOn()) row = `<span>Уведомления включены<small>предложения, решения, сроки покупки</small></span><button type="button" class="tc-btn" id="grPushOff">Выключить</button>`;
  else row = `<span>Уведомления<small>предложения, решения, сроки покупки</small></span><button type="button" class="tc-btn primary" id="grPushOn">Включить</button>`;
  return row ? `<div class="tc-flrow tc-push" id="grPush">${icon('bell')}${row}</div>` : '';
}
function wirePush(m) {
  const say = t => { const p = m.querySelector('#setMsg'); if (p) p.textContent = t; };
  const on = m.querySelector('#grPushOn'), off = m.querySelector('#grPushOff');
  if (on) on.addEventListener('click', async () => {
    on.disabled = true;
    try {
      if (await Notification.requestPermission() !== 'granted') { say('Без разрешения уведомления не придут.'); on.disabled = false; return; }
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64u(vapidKey()) });
      await Api.run('save_push', { p_sub: sub.toJSON() });
      try { localStorage.setItem(PUSH_KEY, sub.endpoint); } catch (e) {}
      closeSheet(); openSettings();
    } catch (e) { say('Не получилось включить уведомления — попробуйте ещё раз с интернетом.'); on.disabled = false; }
  });
  if (off) off.addEventListener('click', async () => {
    const ep = pushOn();
    try { const reg = await navigator.serviceWorker.ready; const sub = await reg.pushManager.getSubscription(); if (sub) await sub.unsubscribe(); } catch (e) {}
    try { localStorage.removeItem(PUSH_KEY); } catch (e) {}
    if (ep) Api.call('delete_push', { p_endpoint: ep }, null);
    closeSheet(); openSettings();
  });
}
/* the app is open: whatever the badge counted has been seen */
function clearBadge() {
  if (document.hidden) return;
  if (navigator.clearAppBadge) navigator.clearAppBadge().catch(() => {});
  if (navigator.serviceWorker && navigator.serviceWorker.controller) navigator.serviceWorker.controller.postMessage('badge:clear');
}
