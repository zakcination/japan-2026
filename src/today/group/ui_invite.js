/* ---------- activation: the invite kit, the first run, WhatsApp nudges, the private funnel ---------- */
const ONBOARDED = 'japan2026.onboarded.v1', TRACKED = 'japan2026.tracked.v1';
const withQ = (u, q) => u + (u.includes('?') ? '&' : '?') + q;
/* the personal link: ?who= opens that person's PIN; &code= (one time) lets a guest set it the first time */
const inviteUrl = (id, code) => withQ(Trips.shareUrl(), `who=${encodeURIComponent(id)}${code ? '&code=' + encodeURIComponent(code) : ''}`);
const waUrl = text => 'https://wa.me/?text=' + encodeURIComponent(text);
function inviteText(name, url) {
  return `${name}, привет! Это приложение нашей поездки в Японию: план по дням, билеты и что кому купить.\n`
    + `1. Откройте ссылку в Safari\n2. Выберите себя и придумайте PIN\n3. Поделиться → На экран «Домой»\n${url}`;
}
function qrSVG(text) {
  try { const q = qrcode(0, 'M'); q.addData(text); q.make(); return q.createSvgTag({ cellSize: 4, margin: 8, scalable: true, title: 'QR-код приглашения' }); }
  catch (e) { return ''; }
}

/* ⚙ «Пригласить» on a guest row: ask the server for the guest's link (a code only while they have no PIN) */
function openInvite(id) {
  const m = (Api.state().members || []).find(x => x.id === id); if (!m) return;
  Api.run('invite_link', { p_member: id }).then(r => showInvite(m.name, id, r && r.code))
    .catch(e => { const p = document.querySelector('#tcSheet #setMsg'); if (p) p.textContent = e && !e.status ? 'Нет сети — попробуйте позже' : 'Не получилось — попробуйте ещё раз'; });
}
function showInvite(name, id, code) {
  const who = ((Api.state() || {}).members || []).find(x => x.id === id);
  if (!id || (who && who.role !== 'guest')) { closeSheet(); openSettings(); return; }   // a host's PIN is set by the owner: no invite
  const url = inviteUrl(id, code), text = inviteText(name, url);
  sheet('Пригласить: ' + name, `<p class="tc-sub">${code ? 'Ссылка одноразовая: по ней можно войти в первый раз и придумать PIN.' : 'PIN уже есть — по ссылке откроется вход.'}</p>
    <pre class="tc-invite-text" id="grInviteText">${esc(text)}</pre>
    <input id="grInvite" type="hidden" value="${esc(url)}">
    <a class="tc-btn primary wide" id="grInviteWa" href="${esc(waUrl(text))}" target="_blank" rel="noopener">${icon('share')}Отправить в WhatsApp</a>
    <div class="tc-actions two">${navigator.share ? `<button type="button" class="tc-btn" id="grInviteShare">${icon('share')}Поделиться…</button>` : ''}
      <button type="button" class="tc-btn" id="grInviteCopy">Скопировать</button></div>
    <div class="tc-invite-qr" id="grInviteQr">${qrSVG(url)}</div><p class="tc-foot">Или покажите QR-код — его можно навести камерой iPhone.</p>`, s => {
    const cp = s.querySelector('#grInviteCopy');
    cp.addEventListener('click', () => (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject())
      .then(() => { cp.textContent = 'Скопировано'; }, () => { cp.textContent = 'Не получилось — выделите текст'; }));
    const sh = s.querySelector('#grInviteShare');
    if (sh) sh.addEventListener('click', () => navigator.share({ text }).catch(() => {}));
  });
}

/* the funnel: each event once per member on this phone; the server keeps it once per member anyway */
function track(ev) {
  const me = Api.me(); if (!me) return;
  let t = {}; try { t = JSON.parse(localStorage.getItem(TRACKED) || '{}') || {}; } catch (e) {}
  const k = me.id + ':' + ev; if (t[k]) return;
  t[k] = 1; try { localStorage.setItem(TRACKED, JSON.stringify(t)); } catch (e) {}
  Api.call('track', { p_event: ev }, null);
}
function funnelHTML() { return '<p class="tc-sub tc-funnel" id="grFunnel">Активность группы: загружаю…</p>'; }
function wireFunnel(m) {
  const p = m.querySelector('#grFunnel'); if (!p) return;
  Api.run('funnel_counts', {}).then(c => {
    p.textContent = `Приглашены ${c.members} · вошли ${c.login} · на экране «Домой» ${c.installed} · присоединились ${c.joined} · купили ${c.bought}`;
  }).catch(() => { p.textContent = 'Активность группы — нужна сеть'; });
}

/* right after the first sign-in on this phone: Home Screen → parts → «Дела» */
function onboarded() { try { return !!localStorage.getItem(ONBOARDED); } catch (e) { return true; } }
function openFirstRun(step) {
  step = step || (Ios.isIOS() && !Ios.standalone() ? 1 : 2);        // the Home Screen step only means something in iPhone Safari
  const me = Api.me(), s = Api.state() || {};
  if (step === 2 && (!me || me.role === 'host' || !(s.parts || []).length)) step = 3;
  if (step === 3) {
    try { localStorage.setItem(ONBOARDED, '1'); } catch (e) {}
    closeSheet(); go('tix'); return;
  }
  const inPart = id => (s.joins || []).some(j => j.member === me.id && j.scope === 'part' && j.ref === id && j.mode === 'in');
  const body = step === 1
    ? `<p class="tc-sub">${me && me.role !== 'host' && (s.parts || []).length ? 'Шаг 1 из 2. ' : ''}Так приложение открывается без интернета и не теряет билеты.</p>
      <ol class="tc-howto"><li>Нажмите «Поделиться» внизу Safari</li><li>«На экран „Домой“» → «Добавить»</li></ol>`
    : `<p class="tc-sub">Шаг 2 из 2. К чему вы присоединяетесь? Билеты на эти части появятся в «Делах».</p>
      <div class="tc-group">${s.parts.map(p => `<label class="tc-act tc-fr-row"><span>${esc(p.title)}</span>
        <input type="checkbox" switch data-fr-part="${esc(p.id)}"${inPart(p.id) ? ' checked' : ''}></label>`).join('')}</div>`;
  sheet(step === 1 ? 'На экран «Домой»' : 'Ваши части поездки', `<div id="grFirstRun">${body}
    <button type="button" class="tc-btn primary wide" id="grFrNext">${step === 1 ? 'Дальше' : 'Готово'}</button></div>`, m => {
    m.querySelectorAll('[data-fr-part]').forEach(i => i.addEventListener('change', () => setJoin('part', i.dataset.frPart, i.checked ? 'in' : 'none')));
    m.querySelector('#grFrNext').addEventListener('click', () => openFirstRun(step + 1));
  });
}

/* «Напомнить в WhatsApp»: the deadline and a link straight to it */
function nudgeHTML(text, url, inline) {
  if (inline === 'icon') return `<a class="tc-nudge-ic tc-nudge" href="${esc(waUrl(text + ': ' + url))}" target="_blank" rel="noopener" aria-label="Напомнить в WhatsApp" title="Напомнить в WhatsApp">${icon('share')}</a>`;
  return `<a class="${inline ? 'tc-link' : 'tc-btn'} tc-nudge" href="${esc(waUrl(text + ': ' + url))}" target="_blank" rel="noopener" aria-label="Напомнить в WhatsApp">${icon('share')}${inline ? 'Напомнить' : 'Напомнить в WhatsApp'}</a>`;
}
const deepLink = h => Trips.shareUrl() + '#' + h;
let FLASH = null;                         // the task a #task= link points at: highlighted for a moment, across re-renders

/* #tab=…, #prep=…, #task=… — handled once on load, then taken off the address */
function handleDeepLink() {
  const m = location.hash.match(/^#(tab|prep|task)=([A-Za-z0-9:_-]{1,80})$/); if (!m) return;
  history.replaceState(null, '', location.pathname + location.search);
  const [, k, v] = m;
  const sh = document.getElementById('tcSheet'), busy = !!(sh && !sh.hidden);   // «Кто вы?» is open: keep it, just switch the tab
  if (k === 'tab' && ['now', 'day', 'tix', 'stats'].includes(v)) go(v);
  else if (k === 'prep' && Object.prototype.hasOwnProperty.call(Prep.TITLES, v)) { go('now'); if (!busy) openPrep(v); }
  else if (k === 'task') {
    FLASH = v; setTimeout(() => { FLASH = null; }, 2500);
    go('tix');
    const el = [...document.querySelectorAll('[data-ref]')].find(x => x.dataset.ref === v);
    if (el) { el.scrollIntoView({ block: 'center' }); el.classList.add('tc-flash'); }
  }
}
