/* ---------- iPhone extras: Calendar with «пора выходить» alarms, Apple Maps, screen kept on, install hint ----------
   The top part is pure (tested in a blank page); the rest runs in the app and uses the store and the shell. */
const Ios = (() => {
  const isIOS = (ua = navigator.userAgent, platform = navigator.platform, touch = navigator.maxTouchPoints) =>
    /iP(hone|ad|od)/.test(ua) || (platform === 'MacIntel' && touch > 1);
  const standalone = () => navigator.standalone === true ||
    (typeof matchMedia === 'function' && matchMedia('(display-mode: standalone)').matches);

  /* Apple Maps, public transport; a place without numeric coordinates is searched by name */
  function appleRoute(e, mode = 'r') {
    const lat = e.lat === '' || e.lat == null ? NaN : +e.lat, lng = e.lng === '' || e.lng == null ? NaN : +e.lng;
    const to = Number.isFinite(lat) && Number.isFinite(lng) ? `${lat},${lng}` : encodeURIComponent((e.pname || e.to || e.t || '') + ' Japan');
    return `https://maps.apple.com/?daddr=${to}&dirflg=${mode}`;
  }

  /* ---------- iCalendar (RFC 5545) ---------- */
  const escText = s => String(s == null ? '' : s).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r\n|\r|\n/g, '\\n');
  const enc = new TextEncoder();
  /* lines longer than 75 octets continue on the next line after CRLF + space, never inside a UTF-8 character */
  function fold(line) {
    const out = []; let cur = '', n = 0;
    for (const ch of line) {
      const b = enc.encode(ch).length;
      if (n + b > (out.length ? 74 : 75)) { out.push(cur); cur = ''; n = 0; }
      cur += ch; n += b;
    }
    out.push(cur);
    return out.join('\r\n ');
  }
  const p2 = v => String(v).padStart(2, '0');
  function stampOf(iso, min) {
    const d = new Date(iso + 'T00:00:00Z'); d.setUTCMinutes(d.getUTCMinutes() + min);
    return `${d.getUTCFullYear()}${p2(d.getUTCMonth() + 1)}${p2(d.getUTCDate())}T${p2(d.getUTCHours())}${p2(d.getUTCMinutes())}00`;
  }
  const TZ = ['BEGIN:VTIMEZONE', 'TZID:Asia/Tokyo', 'BEGIN:STANDARD', 'DTSTART:19700101T000000',
              'TZOFFSETFROM:+0900', 'TZOFFSETTO:+0900', 'TZNAME:JST', 'END:STANDARD', 'END:VTIMEZONE'];

  /* events: [{id, t, ns, ne, leave?, loc?, note?, url?}] in minutes from midnight of dateISO (Japan time).
     A stable UID per stop means a second export updates the stop instead of adding a copy. */
  function ics({ name, dateISO, events, stamp, seq = 0 }) {
    const L = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//japan-2026//TODAY//RU', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
               'X-WR-CALNAME:' + escText(name || 'Поездка'), 'X-WR-TIMEZONE:Asia/Tokyo', ...TZ];
    events.forEach(e => {
      const end = Number.isFinite(e.ne) && e.ne > e.ns ? e.ne : e.ns + 15;
      const before = Number.isFinite(e.leave) && e.leave < e.ns ? Math.round(e.ns - e.leave) : 10;
      L.push('BEGIN:VEVENT', `UID:${String(e.id).replace(/[^\w.-]/g, '_')}@japan-2026`, 'DTSTAMP:' + stamp, 'SEQUENCE:' + seq,
        'DTSTART;TZID=Asia/Tokyo:' + stampOf(dateISO, e.ns), 'DTEND;TZID=Asia/Tokyo:' + stampOf(dateISO, end),
        'SUMMARY:' + escText(e.t));
      if (e.loc) L.push('LOCATION:' + escText(e.loc));
      if (e.note) L.push('DESCRIPTION:' + escText(e.note));
      if (e.url) L.push('URL:' + e.url);
      if (e.alarm !== false) L.push('BEGIN:VALARM', 'ACTION:DISPLAY',
        'DESCRIPTION:' + escText((Number.isFinite(e.leave) && e.leave < e.ns ? 'Пора выходить: ' : 'Скоро: ') + e.t),
        `TRIGGER:-PT${before}M`, 'END:VALARM');
      L.push('END:VEVENT');
    });
    L.push('END:VCALENDAR');
    return L.map(fold).join('\r\n') + '\r\n';
  }

  /* ---------- in the app ---------- */
  const routeUrl = e => isIOS() ? appleRoute(e) : groute(e);
  const walkUrl = e => isIOS() ? appleRoute(e, 'w') : groute(e).replace('travelmode=transit', 'travelmode=walking');

  /* the stops of a day worth a calendar entry, planned as they stand now */
  function dayEvents(day) {
    const x = ctx();
    const evs = day.n === x.cday.n ? x.cevs : plan(day, null);
    return evs.filter(e => !e.skip && !e.auto && !e.bad && e.cat !== 'routine').map(e => ({
      id: e.id, t: e.t, ns: e.ns, ne: e.ne, leave: Core.travel(e) > 0 ? e.leave : null,
      // alarms only on what matters: departures, bought/booked things, events (owners' choice)
      alarm: Core.isAnchor(e) || !!e.bk || e.cat === 'event' || e.cat === 'transport',
      loc: e.frm && e.to ? `${e.frm} → ${e.to}` : (e.pname || e.to || ''),
      note: [e.note, routeUrl(e)].filter(Boolean).join('\n'), url: Core.safeUrl(e.link),
    }));
  }

  function calendarForDay(day) {
    const evs = dayEvents(day), iso = dateOf(day);
    const d = new Date(iso + 'T12:00:00Z');
    const when = d.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' });
    sheet('В Календарь', `
      <p class="tc-sub">${esc(when)} · ${evs.length} ${evs.length === 1 ? 'событие' : evs.length < 5 && evs.length ? 'события' : 'событий'}.
        Напоминания — только на важном: переезды, брони и события; приходят в момент «выйти», даже если приложение закрыто.</p>
      <div class="tc-group" id="tcCal">${evs.map(e => `<div class="tc-calrow"><b>${hm(e.ns)}</b><span>${esc(e.t)}</span>
        ${e.alarm ? `<em>${icon('bell')}${hm(e.leave != null ? e.leave : e.ns - 10)}</em>` : '<em></em>'}</div>`).join('')}</div>
      <button type="button" class="tc-btn primary wide" id="tcCalGo">${icon('cal')}${isIOS() ? 'Добавить в Календарь iPhone' : 'Скачать .ics'}</button>`,
    m => m.querySelector('#tcCalGo').addEventListener('click', () => {
      const txt = ics({ name: T.name, dateISO: iso, events: evs,
                        stamp: new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+/, ''),
                        seq: Math.floor(Date.now() / 60000) % 1e8 });
      const url = URL.createObjectURL(new Blob([txt], { type: 'text/calendar;charset=utf-8' }));
      const a = document.createElement('a');
      a.href = url;
      // Safari on iPhone opens a text/calendar file straight in Calendar; elsewhere it's a download
      if (!isIOS()) a.download = `trip-day-${day.n}.ics`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    }));
  }

  /* keep the screen on while «Пора выходить» is up; the ticket holds its own lock */
  function keepAwake(on) {
    if (on) Wake.on();
    else { const t = document.getElementById('tcTicket'); if (!t || t.hidden) Wake.off(); }
  }

  /* Safari only: the first screen suggests «На экран „Домой“» once; the cross hides it for good */
  const HINT_KEY = 'japan2026.install.v1';
  function installHint() {
    let hidden = false; try { hidden = !!localStorage.getItem(HINT_KEY); } catch (e) {}
    if (!isIOS() || standalone() || hidden) return '';
    return `<section class="tc-card tc-install" id="tcInstall"><span class="tc-install-ic" aria-hidden="true"><i></i></span>
      <div><b>Установите на экран «Домой»</b><span class="tc-sub">Нажмите ${icon('share')} «Поделиться» → «На экран „Домой“».
        Сделайте это до того, как прикреплять билеты: у приложения на экране «Домой» своё хранилище.</span></div>
      <button type="button" class="tc-x" id="tcInstallX" aria-label="Скрыть подсказку">${icon('close')}</button></section>`;
  }
  function wireInstall(root) {
    const x = root.querySelector('#tcInstallX');
    if (x) x.addEventListener('click', () => { try { localStorage.setItem(HINT_KEY, '1'); } catch (e) {} renderShell(); });
  }

  return { isIOS, standalone, appleRoute, escText, fold, ics, routeUrl, walkUrl, dayEvents, calendarForDay, keepAwake, installHint, wireInstall };
})();
