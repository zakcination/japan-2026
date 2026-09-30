/* ---------- «Кто вы?» + PIN; the group part of ⚙ ---------- */
const LOGIN_ASKED = 'japan2026.loginasked.v1';
const PIN_ERR = { 'wrong PIN': 'Неверный PIN', 'locked, try later': 'Слишком много попыток — подождите 15 минут', 'Нет сети': 'Нет сети — попробуйте позже',
  'invite needed': 'Для первого входа нужна ваша ссылка-приглашение от хозяев', 'ask a host': 'Этот телефон уже вошёл как другой участник — спросите хозяев',
  'PIN is set by the owner': 'PIN хозяина задаётся при настройке', 'PIN must be 4 digits': 'PIN — 4 цифры' };
/* the invite link: ?who=<member id>&code=<one-time code> opens straight on that person's PIN */
const INVITE = (() => { const q = new URLSearchParams(location.search); const who = q.get('who'), code = q.get('code');
  return /^[0-9a-f-]{36}$/.test(who || '') ? { who, code: /^[0-9a-f]{6,32}$/.test(code || '') ? code : null } : null; })();

async function openLogin() {
  try { localStorage.setItem(LOGIN_ASKED, '1'); } catch (e) {}
  sheet('Кто вы?', `<p class="tc-sub">Выберите себя — дальше PIN из 4 цифр. В первый раз вы его придумываете.</p>
    <div class="tc-group" id="grNames"><p class="tc-empty">Загружаю…</p></div>
    <button type="button" class="tc-btn wide" id="grJustLook">Просто посмотреть</button>`, async m => {
    m.querySelector('#grJustLook').addEventListener('click', closeSheet);
    let names = [];
    try { names = await Api.memberNames(); } catch (e) { names = ((Api.state() || {}).members || []); }
    const box = m.querySelector('#grNames');
    if (!box || !box.isConnected) return;                                // another sheet took its place meanwhile
    if (!names.length) { box.innerHTML = '<p class="tc-empty">Нет сети — войдите позже.</p>'; return; }
    const invited = INVITE && names.find(n => n.id === INVITE.who);
    if (invited) { openPin(invited.id, invited.name); return; }            // came by a personal invite link
    box.innerHTML = names.map(n => `<button type="button" class="tc-act" data-member="${esc(n.id)}">${icon('now')}<span>${esc(n.name)}</span></button>`).join('');
    box.querySelectorAll('[data-member]').forEach(b => b.addEventListener('click', () => openPin(b.dataset.member, b.textContent.trim())));
  });
}
function openPin(id, name) {
  sheet(name, `<label class="tc-f" for="grPin"><span>PIN — 4 цифры</span>
      <input id="grPin" type="password" inputmode="numeric" pattern="\\d*" maxlength="4" autocomplete="one-time-code" autofocus></label>
    <p class="tc-warn" id="grMsg" role="status"></p>`, m => {
    const pin = m.querySelector('#grPin'), msg = m.querySelector('#grMsg');
    pin.addEventListener('input', async () => {
      if (pin.disabled) return;                                   // one attempt at a time (paste / autofill fire twice)
      pin.value = pin.value.replace(/\D/g, '').slice(0, 4);
      if (pin.value.length < 4) return;
      pin.disabled = true;
      const r = await Api.login(id, pin.value, INVITE && INVITE.who === id ? INVITE.code : null);
      pin.disabled = false;
      if (r.ok) { track('login'); if (Ios.standalone()) track('installed'); if (onboarded()) { closeSheet(); renderShell(); } else openFirstRun(); return; }
      msg.textContent = PIN_ERR[r.error] || 'Не получилось войти — попробуйте ещё раз'; pin.value = ''; pin.focus();
    });
    pin.focus();
  });
}
function groupSettingsHTML() {
  if (!Api.enabled()) return '';
  const me = Api.me(), st = Api.status();
  if (!me) return `<div class="tc-group"><button type="button" class="tc-act" id="grLogin">${icon('now')}<span>Войти в группу<small>выбрать себя и PIN</small></span></button></div>`;
  const s = Api.state() || { members: [] };
  const sync = st.pending ? `ждёт отправки: ${st.pending}` : st.at ? `синхронизировано ${new Date(st.at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}` : 'ещё не синхронизировано';
  return `<div class="tc-card"><b>Вы вошли как ${esc(me.name)}</b><span class="tc-sub">${esc(sync)}${st.online ? '' : ' · нет сети'}${st.error && st.error !== 'login' ? ' · ' + esc(st.error) : ''}</span>
      ${st.error === 'login' ? '<button type="button" class="tc-btn primary" id="grRelogin">Войти снова</button>' : ''}
      <button type="button" class="tc-btn" id="grLogout">Выйти</button></div>
    ${me.role === 'host' ? `<span class="tc-sech">Участники</span><div class="tc-group">${s.members.map(x =>
      `<div class="tc-flrow"><span><b>${esc(x.name)}</b><small>${x.role === 'host' ? 'хозяин' : 'гость'}</small></span>
        ${x.role === 'guest' ? `<span class="tc-actions two"><button type="button" class="tc-btn primary" data-invite="${esc(x.id)}">Пригласить</button>
          <button type="button" class="tc-btn" data-reset="${esc(x.id)}">Сбросить PIN</button></span>`
          : x.id !== me.id ? `<button type="button" class="tc-btn" data-reset="${esc(x.id)}">Сбросить PIN</button>` : ''}</div>`).join('')}</div>
      ${funnelHTML()}
      <div class="tc-form2">${fld('grNewName', 'Новый участник', '', 'text', 'maxlength="40"')}<button type="button" class="tc-btn primary" id="grAdd">${icon('plus')}Добавить</button></div>
      <p class="tc-foot">Если приложение долго не открывали, бесплатный Supabase «засыпает»: зайдите на supabase.com → проект → Restore.</p>` : ''}`;
}
function wireGroupSettings(m) {
  const on = (id, f) => { const b = m.querySelector(id); if (b) b.addEventListener('click', f); };
  on('#grLogin', () => { closeSheet(); openLogin(); });
  on('#grRelogin', () => { const me = Api.me(); Api.reauth(); closeSheet(); openPin(me.id, me.name); });
  on('#grLogout', () => twoTap(m.querySelector('#grLogout'), 'Точно выйти?', () => { Api.logout(); closeSheet(); renderShell(); }));
  on('#grAdd', () => {
    const name = m.querySelector('#grNewName').value.trim(); if (!name) return;
    Api.run('add_member', { p_name: name, p_role: 'guest' }).then(r => showInvite(name, r && r.id, r && r.code))
      .catch(e => { m.querySelector('#grNewName').value = name; alert0(m, e); });
  });
  m.querySelectorAll('[data-invite]').forEach(b => b.addEventListener('click', () => openInvite(b.dataset.invite)));
  wireFunnel(m);
  m.querySelectorAll('[data-reset]').forEach(b => b.addEventListener('click', () => twoTap(b, 'Точно?', () => {
    const who = (Api.state().members.find(x => x.id === b.dataset.reset) || {}).name || '';
    Api.run('reset_pin', { p_member: b.dataset.reset }).then(r => showInvite(who, b.dataset.reset, r && r.code)).catch(e => alert0(m, e));
  })));
}

const alert0 = (m, e) => { const p = m.querySelector('#setMsg'); if (p) p.textContent = e && !e.status ? 'Нет сети — попробуйте позже' : 'Не получилось — попробуйте ещё раз'; };
