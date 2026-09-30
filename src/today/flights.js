/* ---------- flights: what the app knows without the network ----------
   A flight number like «MU 575» gives the airline; a number we already know (the trip's own flights,
   baked in) gives the route and times; airports give the time zone, so the countdown is right even
   when the phone is still on home time. Live status is a link to Flightradar24 — a live schedule API
   would need a secret key, which can't live in a public offline page. Pure: tested in a blank page. */
const Flights = (() => {
  const AIRLINES = {
    MU: 'China Eastern', FM: 'Shanghai Airlines', CA: 'Air China', CZ: 'China Southern', HU: 'Hainan Airlines',
    '3U': 'Sichuan Airlines', MF: 'Xiamen Air', HO: 'Juneyao Air', '9C': 'Spring Airlines', KC: 'Air Astana',
    DV: 'SCAT', FS: 'FlyArystan', HY: 'Uzbekistan Airways', NH: 'ANA', JL: 'Japan Airlines', MM: 'Peach',
    GK: 'Jetstar Japan', BC: 'Skymark', ZG: 'ZIPAIR', KE: 'Korean Air', OZ: 'Asiana', '7C': 'Jeju Air',
    TW: "T'way Air", LJ: 'Jin Air', TK: 'Turkish Airlines', PC: 'Pegasus', EK: 'Emirates', FZ: 'flydubai',
    QR: 'Qatar Airways', EY: 'Etihad', SU: 'Aeroflot', CX: 'Cathay Pacific', UO: 'HK Express', BR: 'EVA Air',
    CI: 'China Airlines', SQ: 'Singapore Airlines', TG: 'Thai Airways', VN: 'Vietnam Airlines',
    LH: 'Lufthansa', AF: 'Air France', KL: 'KLM', BA: 'British Airways', AY: 'Finnair',
  };
  /* code: [name, UTC offset in minutes (no summer time) or an IANA zone where there is one] */
  const AIRPORTS = {
    ALA: ['Алматы', 300], NQZ: ['Астана', 300], CIT: ['Шымкент', 300], GUW: ['Атырау', 300], SCO: ['Актау', 300],
    AKX: ['Актобе', 300], KGF: ['Караганда', 300], PWQ: ['Павлодар', 300], UKK: ['Усть-Каменогорск', 300],
    TAS: ['Ташкент', 300], FRU: ['Бишкек', 360], DYU: ['Душанбе', 300],
    PVG: ['Шанхай Пудун', 480], SHA: ['Шанхай Хунцяо', 480], PEK: ['Пекин', 480], PKX: ['Пекин Дасин', 480],
    CAN: ['Гуанчжоу', 480], SZX: ['Шэньчжэнь', 480], CTU: ['Чэнду', 480], TFU: ['Чэнду Тяньфу', 480],
    URC: ['Урумчи', 480], XIY: ['Сиань', 480], TAO: ['Циндао', 480], HKG: ['Гонконг', 480], TPE: ['Тайбэй', 480],
    HND: ['Токио Ханэда', 540], NRT: ['Токио Нарита', 540], KIX: ['Осака Кансай', 540], ITM: ['Осака Итами', 540],
    NGO: ['Нагоя', 540], FUK: ['Фукуока', 540], CTS: ['Саппоро', 540], OKA: ['Окинава', 540],
    ICN: ['Сеул Инчхон', 540], GMP: ['Сеул Кимпхо', 540], PUS: ['Пусан', 540],
    IST: ['Стамбул', 180], SAW: ['Стамбул Сабиха', 180], DXB: ['Дубай', 240], DWC: ['Дубай Аль-Мактум', 240],
    AUH: ['Абу-Даби', 240], DOH: ['Доха', 180], SVO: ['Москва Шереметьево', 180], DME: ['Москва Домодедово', 180],
    VKO: ['Москва Внуково', 180], LED: ['Санкт-Петербург', 180], BKK: ['Бангкок', 420], SIN: ['Сингапур', 480],
    KUL: ['Куала-Лумпур', 480], DEL: ['Дели', 330],
    FRA: ['Франкфурт', 'Europe/Berlin'], MUC: ['Мюнхен', 'Europe/Berlin'], CDG: ['Париж', 'Europe/Paris'],
    AMS: ['Амстердам', 'Europe/Amsterdam'], LHR: ['Лондон', 'Europe/London'], HEL: ['Хельсинки', 'Europe/Helsinki'],
  };
  const JAPAN = new Set(['HND', 'NRT', 'KIX', 'ITM', 'NGO', 'FUK', 'CTS', 'OKA']);
  const NO = /^([A-Z0-9]{2})(\d{1,4})$/, CODE = /^[A-Z]{3}$/, DATE = /^\d{4}-\d{2}-\d{2}$/, TIME = /^([01]?\d|2[0-3]):[0-5]\d$/;

  const normNo = s => String(s || '').toUpperCase().replace(/[\s-]/g, '');
  const pretty = no => { const m = NO.exec(no); return m ? `${m[1]} ${+m[2]}` : no; };
  const airline = no => { const m = NO.exec(normNo(no)); return m ? AIRLINES[m[1]] || null : null; };
  const airport = code => AIRPORTS[code] ? AIRPORTS[code][0] : code;

  /* minutes east of UTC at that airport and moment; `off` is the traveller's own choice for an unknown airport */
  function offsetAt(code, utcMs, off) {
    const z = AIRPORTS[code] && AIRPORTS[code][1];
    if (typeof z === 'number') return z;
    if (typeof z === 'string') {
      try {
        const p = {}; new Intl.DateTimeFormat('en-US', { timeZone: z, hourCycle: 'h23', year: 'numeric', month: 'numeric',
          day: 'numeric', hour: 'numeric', minute: 'numeric' }).formatToParts(new Date(utcMs)).forEach(x => { p[x.type] = +x.value; });
        return Math.round((Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute) - Math.floor(utcMs / 60000) * 60000) / 60000);
      } catch (e) { /* fall through */ }
    }
    return Number.isFinite(+off) ? +off : null;
  }
  /* a local date and time at an airport → epoch ms (null when the zone is unknown) */
  function epochOf(dateISO, hhmm, code, off) {
    if (!DATE.test(dateISO) || !TIME.test(hhmm)) return null;
    const [y, mo, d] = dateISO.split('-').map(Number), [h, mi] = hhmm.split(':').map(Number);
    const local = Date.UTC(y, mo - 1, d, h, mi);
    let o = offsetAt(code, local, off); if (o == null) return null;
    o = offsetAt(code, local - o * 60000, off);          // second pass settles summer-time edges
    return local - o * 60000;
  }
  /* departure and arrival as epochs; the arrival day is the first one after departure */
  function times(leg) {
    const dep = epochOf(leg.date, leg.dep, leg.frm, leg.frmOff);
    if (dep == null) return null;
    let arr = null;
    if (TIME.test(leg.arr || '')) {
      for (let k = 0; k < 3 && (arr == null || arr <= dep); k++) {
        const d = new Date(Date.parse(leg.date + 'T00:00:00Z') + k * 864e5).toISOString().slice(0, 10);
        arr = epochOf(d, leg.arr, leg.to, leg.toOff);
      }
      if (arr != null && arr <= dep) arr = null;
    }
    return { dep, arr };
  }

  /* number → what we know about it: airline always, route and times when the flight is known */
  function lookup(no, known) {
    const n = normNo(no), m = NO.exec(n);
    if (!m) return null;
    const k = (known || []).find(f => normNo(f.no) === n);
    return { no: n, airline: AIRLINES[m[1]] || null,
             ...(k ? { frm: k.frm, dep: k.dep, to: k.to, arr: k.arr, frmOff: k.frmOff, toOff: k.toOff } : {}) };
  }

  /* one leg as entered: valid fields only; null when it can't be counted down */
  function clean(f) {
    if (!f || typeof f !== 'object') return null;
    const no = normNo(f.no), frm = String(f.frm || '').toUpperCase(), to = String(f.to || '').toUpperCase();
    const x = { no, date: String(f.date || ''), frm, dep: String(f.dep || ''), to, arr: String(f.arr || '') };
    if (!NO.test(no) || !DATE.test(x.date) || !CODE.test(frm) || !CODE.test(to) || !TIME.test(x.dep)) return null;
    if (!TIME.test(x.arr)) x.arr = '';
    ['frmOff', 'toOff'].forEach(k => { const v = +f[k]; if (f[k] !== '' && f[k] != null && Number.isInteger(v) && v >= -720 && v <= 840) x[k] = v; });
    return times(x) ? x : null;
  }
  const cleanList = list => (Array.isArray(list) ? list : []).map(clean).filter(Boolean)
    .sort((a, b) => times(a).dep - times(b).dep);

  /* the next departure after `nowMs`, and whether the chain it starts is heading to Japan or home */
  function next(list, nowMs) {
    const legs = cleanList(list);
    const i = legs.findIndex(l => times(l).dep > nowMs);
    if (i < 0) return null;
    let dir = null;
    for (const l of legs.slice(i)) {
      if (JAPAN.has(l.frm)) { dir = 'home'; break; }
      if (JAPAN.has(l.to)) { dir = 'japan'; break; }
    }
    const chain = [];                 // the legs flown back to back from here (layovers under a day)
    for (let j = i; j < legs.length; j++) {
      if (j > i) { const p = times(legs[j - 1]); if (!p.arr || times(legs[j]).dep - p.arr > 864e5) break; }
      chain.push(legs[j]);
    }
    return { leg: legs[i], dir, chain, ...times(legs[i]) };
  }

  /* days, hours, minutes left; `unit` is the Russian word for the days */
  function countdown(ms) {
    const m = Math.max(0, Math.floor(ms / 60000)), d = Math.floor(m / 1440), h = Math.floor(m % 1440 / 60), mi = m % 60;
    const unit = d % 10 === 1 && d % 100 !== 11 ? 'день' : [2, 3, 4].includes(d % 10) && ![12, 13, 14].includes(d % 100) ? 'дня' : 'дней';
    return { d, h, m: mi, unit };
  }
  const statusUrl = no => `https://www.flightradar24.com/data/flights/${normNo(no).toLowerCase()}`;
  const codes = () => Object.keys(AIRPORTS);

  /* where the traveller is: before the trip, departure day, in transit, in Japan, after.
     The outbound chain is the legs up to and including the first one landing in Japan; a leg beyond
     it (the way home) never counts. Without such a leg — no flights entered, only a return chain, or
     the earliest leg already starts from Japan — the phase follows the trip's own dates instead. */
  const JST = 540;
  const dayStart = (iso, off) => Date.parse(iso + 'T00:00:00Z') - off * 60000;
  const byDates = (nowMs, firstISO) => ({ phase: nowMs < dayStart(firstISO, JST) ? 'pre' : 'live', dep: null, arrive: null, leg: null });
  function phase(nowMs, list, firstISO, lastISO) {
    const legs = cleanList(list);
    const end = dayStart(lastISO, JST) + 864e5;
    if (nowMs >= end) return { phase: 'post', dep: null, arrive: null, leg: null };
    if (!legs.length) return byDates(nowMs, firstISO);
    const outboundEnd = legs.findIndex(l => JAPAN.has(l.to));
    if (outboundEnd < 0 || JAPAN.has(legs[0].frm)) return byDates(nowMs, firstISO);
    const chain = legs.slice(0, outboundEnd + 1);
    const first = chain[0], t0 = times(first);
    const o = offsetAt(first.frm, t0.dep, first.frmOff) || 0;
    const arrive = times(chain[chain.length - 1]).arr;
    if (nowMs < dayStart(first.date, o)) return { phase: 'pre', dep: t0.dep, arrive, leg: first };
    if (nowMs < t0.dep) return { phase: 'departure', dep: t0.dep, arrive, leg: first };
    const landed = arrive != null ? nowMs >= arrive : nowMs >= dayStart(firstISO, JST);
    if (!landed) {
      const inFlight = chain.find(l => { const tt = times(l); return tt.dep <= nowMs && (tt.arr == null || nowMs < tt.arr); });
      const leg = inFlight || chain.find(l => times(l).dep > nowMs) || chain[chain.length - 1];
      return { phase: 'transit', dep: t0.dep, arrive, leg };
    }
    return { phase: 'live', dep: t0.dep, arrive, leg: null };
  }

  return { AIRLINES, AIRPORTS, normNo, pretty, airline, airport, offsetAt, epochOf, times, lookup, clean, cleanList,
           next, countdown, statusUrl, codes, isJapan: c => JAPAN.has(c), phase };
})();
