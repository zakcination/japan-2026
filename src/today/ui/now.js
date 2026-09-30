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

/* ---------- the top row: the next sunrise or sunset, like the Weather app widget ---------- */
function sunTileHTML(x) {
  const day = x.cday, now = x.c.min;
  if (!day.sun || !x.csun || !Number.isFinite(x.csun.rise)) return '';
  const next = T.days.find(d => d.n === day.n + 1);
  const tomorrow = sunTimes(Core.addDays(dateOf(day), 1), (next || day).sun[0], (next || day).sun[1]);
  const { rise, set } = x.csun;
  const ev = now < rise ? ['Восход', rise, 'Закат', set] : now < set ? ['Закат', set, 'Восход', tomorrow.rise] : ['Восход', tomorrow.rise, 'Закат', tomorrow.set];
  // the sun's path over the day: a cosine peaking at solar noon; the horizon crosses it at sunrise/sunset
  const W = 132, H = 40, A = 15, mid = 20, noon = (rise + set) / 2;
  const y = t => mid - A * Math.cos(2 * Math.PI * (t - noon) / 1440);   // highest at solar noon
  const hz = y(rise), pts = [];
  for (let t = 0; t <= 1440; t += 30) pts.push(`${(t / 1440 * W).toFixed(1)},${y(t).toFixed(1)}`);
  const tn = ((now % 1440) + 1440) % 1440, sx = tn / 1440 * W, sy = y(tn), up = sy < hz;
  const path = `M${pts.join(' L')}`;
  return `<div class="tc-mini tc-sun" id="tcSun" role="group" aria-label="${ev[0]} в ${hm(ev[1])}, ${ev[2].toLowerCase()} в ${hm(ev[3])}">
    <span class="tc-mini-lbl">${icon(ev[0] === 'Закат' ? 'sunset' : 'sunrise')}${ev[0]}</span>
    <b>${hm(ev[1])}</b>
    <svg class="tc-sun-arc" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
      <defs><clipPath id="tcSkyUp"><rect x="0" y="0" width="${W}" height="${hz.toFixed(1)}"/></clipPath>
        <clipPath id="tcSkyDown"><rect x="0" y="${hz.toFixed(1)}" width="${W}" height="${H}"/></clipPath></defs>
      <path d="${path}" class="dim" clip-path="url(#tcSkyDown)"/><path d="${path}" class="lit" clip-path="url(#tcSkyUp)"/>
      <line x1="0" x2="${W}" y1="${hz.toFixed(1)}" y2="${hz.toFixed(1)}" class="hz"/>
      <circle cx="${sx.toFixed(1)}" cy="${sy.toFixed(1)}" r="4.5" class="${up ? 'sun' : 'sun down'}"/></svg>
    <small>${ev[2]}: ${hm(ev[3])}</small></div>`;
}
function topRowHTML(x) {
  const tiles = [weatherTileHTML(x), sunTileHTML(x)].filter(Boolean);
  return tiles.length ? `<div class="tc-toprow${tiles.length === 1 ? ' one' : ''}">${tiles.join('')}</div>` : '';
}

/* ---------- before the trip, departure day, transit, after: «Сейчас» by phase ---------- */
const dayOne = () => Date.parse(dateOf(T.days[0]) + 'T00:00:00+09:00');
function daysWord(n) { return n % 10 === 1 && n % 100 !== 11 ? 'день' : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'дня' : 'дней'; }
/* the header capsule before the trip: only for sales opening within 48 h */
function preCapsuleHTML() {
  const o = Prep.opening(prepItems(), Date.now()); if (!o) return '';
  const left = Math.max(0, Date.parse(o.opens) - Date.now()), m = Math.floor(left / 60000);
  const when = m >= 1440 ? `${Math.floor(m / 1440)} д ${Math.floor(m % 1440 / 60)} ч` : m >= 60 ? `${Math.floor(m / 60)} ч` : `${m} мин`;
  const name = o.title.replace(/^(Купить|Забронировать): /, '').split(',')[0].slice(0, 18);
  return `<button type="button" class="tc-cap soon tc-cap-pre" id="tcCap" data-cap-prep aria-label="${esc(o.title)}: продажи через ${when}">
    <span class="tc-cap-t tc-cap-name">${esc(name)}</span><span class="tc-cap-t tc-cap-when">· продажи через ${when}</span></button>`;
}
/* floor-based minutes/days/hours left, shared by the title («через …») and the hero countdown
   (#tcCount) so the two numbers never disagree — both read the same floored day count. */
function daysHoursLeft(ms) {
  const m = Math.max(0, Math.floor(ms / 60000));
  return { m, d: Math.floor(m / 1440), h: Math.floor(m % 1440 / 60) };
}
function preTitleHTML(x) {
  if (x.ph.phase === 'post') return `<div class="tc-title"><h1>Япония</h1><span>поездка завершена</span></div>`;
  if (x.ph.phase === 'departure') return `<div class="tc-title"><h1>Япония</h1><span>вылет сегодня</span></div>`;
  const ms = (x.ph.dep || dayOne()) - Date.now(), { d, h } = daysHoursLeft(ms);
  // «pre» ends at midnight of departure day, so under 24 h here always means tomorrow
  const sub = ms > 2 * 864e5 ? `через ${d} ${daysWord(d)}` : ms > 864e5 ? `через ${d} д ${h} ч` : 'завтра';
  return `<div class="tc-title"><h1>Япония</h1><span>${sub}</span></div>`;
}
/* «17 дней», from T-2 «1 д 5 ч», on the last day «5:12» */
function countdownText(ms) {
  const { m, d, h } = daysHoursLeft(ms);
  if (ms > 2 * 864e5) return `${d} ${daysWord(d)}`;
  if (ms > 864e5) return `${d} д ${h} ч`;
  return Core.cd(m);
}
/* the first day, step by step: every outbound leg, the stops (Shanghai ones in Shanghai time), Haneda, the hotel.
   The current step is the latest one that has started (a flight in the air counts); the ones before fold into a row. */
let day1All = false;
const zoneWord = (code, off) => { const o = Flights.offsetAt(code, Date.now(), off);
  return o === 480 ? 'по Шанхаю' : o === 540 ? 'по Токио' : `по времени ${Flights.airport(code)}`; };
function day1Steps() {
  const d1 = TV().days[0], base = dayOne();
  const evs = plan(d1, null).filter(e => !e.bad && !e.skip);
  const chain = myFlights(), end = chain.findIndex(l => Flights.isJapan(l.to));
  const legs = end < 0 || Flights.isJapan(chain[0].frm) ? [] : chain.slice(0, end + 1);
  const steps = legs.map(l => {
    const tt = Flights.times(l), d = atAirport(tt.dep, l.frm, l.frmOff), a = tt.arr ? atAirport(tt.arr, l.to, l.toOff) : null;
    return { leg: true, t: `Рейс ${Flights.pretty(l.no)} · ${Flights.airport(l.frm)} → ${Flights.airport(l.to)}`, brief: `Вылет ${Flights.pretty(l.no)}`,
      short: d.hm, meta: `${d.dm} ${zoneWord(l.frm, l.frmOff)}${a ? ` · прилёт ${a.hm} ${zoneWord(l.to, l.toOff)}` : ''}`, at: tt.dep };
  });
  const mixed = legs.length > 0 || evs.some(e => e.sh);
  evs.forEach(e => steps.push({ t: e.t, brief: e.t.split(/[:,]/)[0], short: hm(Core.localMin(e, e.ns)),
    meta: e.sh ? 'по Шанхаю' : mixed ? 'по Токио' : '', at: base + e.ns * 60000 }));
  return steps.map((s, i) => [s, i]).sort((p, q) => p[0].at - q[0].at || p[1] - q[1]).map(p => p[0]);
}
function day1HTML(expanded) {
  const steps = day1Steps(), now = Date.now();
  if (!steps.length) return '';
  let cur = -1; steps.forEach((s, i) => { if (s.at <= now) cur = i; });
  if (!expanded) {
    const first = steps.find(s => s.leg) || steps[0];
    const key = [first, ...steps.filter(s => !s.leg && /^Шанхай|^Прилёт|Заселение/.test(s.t)).slice(0, 3)];
    return `<button type="button" class="tc-card tc-day1" id="tcDay1"><span class="tc-row"><span class="tc-lbl">Первые сутки</span>${icon('arrow')}</span>
      <span class="tc-sub">${key.map(s => esc(s.short + ' ' + s.brief)).join(' → ')}</span></button>`;
  }
  const fold = cur > 0 && !day1All ? cur : 0;
  const li = (s, i) => `<li class="${i === cur ? 'now' : i < cur ? 'done' : ''}"><b>${esc(s.short)}</b><span>${esc(s.t)}${s.meta ? `<small>${esc(s.meta)}</small>` : ''}</span></li>`;
  return `<section class="tc-card tc-day1" id="tcDay1"><span class="tc-lbl">Первые сутки</span><ol class="tc-steps">${
    fold ? `<li class="done tc-steps-fold"><button type="button" class="tc-link" id="tcDay1More">✓ ${fold} позади</button></li>` : ''}${
    steps.map((s, i) => i < fold ? '' : li(s, i)).join('')}</ol></section>`;
}
const wireDay1 = root => { const m = root.querySelector('#tcDay1More'); if (m) m.addEventListener('click', () => { day1All = true; renderShell(); }); };
function renderPre(x, root) {
  const now = Date.now(), list = prepItems(), dep = x.ph.dep, dep0 = dep || dayOne();
  const f = Prep.first(list, now, dep0), g = Prep.groups(list);
  const leg = x.ph.leg, t0 = dep && leg ? atAirport(dep, leg.frm, leg.frmOff) : null;
  const chain = myFlights();
  const out = leg ? chain.slice(0, chain.findIndex(l => Flights.isJapan(l.to)) + 1) : [];
  const route = out.length ? [out[0].frm, ...out.map(l => l.to)].map(c => esc(Flights.airport(c))).join(' → ') : '';
  const opening = list.filter(i => !i.done && i.opens && Date.parse(i.opens) > now).sort((a, b) => Date.parse(a.opens) - Date.parse(b.opens))[0];
  const cities = T.days.map(d => String(d.city || '').split(' →')[0].trim()).filter((c, i, a) => c && c !== a[i - 1]);
  const url = f.item ? Core.safeUrl(f.item.url) : '';
  const word = n => n % 10 === 1 && n % 100 !== 11 ? 'дело' : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'дела' : 'дел';
  let html = `<section class="tc-card tc-count" id="tcCount"><div class="tc-row"><span class="tc-lbl">До вылета</span>${leg ? `<span class="tc-fl-no">${esc(Flights.pretty(leg.no))}</span>` : ''}</div>
    <b class="tc-count-n">${esc(countdownText(dep0 - now))}</b>
    ${route ? `<span class="tc-fl-route">${route}</span>` : ''}
    ${t0 ? `<span class="tc-sub">Вылет ${t0.dm} в ${t0.hm} по времени ${esc(Flights.airport(leg.frm))} · <a class="tc-inl" href="${Flights.statusUrl(leg.no)}" target="_blank" rel="noopener">статус рейса</a></span>`
      : `<span class="tc-sub">до первого дня поездки, ${Core.ddmmyyyy(dateOf(T.days[0])).slice(0, 5)}</span>`}</section>`;
  html += f.item ? `<section class="tc-card tc-first" id="tcFirst"><span class="tc-lbl">Сначала это</span><b>${esc(f.item.title)}</b>
      ${f.item.due ? `<span class="tc-sub${f.item.due.slice(0, 10) < japanNow().date ? ' tc-late' : ''}">${f.item.due.slice(0, 10) < japanNow().date ? 'срок был' : 'до'} ${Core.ddmmyyyy(f.item.due.slice(0, 10)).slice(0, 5)}</span>` : ''}
      <div class="tc-actions two">${url ? `<a class="tc-btn primary" href="${url}" target="_blank" rel="noopener">${icon('share')}Открыть сайт</a>` : ''}${f.item.auto
        ? '' : `<button type="button" class="tc-btn${url ? '' : ' primary'}" data-first-done="${esc(f.item.id)}">${icon('check')}Готово</button>`}</div>
      <div class="tc-first-foot">${f.rest ? `<button type="button" class="tc-link" data-ready="all">ещё ${f.rest} ${word(f.rest)} ›</button>` : '<span></span>'}
        ${f.item.due || f.item.opens ? nudgeHTML(`${f.item.title} — ${f.item.due ? 'до ' + Core.ddmmyyyy(f.item.due.slice(0, 10)).slice(0, 5) : 'продажи ' + Core.ddmmyyyy(f.item.opens.slice(0, 10)).slice(0, 5)}`, deepLink('prep=' + f.item.group), true) : ''}</div></section>`
    : `<section class="tc-card tc-first" id="tcFirst"><span class="tc-lbl">Сначала это</span>
      <b>${list.every(i => i.done) ? 'Всё готово ✓' : 'Сейчас делать нечего'}</b>
      ${opening ? `<span class="tc-sub">${esc(opening.title)} — продажи откроются ${Core.ddmmyyyy(opening.opens.slice(0, 10)).slice(0, 5)}</span>` : ''}</section>`;
  html += `<section class="tc-ready" id="tcReady" aria-label="Готовность">${g.map(r => `<button type="button" class="tc-ready-chip" data-ready="${r.key}"
      aria-label="${esc(r.title)}: ${r.done} из ${r.total}"><svg viewBox="0 0 36 36" class="tc-ready-ring" aria-hidden="true"><circle cx="18" cy="18" r="15" class="bg"/>${r.done ? `<circle cx="18" cy="18" r="15" class="fg"
        stroke-dasharray="${(94.25 * r.done / r.total).toFixed(1)} 94.25" transform="rotate(-90 18 18)"/>` : ''}</svg>
      <span><b>${esc(r.title)}</b><small>${r.done}/${r.total}</small></span></button>`).join('')}</section>`;
  html += Ios.installHint();                   // below readiness: the phone group already lists «на экран „Домой“»
  html += day1HTML(dep0 - now <= 864e5);
  if (cities.length) html += `<button type="button" class="tc-flline" id="tcRoute">${icon('day')}<span>${esc(cities.join(' · '))}<small>маршрут по дням</small></span>${icon('arrow')}</button>`;
  if (dep0 - now <= 7 * 864e5) html += topRowHTML(x);               // weather and sun only from T-7
  if (!chain.length) html += flightTileHTML(x);
  root.innerHTML = `<div class="tc-page">${html}</div>`;
  Ios.wireInstall(root); wireFlightCard(root); wireDay1(root);
  root.querySelectorAll('[data-ready]').forEach(b => b.addEventListener('click', () => openPrep(b.dataset.ready === 'all' ? null : b.dataset.ready)));
  const fd = root.querySelector('[data-first-done]');
  if (fd) fd.addEventListener('click', () => { const l = prepLocal(); l.done[fd.dataset.firstDone] = true; prepSave(l); renderShell(); });
  const toDay1 = () => { viewDay = T.days[0].n; go('day'); };
  const rt = root.querySelector('#tcRoute'); if (rt) rt.addEventListener('click', toDay1);
  const d1 = root.querySelector('button#tcDay1'); if (d1) d1.addEventListener('click', toDay1);
}
function renderPost(x, root) {
  const n = T.days.length;
  root.innerHTML = `<div class="tc-page"><section class="tc-card" id="tcNow"><span class="tc-lbl">Япония</span><h2 class="tc-h2">Поездка завершена</h2>
    <span class="tc-sub">${n} ${daysWord(n)} в Японии</span>
    <button type="button" class="tc-btn primary" id="tcToStats">${icon('stats')}Итоги поездки</button></section></div>`;
  root.querySelector('#tcToStats').addEventListener('click', () => go('stats'));
}
function renderDeparture(x, root) {
  const dep = x.ph.dep, list = prepItems().filter(i => !i.done && (!i.due || Date.parse(i.due.length === 10 ? i.due + 'T23:59:59+09:00' : i.due) <= dep + 864e5)
    && (!i.opens || Date.parse(i.opens) <= Date.now()) && i.group !== 'tickets');
  root.innerHTML = `<div class="tc-page">${flightCardHTML(x)}${list.length ? `<section class="tc-card" id="tcLeft"><span class="tc-lbl">Ещё сделать до вылета</span>
    ${list.slice(0, 5).map(i => `<span class="tc-sub">• ${esc(i.title)}</span>`).join('')}
    <button type="button" class="tc-link" data-ready="${esc(list[0].group)}">все дела ›</button></section>` : ''}${day1HTML(false)}</div>`;
  wireFlightCard(root);
  root.querySelectorAll('[data-ready]').forEach(b => b.addEventListener('click', () => openPrep(b.dataset.ready)));
  const d1 = root.querySelector('button#tcDay1'); if (d1) d1.addEventListener('click', () => { viewDay = T.days[0].n; go('day'); });
}
function renderTransit(x, root) {
  // the countdown only while an outbound leg is still to fly — never the way home from mid-air
  const n = Flights.next(myFlights(), Date.now()), card = n && x.ph.arrive && n.dep < x.ph.arrive ? flightCardHTML(x) : '';
  root.innerHTML = `<div class="tc-page">${day1HTML(true)}${card}</div>`;
  wireFlightCard(root); wireDay1(root);
}

RENDER.now = (x, root) => {
  if (x.ph.phase === 'pre') return renderPre(x, root);
  if (x.ph.phase === 'post') return renderPost(x, root);
  if (x.ph.phase === 'departure') return renderDeparture(x, root);
  if (x.ph.phase === 'transit') return renderTransit(x, root);
  const now = x.c.min, evs = liveEvs(x.cevs);
  const cur = evs.find(e => e.ns <= now && now < e.ne) || null;
  const next = evs.find(e => e.ns > now && Core.isKey(e)) || evs.find(e => e.ns > now) || null;
  const u = x.urg;
  const dark = document.getElementById('today').dataset.th === 'dark';
  let html = Ios.installHint() + topRowHTML(x) + flightCardHTML(x);
  const asked = Trips.asked();
  if (asked) html += `<section class="tc-card tc-note" id="tcAsked"><span class="tc-lbl">Ссылка на другую поездку</span>
    <span class="tc-sub">Ссылка ведёт на «${esc(Trips.nameOf(asked))}», а на телефоне ваша версия с правками.</span>
    <button type="button" class="tc-btn primary" id="tcAskedGo">Открыть «${esc(Trips.nameOf(asked))}»</button></section>`;
  if (dark) html += `<div class="tc-bignow"><span>${hm(now)}</span>${u ? `<em>${u.state === 'go' ? 'пора выходить' : 'выйти через ' + dur(u.leaveIn)}</em>` : ''}</div>`;
  if (!x.cevs.length) {
    html += `<section class="tc-card" id="tcNow"><span class="tc-lbl">Сегодня</span><h2 class="tc-h2">Нет пунктов</h2>
      <span class="tc-sub">Добавьте пункт во вкладке «День».</span></section>`;
  } else if (!cur && !next) {
    const tomorrow = TV().days.find(d => d.n === x.cday.n + 1);
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
  html += flightTileHTML(x);                   // below now / next: a low-priority prompt
  if (x.pv && !x.c.live) {
    const d0 = dateOf(T.days[0]), days = Math.round((Date.parse(d0) - Date.parse(japanNow().date)) / 864e5);
    html += `<p class="tc-preview">${days > 0 ? `Предпросмотр · поездка через ${days} дн.` : 'Предпросмотр'} ·
      <label>день <select id="tcPvDay">${T.days.map(d => `<option value="${d.n}"${d.n === x.cday.n ? ' selected' : ''}>${Core.ddmmyyyy(dateOf(d)).slice(0, 5)}</option>`).join('')}</select></label>
      <label>время <input id="tcPvTime" type="time" value="${hm(now)}"></label></p>
      <button type="button" class="tc-btn" id="tcPvExit">Выйти из предпросмотра</button>`;
  }
  root.innerHTML = `<div class="tc-page">${html}</div>`;
  Ios.wireInstall(root);
  wireFlightCard(root);
  const ag = root.querySelector('#tcAskedGo');
  if (ag) ag.addEventListener('click', () => twoTap(ag, 'Точно? Ваши правки удалятся', () => {
    Trips.backToShared().then(ok => {
      if (!ok) { ag.textContent = 'Нет сети — попробуйте позже'; return; }
      setTitle(); viewDay = null; renderShell();
    });
  }));
  root.querySelectorAll('[data-ticket]').forEach(b => b.addEventListener('click', () => showTicket(b.dataset.ticket)));
  const pd = root.querySelector('#tcPvDay'), pt = root.querySelector('#tcPvTime');
  if (pd) pd.addEventListener('change', () => { S.prevDay = +pd.value; viewDay = S.prevDay; save(); renderShell(); });
  if (pt) pt.addEventListener('change', () => { if (pt.value) { S.prevTime = pt.value; save(); renderShell(); } });
  const px = root.querySelector('#tcPvExit');
  if (px) px.addEventListener('click', () => { S.preview = false; viewDay = null; save(); renderShell(); });
};
