/* ---------- tab «Сейчас»: one screen — what's on, what's next, when to leave ---------- */
const liveEvs = evs => evs.filter(e => !e.skip && !e.auto && !e.bad);
const routeUrl = e => Ios.routeUrl(e);
const stDot = st => {
  const m = { fixed: ['fixed', 'Куплено'], planned: ['planned', 'По плану'], flex: ['flex', 'Гибко'], input: ['input', 'Купить'] };
  const [k, l] = m[st] || m.planned;
  return `<span class="tc-st ${k}"><i aria-hidden="true"></i>${l}</span>`;
};
const subOf = e => [e.frm && e.to ? `${esc(e.frm)} → ${esc(e.to)}` : '', esc(e.mode || '')].filter(Boolean).join(' · ');

function nowCard(x, cur, next) {
  const now = x.c.min;
  if (cur) {
    const p = Math.max(0, Math.min(100, Math.round((now - cur.ns) / Math.max(1, cur.ne - cur.ns) * 100)));
    return `<section class="tc-card" id="tcNow"><span class="tc-lbl">Сейчас</span>
      <h2 class="tc-h2">${esc(cur.t)}</h2>
      <div class="tc-bar" role="progressbar" aria-valuenow="${p}" aria-valuemin="0" aria-valuemax="100"><i style="width:${p}%"></i></div>
      <span class="tc-sub">ещё ${dur(cur.ne - now)} · до ${hm(cur.ne)}</span></section>`;
  }
  if (next && next.leave - now > 0) {
    return `<section class="tc-card" id="tcNow"><span class="tc-lbl">Сейчас</span>
      <h2 class="tc-h2">Свободное время</h2><span class="tc-sub">до выхода ${dur(next.leave - now)}</span></section>`;
  }
  return '';
}

function nextCard(x, next, u) {
  const now = x.c.min;
  const go = u && u.ev === next && u.state === 'go';
  const ticketBtn = next.bk ? `<button type="button" class="tc-btn" data-ticket="${esc(next.bk)}">Билет</button>` : '';
  if (go) {
    return `<section class="tc-card tc-alert" id="tcNext">
      <h2 class="tc-alert-h">Пора выходить</h2>
      <p class="tc-alert-p">Выход был в ${hm(next.leave)}. До начала ${dur(next.ns - now)}.</p>
      <div class="tc-when"><span class="tc-big">${hm(next.ns)}</span><span class="tc-what">${esc(next.t)}</span></div>
      <a class="tc-btn primary wide" href="${routeUrl(next)}" target="_blank" rel="noopener">${icon('arrow')}Начать маршрут</a>
      ${next.bk ? `<button type="button" class="tc-btn wide soft" data-ticket="${esc(next.bk)}">Показать билет</button>` : ''}
    </section>`;
  }
  const leaveIn = next.leave - now;
  const hasTravel = Core.travel(next) > 0;
  return `<section class="tc-card" id="tcNext">
    <div class="tc-row"><span class="tc-lbl">Дальше</span>${stDot(next.st)}</div>
    <div class="tc-when"><span class="tc-big">${hm(next.ns)}</span>
      <span class="tc-whatbox"><span class="tc-what">${esc(next.t)}</span>${subOf(next) ? `<span class="tc-sub">${subOf(next)}</span>` : ''}</span></div>
    ${hasTravel ? `<div class="tc-inset"><div><span class="tc-lbl">Выйти через</span><span class="tc-count">${Core.cd(leaveIn)}</span></div>
      <span class="tc-sub right">в ${hm(next.leave)}${next.ride ? `<br>дорога ${next.ride} мин` : ''}${next.walk ? `<br>пешком ${next.walk}` : ''}${next.buf ? ` · запас ${next.buf}` : ''}</span></div>` : ''}
    ${next.conflict ? `<p class="tc-warn">Не успеваете на ${dur(next.conflict)} — пропустите гибкий пункт.</p>` : ''}
    <div class="tc-actions">
      <a class="tc-btn primary" href="${routeUrl(next)}" target="_blank" rel="noopener">${icon('arrow')}Маршрут</a>
      ${ticketBtn}<a class="tc-btn" href="${gmap(next)}" target="_blank" rel="noopener">Карта</a>
    </div>
  </section>`;
}

RENDER.now = (x, root) => {
  const now = x.c.min, evs = liveEvs(x.cevs);
  const cur = evs.find(e => e.ns <= now && now < e.ne) || null;
  const next = evs.find(e => e.ns > now && Core.isKey(e)) || evs.find(e => e.ns > now) || null;
  const u = x.urg;
  const dark = document.getElementById('today').dataset.th === 'dark';
  let html = Ios.installHint();
  if (dark) html += `<div class="tc-bignow"><span>${hm(now)}</span>${u ? `<em>${u.state === 'go' ? 'пора выходить' : 'выйти через ' + dur(u.leaveIn)}</em>` : ''}</div>`;
  if (!x.cevs.length) {
    html += `<section class="tc-card" id="tcNow"><span class="tc-lbl">Сегодня</span><h2 class="tc-h2">Нет пунктов</h2>
      <span class="tc-sub">Добавьте пункт во вкладке «День».</span></section>`;
  } else if (!cur && !next) {
    const tomorrow = T.days.find(d => d.n === x.cday.n + 1);
    const first = tomorrow ? liveEvs(plan(tomorrow, null)).find(Core.isKey) : null;
    html += `<section class="tc-card" id="tcNow"><span class="tc-lbl">Сегодня</span><h2 class="tc-h2">День завершён</h2>
      <span class="tc-sub">${first ? `Завтра: ${hm(first.ns)} · ${esc(first.t)}` : 'Поездка завершена'}</span></section>`;
  } else {
    html += nowCard(x, cur, next);
    if (next) html += nextCard(x, next, u);
    const cut = x.cevs.filter(e => e.cut || e.auto);
    if (cut.length) html += `<section class="tc-card tc-note"><span class="tc-lbl">План пересчитан</span>
      <span class="tc-sub">${cut.map(e => e.auto ? `убрано: ${esc(e.t)}` : `${esc(e.t)} −${e.cut} мин`).join(' · ')}</span></section>`;
  }
  if (!x.c.live) {
    const d0 = dateOf(T.days[0]), days = Math.round((Date.parse(d0) - Date.parse(japanNow().date)) / 864e5);
    html += `<p class="tc-preview">${days > 0 ? `Предпросмотр · поездка через ${days} дн.` : 'Предпросмотр'} ·
      <label>день <select id="tcPvDay">${T.days.map(d => `<option value="${d.n}"${d.n === x.cday.n ? ' selected' : ''}>${Core.ddmmyyyy(dateOf(d)).slice(0, 5)}</option>`).join('')}</select></label>
      <label>время <input id="tcPvTime" type="time" value="${hm(now)}"></label></p>`;
  }
  root.innerHTML = `<div class="tc-page">${html}</div>`;
  Ios.wireInstall(root);
  root.querySelectorAll('[data-ticket]').forEach(b => b.addEventListener('click', () => showTicket(b.dataset.ticket)));
  const pd = root.querySelector('#tcPvDay'), pt = root.querySelector('#tcPvTime');
  if (pd) pd.addEventListener('change', () => { S.prevDay = +pd.value; viewDay = S.prevDay; save(); renderShell(); });
  if (pt) pt.addEventListener('change', () => { if (pt.value) { S.prevTime = pt.value; save(); renderShell(); } });
};
