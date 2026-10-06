/* ---------- tab «Итоги»: three rings, budget by day, tiles (walk, transport, spent, sunset) ---------- */
const WALK_KMH = 4.5;
const dayBudget = evs => evs.filter(e => !e.skip && !e.auto).reduce((s, e) => s + (+e.cost || 0), 0);   // per person
const num1 = v => (Math.round(v * 10) / 10).toLocaleString('ru-RU');

function ringsSVG(parts, center) {
  // parts: [{p: 0..1, c: css colour}], outermost first
  const R = [46, 34, 22];
  return `<svg class="tc-rings" viewBox="0 0 104 104" role="img" aria-hidden="true">` + parts.map((x, i) => {
    const r = R[i], L = 2 * Math.PI * r, p = Math.max(0, Math.min(1, x.p || 0));
    return `<circle class="bg" cx="52" cy="52" r="${r}" style="stroke:${x.c}"/>` +
      `<circle class="fg" cx="52" cy="52" r="${r}" style="stroke:${x.c}" stroke-dasharray="${(L * p).toFixed(2)} ${L.toFixed(2)}"
        transform="rotate(-90 52 52)"/>`;
  }).join('') + `<text x="52" y="52" dominant-baseline="central" text-anchor="middle">${center}</text></svg>`;
}

function statsDay(x, root) {
  const day = x.day, evs = x.evs, N = T.days.length;
  const iso = dateOf(day), w = new Date(iso + 'T12:00:00Z').getUTCDay();
  const live = evs.filter(e => !e.skip && !e.auto && !e.bad);
  const counted = live.filter(e => e.cat !== 'routine');
  const doneN = counted.filter(e => e.done).length;
  const budget = dayBudget(evs);
  const dayExp = typeof myExpenses === 'function' ? myExpenses().filter(e => !e.deleted && e.date === dateOf(day)) : [];
  const spent = dayExp.length ? Math.round(dayExp.reduce((t, e) => t + e.jpy, 0)) : S.spent[day.n];      // expenses win over the old hand-entered total
  const tripP = Math.min(1, (x.cday.n - 1 + Core.dayProgress(x.cevs, x.c.min)) / N);
  const budP = budget ? (spent || 0) / budget : 0;

  const budgets = TV().days.map(d => ({ d, v: dayBudget(d === day ? evs : plan(d, null)) }));
  const max = Math.max(1, ...budgets.map(b => b.v));
  const total = budgets.reduce((s, b) => s + b.v, 0);

  const kmPlan = live.reduce((s, e) => s + (+e.km || 0) + (+e.walk || 0) / 60 * WALK_KMH, 0);
  const walked = S.walked[day.n];
  const rides = live.filter(e => e.cat === 'transport' || e.ride > 0);
  const trMin = live.reduce((s, e) => s + (e.cat === 'transport' ? e.ne - e.ns : 0) + (+e.ride || 0), 0);
  const sun = day.sun ? sunTimes(iso, day.sun[0], day.sun[1]) : null;
  const wx = weatherFor(day);

  root.innerHTML = `<div class="tc-page">
    <div class="tc-title tc-stats-title"><h1>Деньги</h1><span>${WD2[w]} ${+iso.slice(8)}</span>${gearHTML()}</div>
    <section class="tc-card tc-ringcard">
      ${ringsSVG([{ p: tripP, c: 'var(--ring1)' }, { p: counted.length ? doneN / counted.length : 0, c: 'var(--ring2)' },
                  { p: budP, c: 'var(--ring3)' }], +iso.slice(8))}
      <div class="tc-legend">
        <div><span class="tc-lg" style="color:var(--ring1)">Поездка</span><b>${x.cday.n}/${N}</b><small>дней</small></div>
        <div><span class="tc-lg" style="color:var(--ring2)">Сегодня</span><b>${doneN}/${counted.length}</b><small>пунктов</small></div>
        <div><span class="tc-lg" style="color:var(--ring3)">Бюджет</span><b>${budget ? Math.round(budP * 100) + '%' : '—'}</b><small>потрачено</small></div>
      </div>
    </section>
    <section class="tc-card" id="tcBudget">
      <div class="tc-row"><span class="tc-lbl">Бюджет на человека, ¥</span><span class="tc-lbl">всего ${both(total)}</span></div>
      <div class="tc-bars" role="img" aria-label="Бюджет по дням, всего ${yen(total)}">${budgets.map(b =>
        `<div class="tc-barcol${b.d.n < x.cday.n ? ' done' : b.d.n === x.cday.n ? ' cur' : ''}${b.d === day ? ' on' : ''}">
          <i style="height:${Math.max(4, Math.round(b.v / max * 100))}%"></i><small>${+dateOf(b.d).slice(8)}</small></div>`).join('')}</div>
    </section>
    <div class="tc-tiles">
      <section class="tc-card tc-tile2" id="tcWalkTile"><span class="tc-lbl">Пешком</span>
        <b class="tc-tv">${num1(kmPlan)} км</b><span class="tc-sub">план${walked != null ? ' · факт ' + num1(walked) : ''}</span>
        <input id="tcWalk" type="number" inputmode="decimal" min="0" step="0.1" placeholder="факт, км" value="${walked ?? ''}" aria-label="Пройдено за день, км"></section>
      <section class="tc-card tc-tile2"><span class="tc-lbl">В транспорте</span>
        <b class="tc-tv">${dur(trMin)}</b><span class="tc-sub">${rides.length} ${rides.length === 1 ? 'поездка' : rides.length < 5 && rides.length ? 'поездки' : 'поездок'}</span></section>
      <section class="tc-card tc-tile2" id="tcSpentTile"><span class="tc-lbl">Потрачено</span>
        <b class="tc-tv">${spent != null ? yen(spent) : '—'}</b><span class="tc-sub">${spent != null && home(spent) ? home(spent) + ' · ' : ''}план ${yen(budget)}</span>
        <input id="tcSpent" type="number" inputmode="numeric" min="0" step="100" placeholder="¥ за день" value="${spent ?? ''}" aria-label="Потрачено за день, иены"></section>
      <section class="tc-card tc-tile2" id="tcSunTile"><span class="tc-lbl">Закат</span>
        <b class="tc-tv">${sun ? hm(sun.set) : '—'}</b><span class="tc-sub">${wx ? `${wx.hi}° / ${wx.lo ?? '—'}°${wx.prob != null ? ' · дождь ' + wx.prob + '%' : ''}` : 'погода появится за 16 дней'}</span></section>
    </div>
  </div>`;
  const keep = (id, box) => {
    const i = root.querySelector(id);
    i.addEventListener('change', () => {
      const v = parseFloat(String(i.value).replace(',', '.'));
      if (i.value === '' || !Number.isFinite(v) || v < 0) delete S[box][day.n]; else S[box][day.n] = v;
      save(); renderShell();
    });
  };
  keep('#tcWalk', 'walked'); keep('#tcSpent', 'spent');
};

/* «Деньги»: the expenses dashboard first, then the day's rings and tiles */
RENDER.stats = (x, root) => {
  statsDay(x, root);
  const title = root.querySelector('.tc-stats-title');
  if (typeof moneyHTML === 'function') { title.insertAdjacentHTML('afterend', moneyHTML()); wireMoney(root); }
  const ring = root.querySelector('.tc-ringcard'); if (ring) ring.insertAdjacentHTML('beforebegin', '<h2 class="tc-sech">День поездки</h2>');
};
