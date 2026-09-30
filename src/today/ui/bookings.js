/* ---------- tab «Брони»: today's bookings, the whole trip, ticket files, the full-screen ticket ---------- */

/* keep the screen on while a ticket or the leave alert is shown (Safari 16.4+); silently absent elsewhere */
/* One wanted state, one request in flight: quick on/off/on never leaks a lock, and a lock Safari
   dropped (phone locked, tab hidden) is taken again when the page is visible. */
const Wake = {
  want: false, lock: null, busy: null, failed: false,
  on() { if (!this.want) this.failed = false; this.want = true; return this.sync(); },
  off() { this.want = false; return this.sync(); },
  sync() {
    if (this.busy) return this.busy;
    if (this.want && !this.lock && !this.failed && navigator.wakeLock && !document.hidden) {
      this.busy = navigator.wakeLock.request('screen').then(l => {
        this.lock = l;
        if (l.addEventListener) l.addEventListener('release', () => { if (this.lock === l) this.lock = null; });
      }, () => { this.failed = true; }).then(() => { this.busy = null; return this.sync(); });
      return this.busy;
    }
    if (!this.want && this.lock) { const l = this.lock; this.lock = null; Promise.resolve(l.release()).catch(() => {}); }
    return Promise.resolve(!!this.lock);
  },
};
document.addEventListener('visibilitychange', () => {
  if (document.hidden) return;
  if (Wake.lock && Wake.lock.released) Wake.lock = null;
  Wake.failed = false; Wake.sync();
});

const bkDay = b => T.days.find(d => d.n === (b.days || [])[0]);

function bkRow(b, withDate) {
  const d = bkDay(b), fixed = b.st === 'fixed';
  const when = [withDate && d ? Core.ddmmyyyy(dateOf(d)).slice(0, 5) : '', esc(b.when || ''), b.cost ? money(b.cost) : '']
    .filter(Boolean).join(' · ');
  const right = haveTicket[b.id]
    ? `<button type="button" class="tc-qr" data-ticket="${esc(b.id)}" aria-label="Показать билет: ${esc(b.t)}">QR</button>`
    : `<label class="tc-file">${icon('clip')}Файл<input type="file" accept="image/*,application/pdf" data-attach="${esc(b.id)}"
        aria-label="Прикрепить билет: ${esc(b.t)}" hidden></label>`;
  const links = typeof attachLinksFor === 'function' ? attachLinksFor(b.id) : [];
  const linkBtns = links.map(l => Core.safeUrl(l.url) ? `<a class="tc-qr" href="${Core.safeUrl(l.url)}" target="_blank" rel="noopener">${esc(l.site || 'Бронь')}</a>` : '').join('');
  return `<div class="tc-bk"><div class="tc-bkbody"><span class="tc-bkt">${esc(b.t)}</span>
      ${when ? `<span class="tc-sub">${when}</span>` : ''}
      <button type="button" class="tc-bkst" data-bkst="${esc(b.id)}" aria-pressed="${fixed}"
        aria-label="${fixed ? 'Куплено — отменить отметку' : 'Отметить как купленное'}">${stDot(fixed ? 'fixed' : 'input')}</button></div>
    <div class="tc-bkr">${right}${linkBtns}<button type="button" class="tc-file" data-link="${esc(b.id)}" aria-label="Ссылка на бронь: ${esc(b.t)}">${icon('share')}Ссылка</button></div></div>`;
}

RENDER.tix = (x, root) => {
  const today = planDoc().bookings.filter(b => (b.days || []).includes(x.day.n));
  const rest = planDoc().bookings.filter(b => !(b.days || []).includes(x.day.n))
    .sort((a, b) => ((a.days || [])[0] || 0) - ((b.days || [])[0] || 0));
  const bought = today.filter(b => b.st === 'fixed').length;
  root.innerHTML = `<div class="tc-page">${typeof tasksHTML === 'function' ? tasksHTML(Date.now()) : ''}
    <section id="tcBkToday"><h2 class="tc-sech">${x.day === x.cday ? 'Сегодня' : Core.ddmmyyyy(dateOf(x.day)).slice(0, 5)} · ${bought} из ${today.length} куплено</h2>
      <div class="tc-group">${today.length ? today.map(b => bkRow(b, false)).join('') : '<p class="tc-empty">На этот день броней нет.</p>'}</div></section>
    ${rest.length ? `<section id="tcBkAll"><h2 class="tc-sech">Вся поездка</h2><div class="tc-group">${rest.map(b => bkRow(b, true)).join('')}</div></section>` : ''}
    <p class="tc-foot">Скриншот QR или PDF хранится только в этом браузере на этом телефоне и открывается без интернета.</p>
  </div>`;
  if (typeof wireAttach === 'function') wireAttach(root);
  if (typeof wireTasks === 'function') wireTasks(root);
  root.querySelectorAll('[data-bkst]').forEach(b => b.addEventListener('click', () => {
    const bk = bookingById(b.dataset.bkst); if (!bk) return;
    bk.st = bk.st === 'fixed' ? 'input' : 'fixed'; saveTrip(); renderShell();
  }));
  root.querySelectorAll('[data-ticket]').forEach(b => b.addEventListener('click', () => showTicket(b.dataset.ticket)));
  root.querySelectorAll('[data-attach]').forEach(inp => inp.addEventListener('change', () => attach(inp.dataset.attach, inp)));
};

function attach(id, inp) {
  const f = inp.files && inp.files[0]; if (!f) return Promise.resolve();
  return ticketPut(id, f).then(refreshTickets).then(renderShell)
    .catch(() => { const r = document.getElementById('todayBody'); r.insertAdjacentHTML('afterbegin', '<p class="tc-warn">Не удалось сохранить файл в этом браузере.</p>'); });
}

/* the full-screen ticket: black, the QR on white, the screen kept on */
let ticketURL = null;
function showTicket(id) {
  // a group attachment (att:<id>) shows the title of the booking it belongs to
  const att = String(id).startsWith('att:') && typeof Api !== 'undefined' && Api.state()
    ? (Api.state().attachments || []).find(x => 'att:' + x.id === id) : null;
  const b = bookingById(att ? String(att.ref).slice(3) : id);
  let m = document.getElementById('tcTicket');
  if (!m) {
    m = document.createElement('div'); m.id = 'tcTicket'; m.className = 'tc-ticket';
    m.setAttribute('role', 'dialog'); m.setAttribute('aria-modal', 'true'); m.setAttribute('aria-label', 'Билет');
    document.body.appendChild(m);
  }
  if (ticketURL) { URL.revokeObjectURL(ticketURL); ticketURL = null; }
  m.innerHTML = `<div class="tc-tk-top"><button type="button" class="tc-tk-btn" id="tcTicketDone">Готово</button>
      <span class="tc-tk-awake" id="tcTicketAwake" hidden>${icon('bulb')}Экран не погаснет</span></div>
    <h2>${esc(b ? b.t : 'Билет')}</h2>${b && b.when ? `<p class="tc-tk-sub">${esc(b.when)}</p>` : ''}
    <div class="tc-tk-hold" id="tcTicketHold"></div>
    <p class="tc-tk-sub" id="tcTicketHint"></p>
    <div class="tc-tk-actions">
      <button type="button" class="tc-tk-btn light" id="tcTicketShare" hidden>${icon('share')}Поделиться</button>
      <label class="tc-tk-btn">${icon('clip')}Заменить<input type="file" accept="image/*,application/pdf" id="tcTicketFile" hidden></label>
      <button type="button" class="tc-tk-btn" id="tcTicketDel" hidden>Удалить</button>
    </div>`;
  m.hidden = false;
  const hold = m.querySelector('#tcTicketHold'), hint = m.querySelector('#tcTicketHint');
  m.querySelector('#tcTicketDone').addEventListener('click', closeTicket);
  m.querySelector('#tcTicketFile').addEventListener('change', e => attach(id, e.target).then(() => showTicket(id)));
  m.querySelector('#tcTicketDone').focus();
  Wake.on().then(ok => { const a = m.querySelector('#tcTicketAwake'); if (a && !m.hidden) a.hidden = !ok; });
  ticketGet(id).then(rec => {
    if (!rec) { hint.textContent = 'Билет ещё не прикреплён — нажмите «Заменить» и выберите скриншот QR.'; return; }
    ticketURL = URL.createObjectURL(rec.blob);
    if ((rec.type || '').startsWith('image/')) {
      const i = new Image(); i.src = ticketURL; i.alt = 'Билет: ' + (b ? b.t : ''); hold.appendChild(i);
      hint.textContent = 'Прибавьте яркость — так контролёр отсканирует быстрее.';
    } else if (rec.type === 'application/pdf') {
      URL.revokeObjectURL(ticketURL);
      ticketURL = URL.createObjectURL(new Blob([rec.blob], { type: 'application/pdf' }));
      const f = document.createElement('iframe'); f.src = ticketURL; f.title = 'Билет'; f.setAttribute('sandbox', ''); hold.appendChild(f);
      hint.textContent = 'Если PDF не показался — прикрепите вместо него скриншот QR.';
    } else {
      hint.textContent = 'Этот файл не картинка и не PDF — прикрепите скриншот QR.';
    }
    const file = new File([rec.blob], rec.name || 'ticket', { type: rec.type || '' });
    const sh = m.querySelector('#tcTicketShare');
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      sh.hidden = false;
      sh.addEventListener('click', () => navigator.share({ files: [file], title: b ? b.t : 'Билет' }).catch(() => {}));
    }
    const del = m.querySelector('#tcTicketDel');
    del.hidden = false;
    del.addEventListener('click', () => {
      if (!del.dataset.confirm) {
        del.dataset.confirm = '1'; del.textContent = 'Удалить?';
        setTimeout(() => { if (del.isConnected) { delete del.dataset.confirm; del.textContent = 'Удалить'; } }, 4000);
        return;
      }
      ticketDel(id).then(refreshTickets).then(() => { closeTicket(); renderShell(); });
    });
  }).catch(() => { hint.textContent = 'Хранилище билетов недоступно в этом окне.'; });
}
function closeTicket() {
  const m = document.getElementById('tcTicket'); if (!m) return;
  m.hidden = true; m.innerHTML = '';
  if (ticketURL) { URL.revokeObjectURL(ticketURL); ticketURL = null; }
  Wake.off();
}
