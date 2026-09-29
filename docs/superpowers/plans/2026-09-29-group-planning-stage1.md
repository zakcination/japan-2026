# Group Planning — Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the group plan together: name + PIN login, join parts/days/stops with opt-outs, a personal schedule
(joined group stops + own stops), «Дела» with ticket-buying recipes, tickets as files or links (private or shared),
old tasks imported, all working offline with a write queue — backed by Supabase.

**Architecture:** Supabase is reached with plain `fetch` (no supabase-js): Auth (anonymous sign-in + refresh), one
read RPC `group_state` and write RPCs (all `security definer`, checking the caller's member via `member_devices`);
direct table access is denied by RLS; ticket files go to a private Storage bucket. The app keeps the last state in
`localStorage`, applies writes optimistically, queues them in an outbox and polls every 30 s. Pure logic (who is in,
personal schedule, tasks) lives in `group/model.js`, tested in a blank page. UI tests route the Supabase host to a
Python fake (`tests/fake_supabase.py`) that implements the same RPCs; a contract script runs the same scenarios
against the real project.

**Tech Stack:** Vanilla JS modules glued by `src/build_guide.py`; Supabase (Postgres 15, `pgcrypto`, Auth anonymous
sign-ins, Storage); Python 3.9 + pytest + Playwright (sync) in `.venv`; `urllib` for the contract script.

**Spec:** `docs/superpowers/specs/2026-09-29-group-planning-design.md`

## Global Constraints

- Tickets, booking links, seat numbers, booking codes, PINs never go into the repo, `trips/*.json` or public pages; hosts' booking details live only in Supabase (`recipes.host_ref`, `attachments`).
- In the page: only the project URL and the public `anon` key; `service_role` key and VAPID keys never in code.
- PIN: 4 digits; stored only as bcrypt (`crypt(pin, gen_salt('bf'))`); 5 wrong in a row → locked 15 minutes; never stored on the phone.
- Up to 3 devices per member; a host resets a PIN from ⚙.
- Participation: most specific rule wins — stop > day > part; no rule → not going; hosts are "in" everything by default.
- Personal schedule = group stops the member is in (live) + own `my_stops`; replanner, «Сейчас», capsule, day totals and Calendar export work on it; marks are per phone as today.
- Own stops are private unless `shared`; others can join a shared own stop.
- «Брони» tab label becomes «Дела» (tab key stays `tix`).
- Links: `https://` only; site by domain (`highwaybus.com` → «Highway Bus», `booking.com` → «Booking.com», `smart-ex.jp` → «Smart EX», else the domain); before sharing a link — one warning.
- Without login or without `group` config the app behaves exactly as today (all 83 existing tests stay green).
- Every text from the backend is rendered through `esc()`; links only via `Core.safeUrl`.
- CSP `connect-src` gains `https://*.supabase.co`; nothing else.
- UI copy in Russian; tap targets ≥ 44 px; inputs ≥ 16 px.
- Region Tokyo; free plan; project may sleep after a week idle — ⚙ explains how to wake it.

## Review Focus

1. Offline write, then the phone reloads before sending — the outbox must survive the reload and send once (test in Task 5).
2. Two phones: guest joins a part while a host moves a stop in it — the guest sees the moved stop at the new time on next poll (Task 7).
3. Wrong PIN five times, then the right one — refused until the lock ends; the lock is per member, not per phone (Tasks 1–2).
4. A shared own stop whose author later un-shares it — others who joined keep nothing broken: it disappears from their schedule with no error (Task 7).
5. Token expiry during a long offline stretch — refresh on reconnect; if refresh fails, ask for PIN again, keep the outbox (Task 5).

---

## File Structure

| File | Responsibility |
|---|---|
| `supabase/migrations/001_group.sql` | tables, RLS (deny direct), RPCs, storage policies |
| `tools/seed_group.py` | generates `supabase/seed.sql` from `trips/miras-aikosh.json` + parts + recipes (no private data) |
| `src/today_data.py` | adds `PARTS`, `RECIPES`, `GROUP` config (url/anon) to our trip |
| `src/tests/fake_supabase.py` | Python fake of Auth + RPCs + Storage, used by Playwright routes and contract tests |
| `src/tests/group_contract.py` | the RPC scenarios; runs against the fake in pytest and against the real project by hand |
| `src/today/group/model.js` | pure: `Group.effective`, `Group.personalTrip`, `Group.tasks`, `Group.siteOf`, `Group.overlaps` |
| `src/today/group/api.js` | `Api`: auth session, rpc, storage, outbox, polling, cached state |
| `src/today/group/ui_login.js` | «Кто вы?» + PIN sheet; ⚙ group section (members, reset PIN, status) |
| `src/today/group/ui_join.js` | «День»: plan switch, part chip/sheet, avatars, «Я еду / Без меня», own stops |
| `src/today/group/ui_tasks.js` | «Дела»: tasks with recipes, host_ref, done, import; hosts' recipe editor |
| `src/today/group/ui_attach.js` | attachments: file or link, private/shared, upload/download, open |
| `src/today/store.js` | `TV()` — the trip being shown (personal or group) |
| `src/build_guide.py` | module list, CSP |
| `README.md` | Supabase setup (spec §13) |

Module order in `TODAY_MODULES`: `core.js, flights.js, store.js, trips.js, group/model.js, group/api.js, ios.js, ui/shell.js, ui/flights.js, ui/now.js, ui/day.js, ui/bookings.js, ui/stats.js, ui/settings.js, group/ui_login.js, group/ui_join.js, group/ui_tasks.js, group/ui_attach.js, boot.js`.

## Data contracts (used by every task)

```text
member   {id: uuid, name, role: 'host'|'guest'}
part     {id: text, title, days: [n], stops: [stopId] | null}      // null = every stop of those days
join     {member, scope: 'part'|'day'|'stop'|'mine', ref: text, mode: 'in'|'out'}
          // ref: part id | day n as text | group stop id | my_stop id (joining someone's shared own stop)
my_stop  {id: 'm-<uuid>', member, day: n, ev: {s, e, t, cat, st, ...same fields as plan stops}, shared: bool}
recipe   {bk, what, site, url, opens: ISO|null, opens_note, buy_by: date|null, price_pp: int|null, tips, host_ref}
my_booking {id: 'mb-<uuid>', member, stops: [my_stop id], recipe fields...}
task     {id, title, note, url, due: date|null, assignee: member|null (null = everyone)}
task_state {ref: 'bk:<id>'|'mb:<id>'|'t:<id>', done: bool, at}
attachment {id, member, ref: 'bk:<id>'|'mb:<id>', kind: 'file'|'link', url|null, path|null, name, site, shared}
state (group_state RPC) {me: member, trip: {id, name}, plan: {doc, version}, members: [member], parts, joins,
       recipes, tasks, my_stops, my_bookings, task_state, attachments, now: ISO}
```

---

### Task 1: Fake Supabase and the RPC contract (defines the API)

**Files:**
- Create: `src/tests/fake_supabase.py`, `src/tests/group_contract.py`, `src/tests/test_group_contract.py`

**Interfaces:**
- Produces: HTTP API (same paths as Supabase):
  - `POST /auth/v1/signup` body `{}` → `{access_token, refresh_token, expires_in: 3600, user: {id}}`
  - `POST /auth/v1/token?grant_type=refresh_token` body `{refresh_token}` → same shape
  - `POST /rest/v1/rpc/<name>` headers `apikey`, `Authorization: Bearer <access_token>`, JSON body → JSON result; errors `{code, message}` with status 400 (`P0001` business error) / 401
  - `POST /storage/v1/object/tickets/<path>` (upload, raw body, `Content-Type`), `GET /storage/v1/object/authenticated/tickets/<path>` (download)
- RPCs: `member_names(p_trip)` (any signed-in session; `[{id, name}]` only — added in Task 5), `group_state(p_trip)`, `claim_member(p_member, p_pin)`, `set_join(p_scope, p_ref, p_mode)`, `save_my_stop(p_stop)`, `delete_my_stop(p_id)`, `save_my_booking(p_b)`, `set_task_state(p_ref, p_done)`, `save_attachment(p_a)`, `delete_attachment(p_id)`, hosts only: `save_plan(p_doc, p_version)`, `save_part(p_part)`, `save_recipe(p_r)`, `add_member(p_name, p_role)`, `reset_pin(p_member)`, `save_task(p_task)`, `import_tasks(p_tasks)`.
- `group_contract.py` exposes `run_all(client)` where `client.signup() -> token`, `client.rpc(token, name, args) -> (status, json)`.

- [ ] **Step 1: Write the contract scenarios** (`src/tests/group_contract.py`)

```python
"""RPC scenarios shared by the fake (pytest) and the real Supabase project (python3 src/tests/group_contract.py)."""
import json, os, sys, urllib.request

TRIP = "miras-aikosh"


def ok(r):
    st, body = r
    assert st == 200, (st, body)
    return body


def err(r, code_part):
    st, body = r
    assert st >= 400 and code_part in json.dumps(body, ensure_ascii=False), (st, body)


def run_all(c, host_id, host_pin):
    """host_id/host_pin: a seeded host (seed sets PIN for the first host via the owner)."""
    host = c.signup(); ok(c.rpc(host, "claim_member", {"p_member": host_id, "p_pin": host_pin}))
    s = ok(c.rpc(host, "group_state", {"p_trip": TRIP}))
    assert s["me"]["role"] == "host" and s["plan"]["version"] >= 1
    # host adds Saniya; she sets her PIN on first claim
    san = ok(c.rpc(host, "add_member", {"p_name": "Сания", "p_role": "guest"}))["id"]
    g = c.signup(); ok(c.rpc(g, "claim_member", {"p_member": san, "p_pin": "4821"}))
    # a stranger (signed in, not claimed) sees nothing and can write nothing
    x = c.signup()
    err(c.rpc(x, "group_state", {"p_trip": TRIP}), "not a member")
    err(c.rpc(x, "set_join", {"p_scope": "part", "p_ref": "fuji", "p_mode": "in"}), "not a member")
    # wrong PIN 5 times locks the member, even with the right PIN after
    y = c.signup()
    for _ in range(5):
        err(c.rpc(y, "claim_member", {"p_member": san, "p_pin": "0000"}), "PIN")
    err(c.rpc(y, "claim_member", {"p_member": san, "p_pin": "4821"}), "locked")
    # guest joins a part and opts out of one stop
    ok(c.rpc(g, "set_join", {"p_scope": "part", "p_ref": "fuji", "p_mode": "in"}))
    ok(c.rpc(g, "set_join", {"p_scope": "stop", "p_ref": "d2e5", "p_mode": "out"}))
    gs = ok(c.rpc(g, "group_state", {"p_trip": TRIP}))
    mine = [j for j in gs["joins"] if j["member"] == san]
    assert {(j["scope"], j["ref"], j["mode"]) for j in mine} == {("part", "fuji", "in"), ("stop", "d2e5", "out")}
    # guest cannot change the plan, hosts can (with version check)
    err(c.rpc(g, "save_plan", {"p_doc": gs["plan"]["doc"], "p_version": gs["plan"]["version"]}), "host")
    v = gs["plan"]["version"]
    ok(c.rpc(host, "save_plan", {"p_doc": gs["plan"]["doc"], "p_version": v}))
    err(c.rpc(host, "save_plan", {"p_doc": gs["plan"]["doc"], "p_version": v}), "version")
    # own stops: private unless shared
    ok(c.rpc(g, "save_my_stop", {"p_stop": {"id": "m-1", "day": 3, "ev": {"s": "10:00", "e": "12:00", "t": "Осака"}, "shared": False}}))
    hs = ok(c.rpc(host, "group_state", {"p_trip": TRIP}))
    assert not any(m["id"] == "m-1" for m in hs["my_stops"])
    ok(c.rpc(g, "save_my_stop", {"p_stop": {"id": "m-1", "day": 3, "ev": {"s": "10:00", "e": "12:00", "t": "Осака"}, "shared": True}}))
    hs = ok(c.rpc(host, "group_state", {"p_trip": TRIP}))
    assert any(m["id"] == "m-1" for m in hs["my_stops"])
    # task state is private
    ok(c.rpc(g, "set_task_state", {"p_ref": "bk:bus18", "p_done": True}))
    hs = ok(c.rpc(host, "group_state", {"p_trip": TRIP}))
    assert not any(t["ref"] == "bk:bus18" for t in hs["task_state"])
    # attachments: private unless shared; links must be https
    err(c.rpc(g, "save_attachment", {"p_a": {"id": "a-1", "ref": "bk:bus18", "kind": "link", "url": "javascript:alert(1)", "name": "x"}}), "https")
    ok(c.rpc(g, "save_attachment", {"p_a": {"id": "a-1", "ref": "bk:bus18", "kind": "link", "url": "https://www.highwaybus.com/x", "name": "Бронь", "shared": False}}))
    hs = ok(c.rpc(host, "group_state", {"p_trip": TRIP}))
    assert not any(a["id"] == "a-1" for a in hs["attachments"])
    # host resets the PIN; the old device keeps working, a new claim needs the new PIN
    ok(c.rpc(host, "reset_pin", {"p_member": san}))
    z = c.signup(); ok(c.rpc(z, "claim_member", {"p_member": san, "p_pin": "1111"}))
    return True


class Real:
    """python3 src/tests/group_contract.py <url> <anon-key> <host-member-uuid> <host-pin>"""
    def __init__(self, url, anon):
        self.url, self.anon = url.rstrip("/"), anon

    def _post(self, path, body, token=None):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"apikey": self.anon, "Content-Type": "application/json",
                                              "Authorization": "Bearer " + (token or self.anon)})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"null")

    def signup(self):
        return self._post("/auth/v1/signup", {})[1]["access_token"]

    def rpc(self, token, name, args):
        return self._post(f"/rest/v1/rpc/{name}", args, token)


if __name__ == "__main__":
    url, anon, host_id, pin = sys.argv[1:5]
    print("contract ok:", run_all(Real(url, anon), host_id, pin))
```

- [ ] **Step 2: Write the pytest wrapper** (`src/tests/test_group_contract.py`)

```python
from fake_supabase import FakeSupabase
from group_contract import run_all


def test_contract_on_the_fake():
    f = FakeSupabase.seeded()
    assert run_all(f.client(), f.host_id, f.host_pin)
```

- [ ] **Step 3: Run — fails** (`ModuleNotFoundError: fake_supabase`)

Run: `.venv/bin/pytest src/tests/test_group_contract.py -q`

- [ ] **Step 4: Implement the fake** (`src/tests/fake_supabase.py`)

```python
"""An in-memory stand-in for the parts of Supabase the app uses: anonymous auth, the group RPCs, ticket storage.
Semantics mirror supabase/migrations/001_group.sql; the contract (group_contract.py) keeps them honest."""
import copy, hashlib, json, pathlib, time, uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
TRIP = "miras-aikosh"


class RpcError(Exception):
    def __init__(self, status, message):
        super().__init__(message); self.status, self.message = status, message


def _h(pin):
    return hashlib.sha256(("salt:" + pin).encode()).hexdigest()   # the real DB uses bcrypt


class FakeSupabase:
    def __init__(self):
        self.tokens = {}            # access token -> uid
        self.refresh = {}           # refresh token -> uid
        self.devices = {}           # uid -> member id
        self.members = {}           # id -> {id, name, role, pin_hash, fails, locked_until}
        self.plan = {"doc": None, "version": 1}
        self.parts, self.joins, self.recipes, self.tasks = [], [], {}, []
        self.my_stops, self.my_bookings, self.task_state, self.attachments = {}, {}, {}, {}
        self.files = {}
        self.clock = time.time      # tests may replace it
        self.fail_network = False   # tests flip it to simulate no signal

    # ---------- seed ----------
    @classmethod
    def seeded(cls):
        f = cls()
        trip = json.loads((ROOT / "trips" / f"{TRIP}.json").read_text(encoding="utf-8"))
        f.plan["doc"] = {k: v for k, v in trip.items() if k not in ("group",)}
        f.parts = copy.deepcopy(trip.get("parts", []))
        f.recipes = {r["bk"]: dict(r, host_ref="") for r in trip.get("recipes", [])}
        f.host_id = f._add("Мирас", "host"); f._add("Айкош", "host")
        f.host_pin = "2468"
        f.members[f.host_id]["pin_hash"] = _h(f.host_pin)
        return f

    def _add(self, name, role):
        i = str(uuid.uuid4())
        self.members[i] = {"id": i, "name": name, "role": role, "pin_hash": None, "fails": 0, "locked_until": 0}
        return i

    # ---------- auth ----------
    def signup(self):
        uid = str(uuid.uuid4()); a, r = "at-" + uid, "rt-" + uid
        self.tokens[a] = uid; self.refresh[r] = uid
        return {"access_token": a, "refresh_token": r, "expires_in": 3600, "user": {"id": uid}}

    def refresh_token(self, rt):
        uid = self.refresh.get(rt)
        if not uid: raise RpcError(401, "invalid refresh token")
        a = "at-" + str(uuid.uuid4()); self.tokens[a] = uid
        return {"access_token": a, "refresh_token": rt, "expires_in": 3600, "user": {"id": uid}}

    # ---------- helpers ----------
    def _me(self, token, need_host=False):
        uid = self.tokens.get(token)
        if not uid: raise RpcError(401, "JWT expired or invalid")
        mid = self.devices.get(uid)
        if not mid: raise RpcError(400, "not a member")
        m = self.members[mid]
        if need_host and m["role"] != "host": raise RpcError(400, "host only")
        return m

    def _pub(self, m):
        return {k: m[k] for k in ("id", "name", "role")}

    # ---------- RPCs ----------
    def rpc(self, token, name, a):
        fn = getattr(self, "rpc_" + name, None)
        if not fn: raise RpcError(404, "no such function")
        return fn(token, **a)

    def rpc_claim_member(self, token, p_member, p_pin):
        uid = self.tokens.get(token)
        if not uid: raise RpcError(401, "JWT expired or invalid")
        m = self.members.get(p_member)
        if not m: raise RpcError(400, "no such member")
        if m["locked_until"] > self.clock(): raise RpcError(400, "locked, try later")
        if not (isinstance(p_pin, str) and len(p_pin) == 4 and p_pin.isdigit()): raise RpcError(400, "PIN must be 4 digits")
        if m["pin_hash"] is None:
            m["pin_hash"] = _h(p_pin)
        elif m["pin_hash"] != _h(p_pin):
            m["fails"] += 1
            if m["fails"] >= 5: m["locked_until"], m["fails"] = self.clock() + 900, 0
            raise RpcError(400, "wrong PIN")
        m["fails"] = 0
        mine = [u for u, x in self.devices.items() if x == p_member]
        if len(mine) >= 3: del self.devices[mine[0]]
        self.devices[uid] = p_member
        return self._pub(m)

    def rpc_group_state(self, token, p_trip):
        m = self._me(token); me = m["id"]
        return copy.deepcopy({
            "me": self._pub(m), "trip": {"id": TRIP, "name": self.plan["doc"]["name"]}, "plan": self.plan,
            "members": [self._pub(x) for x in self.members.values()], "parts": self.parts, "joins": self.joins,
            "recipes": [r if m["role"] == "host" or True else r for r in self.recipes.values()],
            "tasks": [t for t in self.tasks if t.get("assignee") in (None, me)],
            "my_stops": [s for s in self.my_stops.values() if s["member"] == me or s["shared"]],
            "my_bookings": [b for b in self.my_bookings.values() if b["member"] == me],
            "task_state": [dict(ref=k[1], **v) for k, v in self.task_state.items() if k[0] == me],
            "attachments": [x for x in self.attachments.values() if x["member"] == me or x["shared"]],
            "now": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock()))})

    def rpc_set_join(self, token, p_scope, p_ref, p_mode):
        me = self._me(token)["id"]
        if p_scope not in ("part", "day", "stop", "mine") or p_mode not in ("in", "out", "none"): raise RpcError(400, "bad join")
        self.joins = [j for j in self.joins if not (j["member"] == me and j["scope"] == p_scope and j["ref"] == str(p_ref))]
        if p_mode != "none": self.joins.append({"member": me, "scope": p_scope, "ref": str(p_ref), "mode": p_mode})
        return True

    def rpc_save_my_stop(self, token, p_stop):
        me = self._me(token)["id"]; s = dict(p_stop)
        if not str(s.get("id", "")).startswith("m-"): raise RpcError(400, "bad id")
        old = self.my_stops.get(s["id"])
        if old and old["member"] != me: raise RpcError(400, "not yours")
        s["member"], s["shared"] = me, bool(s.get("shared"))
        self.my_stops[s["id"]] = s
        return True

    def rpc_delete_my_stop(self, token, p_id):
        me = self._me(token)["id"]
        if self.my_stops.get(p_id, {}).get("member") == me: del self.my_stops[p_id]
        return True

    def rpc_save_my_booking(self, token, p_b):
        me = self._me(token)["id"]; b = dict(p_b)
        if not str(b.get("id", "")).startswith("mb-"): raise RpcError(400, "bad id")
        if b.get("url") and not str(b["url"]).startswith("https://"): raise RpcError(400, "links must be https")
        b["member"] = me; self.my_bookings[b["id"]] = b
        return True

    def rpc_set_task_state(self, token, p_ref, p_done):
        me = self._me(token)["id"]
        self.task_state[(me, p_ref)] = {"done": bool(p_done), "at": self.clock()}
        return True

    def rpc_save_attachment(self, token, p_a):
        me = self._me(token)["id"]; x = dict(p_a)
        if x.get("kind") not in ("file", "link"): raise RpcError(400, "bad kind")
        if x["kind"] == "link" and not str(x.get("url", "")).startswith("https://"): raise RpcError(400, "links must be https")
        old = self.attachments.get(x["id"])
        if old and old["member"] != me: raise RpcError(400, "not yours")
        x["member"], x["shared"] = me, bool(x.get("shared"))
        self.attachments[x["id"]] = x
        return True

    def rpc_delete_attachment(self, token, p_id):
        me = self._me(token)["id"]
        if self.attachments.get(p_id, {}).get("member") == me: del self.attachments[p_id]
        return True

    def rpc_save_plan(self, token, p_doc, p_version):
        self._me(token, need_host=True)
        if p_version != self.plan["version"]: raise RpcError(400, "plan version changed")
        self.plan = {"doc": p_doc, "version": p_version + 1}
        return self.plan["version"]

    def rpc_save_part(self, token, p_part):
        self._me(token, need_host=True)
        self.parts = [p for p in self.parts if p["id"] != p_part["id"]] + [p_part]
        return True

    def rpc_save_recipe(self, token, p_r):
        self._me(token, need_host=True)
        if p_r.get("url") and not str(p_r["url"]).startswith("https://"): raise RpcError(400, "links must be https")
        self.recipes[p_r["bk"]] = dict(p_r)
        return True

    def rpc_add_member(self, token, p_name, p_role):
        self._me(token, need_host=True)
        if p_role not in ("host", "guest") or not str(p_name).strip(): raise RpcError(400, "bad member")
        return {"id": self._add(str(p_name).strip()[:40], p_role)}

    def rpc_reset_pin(self, token, p_member):
        self._me(token, need_host=True)
        m = self.members[p_member]; m["pin_hash"], m["fails"], m["locked_until"] = None, 0, 0
        return True

    def rpc_save_task(self, token, p_task):
        self._me(token, need_host=True)
        t = dict(p_task); t.setdefault("id", "t-" + str(uuid.uuid4()))
        self.tasks = [x for x in self.tasks if x["id"] != t["id"]] + [t]
        return t["id"]

    def rpc_import_tasks(self, token, p_tasks):
        self._me(token, need_host=True)
        for t in p_tasks: self.rpc_save_task(token, t)
        return len(p_tasks)

    # ---------- storage ----------
    def upload(self, token, path, body, ctype):
        me = self._me(token)["id"]
        if not path.startswith(me + "/"): raise RpcError(403, "not your folder")
        self.files[path] = (body, ctype)
        return {"Key": "tickets/" + path}

    def download(self, token, path):
        me = self._me(token)["id"]
        ok = path.startswith(me + "/") or any(x["shared"] and x.get("path") == path for x in self.attachments.values())
        if not ok or path not in self.files: raise RpcError(404, "not found")
        return self.files[path]

    # ---------- plumbing for tests ----------
    def client(self):
        f = self

        class C:
            def signup(self): return f.signup()["access_token"]

            def rpc(self, token, name, args):
                try: return 200, f.rpc(token, name, args)
                except RpcError as e: return e.status, {"code": "P0001", "message": e.message}
        return C()

    def route(self, route):
        """Playwright handler for https://*.supabase.co/** — call page.route(pattern, fake.route)."""
        req = route.request
        if self.fail_network: return route.abort()
        path = req.url.split(".supabase.co", 1)[1]
        tok = (req.headers.get("authorization") or "").replace("Bearer ", "")
        cors = {"access-control-allow-origin": "*"}
        def send(status, obj=None, body=None, ctype="application/json"):
            route.fulfill(status=status, headers=cors, content_type=ctype,
                          body=body if body is not None else json.dumps(obj, ensure_ascii=False))
        try:
            if req.method == "OPTIONS": return route.fulfill(status=204, headers={**cors, "access-control-allow-headers": "*", "access-control-allow-methods": "*"})
            if path.startswith("/auth/v1/signup"): return send(200, self.signup())
            if path.startswith("/auth/v1/token"): return send(200, self.refresh_token(json.loads(req.post_data or "{}").get("refresh_token")))
            if path.startswith("/rest/v1/rpc/"): return send(200, self.rpc(tok, path.split("/rpc/")[1], json.loads(req.post_data or "{}")))
            if path.startswith("/storage/v1/object/authenticated/tickets/"):
                body, ctype = self.download(tok, path.split("/tickets/", 1)[1]); return send(200, body=body, ctype=ctype)
            if path.startswith("/storage/v1/object/tickets/") and req.method == "POST":
                return send(200, self.upload(tok, path.split("/tickets/", 1)[1], req.post_data_buffer, req.headers.get("content-type", "")))
            return send(404, {"message": "not found"})
        except RpcError as e:
            return send(e.status, {"code": "P0001", "message": e.message})
```

- [ ] **Step 5: Make `seeded()` work before Task 9** — until `trips/miras-aikosh.json` has `parts`/`recipes`, `seeded()` uses `trip.get(...)` defaults (already written). Run the test.

Run: `.venv/bin/pytest src/tests/test_group_contract.py -q` → PASS (the part id `fuji` needs no seed: joins accept any ref).

- [ ] **Step 6: Commit**

```bash
git add src/tests/fake_supabase.py src/tests/group_contract.py src/tests/test_group_contract.py
git commit -m "Group: RPC contract and an in-memory Supabase fake for tests"
```

### Task 2: The real database — migration and seed

**Files:**
- Create: `supabase/migrations/001_group.sql`, `tools/seed_group.py`
- Test: `src/tests/test_group_sql.py` (static checks) + manual contract run (Task 11)

**Interfaces:**
- Consumes: RPC names/args from Task 1.
- Produces: SQL the owner pastes into Supabase; `supabase/seed.sql` generated by `python3 tools/seed_group.py`.

- [ ] **Step 1: Static test** (`src/tests/test_group_sql.py`) — every RPC in the contract exists, is `security definer`, sets `search_path`, and every table has RLS enabled with no permissive policy:

```python
import re
from conftest import ROOT

SQL = (ROOT / "supabase" / "migrations" / "001_group.sql").read_text(encoding="utf-8")
RPCS = ["group_state", "claim_member", "set_join", "save_my_stop", "delete_my_stop", "save_my_booking", "set_task_state",
        "save_attachment", "delete_attachment", "save_plan", "save_part", "save_recipe", "add_member", "reset_pin",
        "save_task", "import_tasks"]
TABLES = ["trips", "members", "member_devices", "plan", "parts", "joins", "recipes", "tasks", "task_state",
          "attachments", "my_stops", "my_bookings"]


def test_every_rpc_is_a_guarded_security_definer():
    for name in RPCS:
        m = re.search(rf"create or replace function public\.{name}\((.*?)\$\$;", SQL, re.S)
        assert m, name
        body = m.group(0)
        assert "security definer" in body and "set search_path = public, extensions" in body, name
        if name not in ("claim_member",):
            assert "_me(" in body or "_host(" in body, name


def test_every_table_has_rls_and_no_open_policy():
    for t in TABLES:
        assert f"alter table public.{t} enable row level security" in SQL, t
    assert "create policy" not in SQL.split("-- storage")[0]      # tables: deny direct access entirely


def test_no_private_values_in_sql():
    assert not re.search(r"\b09[AB]\b|pin_hash\s*=\s*'", SQL)
```

- [ ] **Step 2: Run — fails** (file missing).

- [ ] **Step 3: Write the migration** (`supabase/migrations/001_group.sql`)

```sql
-- Group planning, stage 1. Paste into Supabase → SQL Editor → Run. Idempotent.
create extension if not exists pgcrypto with schema extensions;

create table if not exists public.trips (id text primary key, name text not null);
create table if not exists public.members (
  id uuid primary key default gen_random_uuid(), trip text not null references public.trips(id),
  name text not null check (length(name) between 1 and 40), role text not null check (role in ('host','guest')),
  pin_hash text, fails int not null default 0, locked_until timestamptz);
create table if not exists public.member_devices (
  uid uuid primary key, member uuid not null references public.members(id) on delete cascade, at timestamptz default now());
create table if not exists public.plan (trip text primary key references public.trips(id), doc jsonb not null, version int not null default 1);
create table if not exists public.parts (trip text references public.trips(id), id text, part jsonb not null, primary key (trip, id));
create table if not exists public.joins (member uuid references public.members(id) on delete cascade, scope text check (scope in ('part','day','stop','mine')),
  ref text, mode text check (mode in ('in','out')), primary key (member, scope, ref));
create table if not exists public.recipes (trip text references public.trips(id), bk text, r jsonb not null, primary key (trip, bk));
create table if not exists public.tasks (trip text references public.trips(id), id text, t jsonb not null, assignee uuid, primary key (trip, id));
create table if not exists public.task_state (member uuid references public.members(id) on delete cascade, ref text, done boolean, at timestamptz default now(), primary key (member, ref));
create table if not exists public.attachments (id text primary key, member uuid references public.members(id) on delete cascade, a jsonb not null, shared boolean not null default false);
create table if not exists public.my_stops (id text primary key, member uuid references public.members(id) on delete cascade, s jsonb not null, shared boolean not null default false);
create table if not exists public.my_bookings (id text primary key, member uuid references public.members(id) on delete cascade, b jsonb not null);

alter table public.trips enable row level security;
alter table public.members enable row level security;
alter table public.member_devices enable row level security;
alter table public.plan enable row level security;
alter table public.parts enable row level security;
alter table public.joins enable row level security;
alter table public.recipes enable row level security;
alter table public.tasks enable row level security;
alter table public.task_state enable row level security;
alter table public.attachments enable row level security;
alter table public.my_stops enable row level security;
alter table public.my_bookings enable row level security;
-- no policies on tables: the only way in is the functions below

create or replace function public._me() returns public.members language plpgsql stable security definer
set search_path = public, extensions as $$
declare m public.members;
begin
  select mm.* into m from public.member_devices d join public.members mm on mm.id = d.member where d.uid = auth.uid();
  if m.id is null then raise exception 'not a member' using errcode = 'P0001'; end if;
  return m;
end $$;

create or replace function public._host() returns public.members language plpgsql stable security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  if m.role <> 'host' then raise exception 'host only' using errcode = 'P0001'; end if;
  return m;
end $$;

create or replace function public._https(u text) returns void language plpgsql immutable as $$
begin
  if u is not null and u <> '' and u !~ '^https://[^\s"''<>]+$' then raise exception 'links must be https' using errcode = 'P0001'; end if;
end $$;

create or replace function public.claim_member(p_member uuid, p_pin text) returns jsonb language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members;
begin
  if auth.uid() is null then raise exception 'sign in first' using errcode = 'P0001'; end if;
  select * into m from public.members where id = p_member for update;
  if m.id is null then raise exception 'no such member' using errcode = 'P0001'; end if;
  if m.locked_until is not null and m.locked_until > now() then raise exception 'locked, try later' using errcode = 'P0001'; end if;
  if p_pin !~ '^\d{4}$' then raise exception 'PIN must be 4 digits' using errcode = 'P0001'; end if;
  if m.pin_hash is null then
    update public.members set pin_hash = crypt(p_pin, gen_salt('bf')), fails = 0 where id = m.id;
  elsif m.pin_hash <> crypt(p_pin, m.pin_hash) then
    update public.members set fails = case when fails + 1 >= 5 then 0 else fails + 1 end,
      locked_until = case when fails + 1 >= 5 then now() + interval '15 minutes' else locked_until end where id = m.id;
    return jsonb_build_object('error', 'wrong PIN');   -- committed; the app shows it
  else
    update public.members set fails = 0 where id = m.id;
  end if;
  delete from public.member_devices where member = m.id and uid not in (
    select uid from public.member_devices where member = m.id order by at desc limit 2);
  insert into public.member_devices(uid, member) values (auth.uid(), m.id)
    on conflict (uid) do update set member = excluded.member, at = now();
  return jsonb_build_object('id', m.id, 'name', m.name, 'role', m.role);
end $$;
-- NOTE: a raised exception would roll back the fail counter, so a wrong PIN returns {"error": "wrong PIN"}.
-- The fake raises instead; group_contract treats both as an error (see Step 4).

create or replace function public.group_state(p_trip text) returns jsonb language plpgsql stable security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  if m.trip <> p_trip then raise exception 'not a member' using errcode = 'P0001'; end if;
  return jsonb_build_object(
    'me', jsonb_build_object('id', m.id, 'name', m.name, 'role', m.role),
    'trip', (select to_jsonb(t) from public.trips t where t.id = p_trip),
    'plan', (select jsonb_build_object('doc', doc, 'version', version) from public.plan where trip = p_trip),
    'members', coalesce((select jsonb_agg(jsonb_build_object('id', id, 'name', name, 'role', role)) from public.members where trip = p_trip), '[]'),
    'parts', coalesce((select jsonb_agg(part) from public.parts where trip = p_trip), '[]'),
    'joins', coalesce((select jsonb_agg(jsonb_build_object('member', j.member, 'scope', j.scope, 'ref', j.ref, 'mode', j.mode))
                       from public.joins j join public.members x on x.id = j.member where x.trip = p_trip), '[]'),
    'recipes', coalesce((select jsonb_agg(r) from public.recipes where trip = p_trip), '[]'),
    'tasks', coalesce((select jsonb_agg(t || jsonb_build_object('assignee', assignee)) from public.tasks where trip = p_trip and (assignee is null or assignee = m.id)), '[]'),
    'my_stops', coalesce((select jsonb_agg(s || jsonb_build_object('member', s2.member, 'shared', s2.shared)) from public.my_stops s2
                          join public.members x on x.id = s2.member where x.trip = p_trip and (s2.member = m.id or s2.shared)), '[]'),
    'my_bookings', coalesce((select jsonb_agg(b || jsonb_build_object('member', member)) from public.my_bookings where member = m.id), '[]'),
    'task_state', coalesce((select jsonb_agg(jsonb_build_object('ref', ref, 'done', done, 'at', at)) from public.task_state where member = m.id), '[]'),
    'attachments', coalesce((select jsonb_agg(a || jsonb_build_object('member', a2.member, 'shared', a2.shared)) from public.attachments a2
                             join public.members x on x.id = a2.member where x.trip = p_trip and (a2.member = m.id or a2.shared)), '[]'),
    'now', now());
end $$;

create or replace function public.set_join(p_scope text, p_ref text, p_mode text) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  if p_mode = 'none' then delete from public.joins where member = m.id and scope = p_scope and ref = p_ref; return true; end if;
  insert into public.joins values (m.id, p_scope, p_ref, p_mode) on conflict (member, scope, ref) do update set mode = excluded.mode;
  return true;
end $$;

create or replace function public.save_my_stop(p_stop jsonb) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me(); owner uuid;
begin
  if (p_stop->>'id') !~ '^m-[A-Za-z0-9-]{1,60}$' then raise exception 'bad id' using errcode = 'P0001'; end if;
  select member into owner from public.my_stops where id = p_stop->>'id';
  if owner is not null and owner <> m.id then raise exception 'not yours' using errcode = 'P0001'; end if;
  insert into public.my_stops values (p_stop->>'id', m.id, p_stop - 'shared' - 'member', coalesce((p_stop->>'shared')::boolean, false))
    on conflict (id) do update set s = excluded.s, shared = excluded.shared;
  return true;
end $$;

create or replace function public.delete_my_stop(p_id text) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin delete from public.my_stops where id = p_id and member = m.id; return true; end $$;

create or replace function public.save_my_booking(p_b jsonb) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  if (p_b->>'id') !~ '^mb-[A-Za-z0-9-]{1,60}$' then raise exception 'bad id' using errcode = 'P0001'; end if;
  perform public._https(p_b->>'url');
  insert into public.my_bookings values (p_b->>'id', m.id, p_b - 'member')
    on conflict (id) do update set b = excluded.b where public.my_bookings.member = m.id;
  return true;
end $$;

create or replace function public.set_task_state(p_ref text, p_done boolean) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin
  insert into public.task_state values (m.id, p_ref, p_done, now()) on conflict (member, ref) do update set done = excluded.done, at = now();
  return true;
end $$;

create or replace function public.save_attachment(p_a jsonb) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me(); owner uuid;
begin
  if (p_a->>'kind') not in ('file','link') then raise exception 'bad kind' using errcode = 'P0001'; end if;
  if (p_a->>'kind') = 'link' then
    if coalesce(p_a->>'url','') !~ '^https://[^\s"''<>]+$' then raise exception 'links must be https' using errcode = 'P0001'; end if;
  elsif coalesce(p_a->>'path','') not like m.id::text || '/%' then raise exception 'not your file' using errcode = 'P0001';
  end if;
  select member into owner from public.attachments where id = p_a->>'id';
  if owner is not null and owner <> m.id then raise exception 'not yours' using errcode = 'P0001'; end if;
  insert into public.attachments values (p_a->>'id', m.id, p_a - 'shared' - 'member', coalesce((p_a->>'shared')::boolean, false))
    on conflict (id) do update set a = excluded.a, shared = excluded.shared;
  return true;
end $$;

create or replace function public.delete_attachment(p_id text) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._me();
begin delete from public.attachments where id = p_id and member = m.id; return true; end $$;

create or replace function public.save_plan(p_doc jsonb, p_version int) returns int language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host(); v int;
begin
  update public.plan set doc = p_doc, version = version + 1 where trip = m.trip and version = p_version returning version into v;
  if v is null then raise exception 'plan version changed' using errcode = 'P0001'; end if;
  return v;
end $$;

create or replace function public.save_part(p_part jsonb) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host();
begin
  insert into public.parts values (m.trip, p_part->>'id', p_part) on conflict (trip, id) do update set part = excluded.part;
  return true;
end $$;

create or replace function public.save_recipe(p_r jsonb) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host();
begin
  perform public._https(p_r->>'url');
  insert into public.recipes values (m.trip, p_r->>'bk', p_r) on conflict (trip, bk) do update set r = excluded.r;
  return true;
end $$;

create or replace function public.add_member(p_name text, p_role text) returns jsonb language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host(); i uuid;
begin
  insert into public.members(trip, name, role) values (m.trip, trim(p_name), p_role) returning id into i;
  return jsonb_build_object('id', i);
end $$;

create or replace function public.reset_pin(p_member uuid) returns boolean language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host();
begin
  update public.members set pin_hash = null, fails = 0, locked_until = null where id = p_member and trip = m.trip;
  return true;
end $$;

create or replace function public.save_task(p_task jsonb) returns text language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host(); i text := coalesce(p_task->>'id', 't-' || gen_random_uuid());
begin
  perform public._https(p_task->>'url');
  insert into public.tasks values (m.trip, i, p_task - 'assignee', nullif(p_task->>'assignee','')::uuid)
    on conflict (trip, id) do update set t = excluded.t, assignee = excluded.assignee;
  return i;
end $$;

create or replace function public.import_tasks(p_tasks jsonb) returns int language plpgsql security definer
set search_path = public, extensions as $$
declare m public.members := public._host(); x jsonb; n int := 0;
begin
  for x in select * from jsonb_array_elements(p_tasks) loop perform public.save_task(x); n := n + 1; end loop;
  return n;
end $$;

revoke all on all functions in schema public from public, anon;
grant execute on function public.group_state, public.claim_member, public.set_join, public.save_my_stop, public.delete_my_stop,
  public.save_my_booking, public.set_task_state, public.save_attachment, public.delete_attachment, public.save_plan,
  public.save_part, public.save_recipe, public.add_member, public.reset_pin, public.save_task, public.import_tasks to authenticated;

-- storage: private bucket; a member writes only into <member id>/...; reads own files and files of shared attachments
insert into storage.buckets (id, name, public) values ('tickets', 'tickets', false) on conflict (id) do nothing;
drop policy if exists "tickets write own" on storage.objects;
create policy "tickets write own" on storage.objects for insert to authenticated
  with check (bucket_id = 'tickets' and (storage.foldername(name))[1] = (select member::text from public.member_devices where uid = auth.uid()));
drop policy if exists "tickets read own or shared" on storage.objects;
create policy "tickets read own or shared" on storage.objects for select to authenticated
  using (bucket_id = 'tickets' and (
    (storage.foldername(name))[1] = (select member::text from public.member_devices where uid = auth.uid())
    or exists (select 1 from public.attachments a where a.shared and a.a->>'path' = name
               and a.member in (select id from public.members where trip = (select mm.trip from public.member_devices d join public.members mm on mm.id = d.member where d.uid = auth.uid())))));
```

Update `group_contract.err` to accept either an HTTP error or a 200 body with `{"error": ...}` (the real `claim_member` returns the wrong-PIN error so the counter commits):

```python
def err(r, code_part):
    st, body = r
    text = json.dumps(body, ensure_ascii=False)
    assert (st >= 400 or (isinstance(body, dict) and "error" in body)) and code_part in text, (st, body)
```

- [ ] **Step 4: Seed generator** (`tools/seed_group.py`) — writes `supabase/seed.sql` with the trip, the plan doc (from `trips/miras-aikosh.json`, minus `group`), parts, recipes (without `host_ref`) and the two hosts (no PINs). The owner sets the first host PIN by claiming it in the app (first claim sets the PIN).

```python
"""python3 tools/seed_group.py → supabase/seed.sql (no private data: no PINs, no seats, no booking links)."""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
t = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
q = lambda s: "'" + str(s).replace("'", "''") + "'"
j = lambda o: q(json.dumps(o, ensure_ascii=False)) + "::jsonb"
doc = {k: v for k, v in t.items() if k not in ("group",)}
out = ["-- generated by tools/seed_group.py — run once after 001_group.sql",
       f"insert into public.trips values ('miras-aikosh', {q(t['name'])}) on conflict do nothing;",
       f"insert into public.plan values ('miras-aikosh', {j(doc)}, 1) on conflict (trip) do nothing;"]
for p in t.get("parts", []):
    out.append(f"insert into public.parts values ('miras-aikosh', {q(p['id'])}, {j(p)}) on conflict do nothing;")
for r in t.get("recipes", []):
    out.append(f"insert into public.recipes values ('miras-aikosh', {q(r['bk'])}, {j(dict(r, host_ref=''))}) on conflict do nothing;")
for name in ("Мирас", "Айкош"):
    out.append(f"insert into public.members(trip, name, role) select 'miras-aikosh', {q(name)}, 'host' "
               f"where not exists (select 1 from public.members where trip = 'miras-aikosh' and name = {q(name)});")
(ROOT / "supabase" / "seed.sql").write_text("\n".join(out) + "\n", encoding="utf-8")
print("supabase/seed.sql written")
```

- [ ] **Step 5: Run** `.venv/bin/pytest src/tests/test_group_sql.py src/tests/test_group_contract.py -q` → PASS; `python3 tools/seed_group.py` → file written.

- [ ] **Step 6: Commit**

```bash
git add supabase tools/seed_group.py src/tests/test_group_sql.py src/tests/group_contract.py
git commit -m "Group: Supabase migration (RLS deny-all, guarded RPCs, private ticket storage) and seed generator"
```

### Task 3: Parts, recipes and group config in the trip data

**Files:**
- Modify: `src/today_data.py` (add `PARTS`, `RECIPES`, `GROUP`; emit for the personal trip only), `trips/*.json` (regenerated)
- Test: `src/tests/test_group_data.py`

**Interfaces:**
- Produces in `trips/miras-aikosh.json`: `parts: [part]`, `recipes: [recipe without host_ref]`, `group: {url, anon} | null` (null until the owner gives them).

- [ ] **Step 1: Test**

```python
import json
from conftest import ROOT

T = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))


def test_parts_cover_known_stops_and_days():
    ids = {e["id"] for d in T["days"] for e in d["ev"]}
    assert [p["id"] for p in T["parts"]] == ["arrive", "fuji", "kyoto", "nagoya", "tokyo"]
    for p in T["parts"]:
        assert p["days"] and all(1 <= n <= 11 for n in p["days"])
        assert p["stops"] is None or set(p["stops"]) <= ids


def test_recipes_are_public_safe_and_complete():
    bks = {b["id"] for b in T["bookings"]}
    for r in T["recipes"]:
        assert r["bk"] in bks and r["url"].startswith("https://") and r["what"]
        assert "host_ref" not in r
    txt = json.dumps(T, ensure_ascii=False)
    assert "09A" not in txt and "09B" not in txt


def test_template_has_no_group_things():
    tpl = json.loads((ROOT / "trips" / "template.json").read_text(encoding="utf-8"))
    assert not tpl.get("parts") and not tpl.get("recipes") and not tpl.get("group")
```

- [ ] **Step 2: Run — fails** (`KeyError: 'parts'`).

- [ ] **Step 3: Add to `src/today_data.py`** (after `FLIGHTS`):

```python
# Parts of the trip people join as a whole (spec §5). stops=None → every stop of those days.
# Day 2 splits: Fuji until the Mishima bus (d2e0–d2e9) belongs to «fuji»; the Shinkansen and Kyoto check-in to «kyoto».
PARTS = [
    dict(id="arrive", title="Прилёт, Токио", days=[1], stops=None),
    dict(id="fuji", title="Фудзи / Кавагутико", days=[2], stops=[f"d2e{i}" for i in range(0, 10)]),
    dict(id="kyoto", title="Киото", days=[2, 3, 4], stops=["d2e10", "d2e11", "d2e12"] + ["d3e%d" % i for i in range(0, 30)] + ["d4e%d" % i for i in range(0, 30)]),
    dict(id="nagoya", title="Нагоя и дзюдо", days=[4, 5, 6], stops=None),
    dict(id="tokyo", title="Токио", days=[6, 7, 8, 9, 10, 11], stops=None),
]
# Buying recipes (spec appendix A). Hosts' own booking details (seats, numbers) are NOT here — only in Supabase.
RECIPES = [
    dict(bk="bus18", what="Автобус Keio, Busta Shinjuku → Kawaguchiko Sta., 18.10, 06:45", site="Highway Bus",
         url="https://www.highwaybus.com/", opens=None, opens_note="за месяц — уже открыты", buy_by="2026-10-10", price_pp=2200,
         tips="Выходить на Kawaguchiko Sta. — это не конечная. Утренние места уходят первыми."),
    dict(bk="bus_mishima", what="Автобус Fujikyu, Kawaguchiko Sta. → Mishima Sta., 18.10, 17:00 → 18:40", site="Fujikyu",
         url="https://bus.fujikyu.co.jp/en/highway/mishima/", opens=None, opens_note="проверить, нужна ли бронь", buy_by="2026-10-15", price_pp=2700,
         tips="От Oishi Park до станции — ретро-автобус ~25 мин."),
    dict(bk="shin18", what="Синкансэн Мисима → Киото, 18.10, после 19:00 (план 19:46)", site="Smart EX",
         url="https://smart-ex.jp/en/", opens=None, opens_note="обычно за месяц — проверить", buy_by="2026-10-15", price_pp=10500,
         tips="Место E — справа. Возьмите тот же поезд, что у хозяев."),
    dict(bk="shin20", what="Синкансэн Киото → Нагоя, 20.10, ~18:30", site="Smart EX",
         url="https://smart-ex.jp/en/", opens=None, opens_note="проверить", buy_by="2026-10-18", price_pp=5900,
         tips="Чемодан больше 160 см по сумме сторон — место с багажной зоной."),
    dict(bk="judo", what="Финалы пара-дзюдо PJU06, 21.10, 16:00, Aichi Budokan", site="Aichi-Nagoya 2026",
         url="https://lp-apg.tickets-aichi-nagoya2026.org/pdf/guide_ja-6.pdf", opens=None, opens_note="проверить", buy_by="2026-10-19", price_pp=2000,
         tips="Болеем за Казахстан."),
    dict(bk="shin22", what="Синкансэн Нагоя → Токио, 22.10, 18:00–19:00", site="Smart EX",
         url="https://smart-ex.jp/en/", opens=None, opens_note="проверить", buy_by="2026-10-20", price_pp=11300, tips=""),
    dict(bk="disney", what="Tokyo Disneyland, 24.10, билет на дату", site="Tokyo Disney Resort",
         url="https://www.tokyodisneyresort.jp/en/tdl/daily/calendar/20261024/", opens=None, opens_note="проверить", buy_by="2026-10-17", price_pp=12400,
         tips="Свою еду проносить нельзя; халяля почти нет."),
    dict(bk="sky", what="Shibuya Sky, 25.10, ~16:30 (закат ~16:50)", site="Shibuya Sky",
         url="https://www.shibuya-scramble-square.com/sky/ticket/", opens="2026-10-11T00:00+09:00",
         opens_note="11.10 00:00 по Японии = 10.10 20:00 по Алматы", buy_by="2026-10-11", price_pp=3400,
         tips="Слоты на закат уходят быстро."),
    dict(bk="teamlab", what="teamLab Borderless, 26.10, билет на время", site="teamLab",
         url="https://www.teamlab.art/e/tokyo/", opens=None, opens_note="проверить", buy_by="2026-10-20", price_pp=3600, tips=""),
]
GROUP = None   # {"url": "https://<project>.supabase.co", "anon": "<anon public key>"} — set when the owner creates the project
```

and in `trip(personal)`'s returned dict: `parts=PARTS if personal else [], recipes=RECIPES if personal else [], group=GROUP if personal else None`.

- [ ] **Step 4: Run** `cd src && python3 today_data.py && cd .. && .venv/bin/pytest src/tests/test_group_data.py -q` → PASS (if a `kyoto` stop id doesn't exist, the list filter in the test fails — build the kyoto list from actual ids instead: `[e ids of day 2 with index ≥ 10] + all ids of days 3 and 4 before the 18:30 train`; adjust `PARTS` so the test passes). Run the full suite: all green (`cleanTrip` passes unknown keys through).

- [ ] **Step 5: Commit** `git add src/today_data.py trips src/tests/test_group_data.py && git commit -m "Group: trip parts and buying recipes in the trip data"`

### Task 4: Pure model — who is in, personal schedule, tasks, link sites

**Files:**
- Create: `src/today/group/model.js`
- Modify: `src/tests/conftest.py` (`core()` exposes `window.Group` when `group/model.js` is loaded)
- Test: `src/tests/test_group_model.py`

**Interfaces:**
- Produces `Group` (pure, no DOM, no storage):
  - `Group.effective(state, memberId) -> Set<stopId>` — stops of the group plan the member is in.
  - `Group.personalTrip(plan, state, memberId) -> trip` — same shape as the plan (days → ev), each ev gets `from: 'group'|'mine'`, `sharedBy` (author name for joined shared own stops), `who: [memberId]` (group stops: members in); days keep `n, date, label, sun, wcity`.
  - `Group.overlaps(dayEv) -> [[idA, idB]]` — pairs whose `[s, e)` intersect (minutes, same day).
  - `Group.tasks(plan, state, memberId) -> [{ref, kind: 'recipe'|'mine'|'task', title, recipe|task, done, dropped}]` sorted: open sales and buy_by soonest first, then opens soonest, then the rest; done last.
  - `Group.siteOf(url) -> {site, host} | null` — null unless `https:`.

- [ ] **Step 1: Tests** (`src/tests/test_group_model.py`)

```python
import json
from conftest import ROOT

TRIP = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
S, H = "s-1", "h-1"


def state(**kw):
    base = {"me": {"id": S, "role": "guest"}, "members": [{"id": H, "name": "Мирас", "role": "host"}, {"id": S, "name": "Сания", "role": "guest"}],
            "parts": TRIP["parts"], "joins": [], "recipes": TRIP["recipes"], "tasks": [], "my_stops": [], "my_bookings": [],
            "task_state": [], "attachments": []}
    base.update(kw); return base


def ev(pg, js):
    return pg.evaluate(f"(() => {{ const P = {json.dumps(TRIP)}; {js} }})()")


def test_part_join_with_opt_out_and_specific_rule_wins(core):
    pg = core(("core.js", "group/model.js"))
    st = state(joins=[{"member": S, "scope": "part", "ref": "fuji", "mode": "in"},
                      {"member": S, "scope": "stop", "ref": "d2e5", "mode": "out"},
                      {"member": S, "scope": "day", "ref": "3", "mode": "in"},
                      {"member": S, "scope": "stop", "ref": "d3e1", "mode": "out"}])
    got = set(ev(pg, f"return [...Group.effective({json.dumps(st)}, '{S}')];"))
    assert "d2e3" in got and "d2e5" not in got and "d2e10" not in got
    assert "d3e0" in got and "d3e1" not in got
    hosts = set(ev(pg, f"return [...Group.effective({json.dumps(state())}, '{H}')];"))
    assert len(hosts) == sum(len(d["ev"]) for d in TRIP["days"])       # hosts are in everything


def test_personal_trip_merges_own_and_shared_stops(core):
    pg = core(("core.js", "group/model.js"))
    st = state(joins=[{"member": S, "scope": "part", "ref": "fuji", "mode": "in"},
                      {"member": S, "scope": "mine", "ref": "m-h1", "mode": "in"}],
               my_stops=[{"id": "m-1", "member": S, "day": 3, "ev": {"s": "10:00", "e": "12:00", "t": "Осака: Dotonbori"}, "shared": False},
                         {"id": "m-h1", "member": H, "day": 3, "ev": {"s": "15:00", "e": "16:00", "t": "Кофе"}, "shared": True},
                         {"id": "m-h2", "member": H, "day": 3, "ev": {"s": "17:00", "e": "18:00", "t": "Не мой"}, "shared": True}])
    t = ev(pg, f"return Group.personalTrip(P, {json.dumps(st)}, '{S}');")
    d2 = next(d for d in t["days"] if d["n"] == 2); d3 = next(d for d in t["days"] if d["n"] == 3)
    assert [e["id"] for e in d2["ev"]][:2] == ["d2e0", "d2e1"] and all(e["from"] == "group" for e in d2["ev"])
    assert {e["t"] for e in d3["ev"]} == {"Осака: Dotonbori", "Кофе"}
    kofe = next(e for e in d3["ev"] if e["t"] == "Кофе")
    assert kofe["from"] == "mine" and kofe["sharedBy"] == "Мирас"
    assert [x["id"] for x in t["days"]] == [x["id"] for x in t["days"]] and len(t["days"]) == 11
    assert t["bookings"] == TRIP["bookings"]


def test_overlaps(core):
    pg = core(("core.js", "group/model.js"))
    pairs = pg.evaluate("Group.overlaps([{id:'a', s:'10:00', e:'12:00'}, {id:'b', s:'11:30', e:'13:00'}, {id:'c', s:'13:00', e:'14:00'}])")
    assert pairs == [["a", "b"]]


def test_tasks_follow_joins_and_sort_by_urgency(core):
    pg = core(("core.js", "group/model.js"))
    st = state(joins=[{"member": S, "scope": "part", "ref": "fuji", "mode": "in"}],
               task_state=[{"ref": "bk:bus_mishima", "done": True}],
               tasks=[{"id": "t-1", "title": "Оформить Suica", "due": "2026-10-10", "assignee": None}])
    ts = ev(pg, f"return Group.tasks(P, {json.dumps(st)}, '{S}', Date.UTC(2026, 8, 30));")
    refs = [t["ref"] for t in ts]
    assert "bk:bus18" in refs and "bk:bus_mishima" in refs and "bk:shin18" not in refs and "t:t-1" in refs
    assert refs[-1] == "bk:bus_mishima"                                   # done goes last
    # opting out of a stop drops its task unless already bought
    st2 = dict(st, joins=st["joins"] + [{"member": S, "scope": "stop", "ref": "d2e9", "mode": "out"}])
    ts2 = ev(pg, f"return Group.tasks(P, {json.dumps(st2)}, '{S}', Date.UTC(2026, 8, 30));")
    mish = next(t for t in ts2 if t["ref"] == "bk:bus_mishima")
    assert mish["dropped"] is True                                         # bought, then opted out → «сдайте билет»


def test_site_of_links(core):
    pg = core(("core.js", "group/model.js"))
    assert pg.evaluate("Group.siteOf('https://www.highwaybus.com/gp/reserve/x')")["site"] == "Highway Bus"
    assert pg.evaluate("Group.siteOf('https://secure.booking.com/confirmation.ru.html?x')")["site"] == "Booking.com"
    assert pg.evaluate("Group.siteOf('https://smart-ex.jp/en/')")["site"] == "Smart EX"
    assert pg.evaluate("Group.siteOf('https://example.org/a')")["site"] == "example.org"
    assert pg.evaluate("Group.siteOf('javascript:alert(1)')") is None
    assert pg.evaluate("Group.siteOf('http://booking.com')") is None
```

- [ ] **Step 2: Expose `Group` in the `core` fixture** — in `conftest.py` `core()`: add `+ ("\nwindow.Group = Group;" if "group/model.js" in mods else "")`.

- [ ] **Step 3: Run — fails** (file missing).

- [ ] **Step 4: Implement** (`src/today/group/model.js`)

```js
/* ---------- group model: who is in, the personal schedule, the tasks — pure, no DOM ---------- */
const Group = (() => {
  const toMin = Core.toMin;
  const byId = (xs, id) => (xs || []).find(x => x.id === id);
  const roleOf = (st, id) => (byId(st.members, id) || {}).role;
  const allStops = plan => plan.days.flatMap(d => d.ev.map(e => ({ id: e.id, n: d.n })));

  /* stop > day > part; nothing → out; hosts default in. Returns the Set of group stop ids the member is in. */
  function effectiveIn(plan, st, mid) {
    const js = (st.joins || []).filter(j => j.member === mid);
    const host = roleOf(st, mid) === 'host';
    const rule = (scope, ref) => { const j = js.find(x => x.scope === scope && x.ref === String(ref)); return j ? j.mode : null; };
    const partsOf = (id, n) => (st.parts || []).filter(p => p.stops ? p.stops.includes(id) : p.days.includes(n)).map(p => p.id);
    const partRule = (id, n) => { const ms = partsOf(id, n).map(p => rule('part', p)).filter(Boolean);
      return ms.includes('in') ? 'in' : ms.includes('out') ? 'out' : null; };
    const out = new Set();
    allStops(plan).forEach(({ id, n }) => {
      const m = rule('stop', id) || rule('day', n) || partRule(id, n) || (host ? 'in' : null);
      if (m === 'in') out.add(id);
    });
    return out;
  }

  function personalTrip(plan, st, mid) {
    const inSet = effectiveIn(plan, st, mid);
    const names = new Map((st.members || []).map(m => [m.id, m.name]));
    const who = id => (st.members || []).filter(m => effectiveIn(plan, st, m.id).has(id)).map(m => m.id);
    const joinedMine = new Set((st.joins || []).filter(j => j.member === mid && j.scope === 'mine' && j.mode === 'in').map(j => j.ref));
    const mine = (st.my_stops || []).filter(s => s.member === mid || (s.shared && joinedMine.has(s.id)));
    const days = plan.days.map(d => {
      const g = d.ev.filter(e => inSet.has(e.id)).map(e => ({ ...e, from: 'group', who: who(e.id) }));
      const m = mine.filter(s => s.day === d.n).map(s => ({ st: 'planned', cat: 'activity', ...s.ev, id: s.id, from: 'mine',
        sharedBy: s.member !== mid ? names.get(s.member) || '' : null, shared: !!s.shared }));
      const ev = [...g, ...m].sort((a, b) => (toMin(a.s) || 0) - (toMin(b.s) || 0));
      return { ...d, ev };
    });
    return { ...plan, days };
  }

  function overlaps(evs) {
    const iv = evs.map(e => { const s = toMin(e.s); let en = e.e ? toMin(e.e) : s + 15; if (en < s) en += 1440; return [e.id, s, en]; })
      .filter(x => Number.isFinite(x[1])).sort((a, b) => a[1] - b[1]);
    const out = [];
    for (let i = 0; i < iv.length; i++) for (let k = i + 1; k < iv.length && iv[k][1] < iv[i][2]; k++) out.push([iv[i][0], iv[k][0]]);
    return out;
  }

  function tasks(plan, st, mid, nowMs) {
    const inSet = effectiveIn(plan, st, mid);
    const done = new Map((st.task_state || []).map(t => [t.ref, !!t.done]));
    const bkStops = new Map();
    plan.days.forEach(d => d.ev.forEach(e => { if (e.bk) { if (!bkStops.has(e.bk)) bkStops.set(e.bk, []); bkStops.get(e.bk).push(e.id); } }));
    const out = [];
    (st.recipes || []).forEach(r => {
      const ids = bkStops.get(r.bk) || [];
      const going = ids.some(id => inSet.has(id)), ref = 'bk:' + r.bk, d = done.get(ref) || false;
      if (going || d) out.push({ ref, kind: 'recipe', title: r.what, recipe: r, done: d, dropped: !going && d });
    });
    (st.my_bookings || []).filter(b => b.member === mid).forEach(b => {
      const ref = 'mb:' + b.id; out.push({ ref, kind: 'mine', title: b.what || b.title || 'Моя бронь', recipe: b, done: done.get(ref) || false, dropped: false });
    });
    (st.tasks || []).filter(t => !t.assignee || t.assignee === mid).forEach(t => {
      const ref = 't:' + t.id; out.push({ ref, kind: 'task', title: t.title, task: t, done: done.get(ref) || false, dropped: false });
    });
    const at = x => { const v = x && Date.parse(x); return Number.isFinite(v) ? v : Infinity; };
    const rank = t => {
      if (t.done && !t.dropped) return [3, 0];
      const r = t.recipe || {}, opens = at(r.opens), by = at(r.buy_by || (t.task || {}).due);
      if (t.dropped) return [0, 0];
      if (opens <= nowMs || !Number.isFinite(opens)) return [1, by];
      return [2, opens];
    };
    return out.sort((a, b) => { const x = rank(a), y = rank(b); return x[0] - y[0] || x[1] - y[1]; });
  }

  const SITES = [[/(^|\.)highwaybus\.com$/, 'Highway Bus'], [/(^|\.)booking\.com$/, 'Booking.com'], [/(^|\.)smart-ex\.jp$/, 'Smart EX'],
                 [/(^|\.)tokyodisneyresort\.jp$/, 'Tokyo Disney Resort'], [/(^|\.)teamlab\.art$/, 'teamLab']];
  function siteOf(url) {
    if (!Core.safeUrl(url)) return null;
    let host; try { host = new URL(url).hostname.toLowerCase(); } catch (e) { return null; }
    const hit = SITES.find(([re]) => re.test(host));
    return { site: hit ? hit[1] : host.replace(/^www\./, ''), host };
  }

  return { effective: effectiveIn, personalTrip, overlaps, tasks, siteOf };
})();
```

`Group.effective` has the signature `(plan, st, memberId)`; the tests call it as `Group.effective(P, st, id)` — update the two calls in `test_part_join_with_opt_out_and_specific_rule_wins` accordingly (`Group.effective(P, ${st}, '${S}')`).

- [ ] **Step 5: Run** `.venv/bin/pytest src/tests/test_group_model.py -q` → PASS.
- [ ] **Step 6: Commit** `git add src/today/group/model.js src/tests/test_group_model.py src/tests/conftest.py && git commit -m "Group: pure model — participation, personal schedule, tasks, link sites"`

### Task 5: API client — session, RPCs, outbox, polling, cached state

**Files:**
- Create: `src/today/group/api.js`
- Modify: `src/build_guide.py` (module list; CSP `connect-src 'self' https://*.open-meteo.com https://*.supabase.co`), `src/tests/conftest.py` (`app(..., supabase=None)` → routes `https://*.supabase.co/**` to `supabase.route`)
- Test: `src/tests/test_group_api.py`

**Interfaces:**
- Consumes: `Core`, `T` (`T.group`, `T.id`), HTTP API (Task 1).
- Produces `Api`:
  - `Api.enabled() -> bool` — `T.group` has `url` and `anon`, and `T.id` is the trip in Supabase.
  - `Api.me() -> member|null`, `Api.state() -> state|null` (cached, `localStorage 'japan2026.group.v1'`), `Api.status() -> {online: bool, pending: int, at: ms|null, error: string|null}`
  - `Api.members() -> Promise<[member]>` for the login sheet — uses a public-safe RPC? No: before login the list comes from `state` cache or from `T.members` (names from the trip file: add `members: [{id, name}]` to the plan doc via seed) — simplest: login sheet reads names from `Api.state()` if cached, else from `T.memberNames` baked into `trips/miras-aikosh.json` by `seed_group.py`? Use: RPC `member_names(p_trip)` callable by any signed-in session, returning `[{id, name}]` only. **Add `member_names` to Task 1 fake and Task 2 SQL** (security definer, no `_me()` check, returns id+name of the trip's members).
  - `Api.login(memberId, pin) -> Promise<{ok, error}>` — signs up anonymously if no session, then `claim_member`.
  - `Api.logout()`
  - `Api.call(name, args, apply) -> void` — optimistic: `apply(state)` mutates the cached state now; pushes `{id, name, args}` to the outbox (`localStorage 'japan2026.outbox.v1'`); triggers `flush()`.
  - `Api.flush() -> Promise` — sends outbox in order; network error → stop and retry in 15 s; 401 → refresh token then retry once; refresh fails → `status.error = 'login'` (UI asks PIN again), keep outbox; 4xx business error → drop the item, `status.error = message`, then `refresh()`.
  - `Api.refresh() -> Promise<bool>` — `group_state`; replaces the cache; returns whether anything changed; fires `window` event `japan2026:group`.
  - Polling: every 30 s while visible, on `visibilitychange` visible and after a successful flush.
  - `Api.upload(path, blob) -> Promise<path>`, `Api.download(path) -> Promise<Blob>`.

- [ ] **Step 1: Tests** (`src/tests/test_group_api.py`) — uses the fake through Playwright routes and a trip with `group` pointing at `https://fake.supabase.co`:

```python
import json
from conftest import ROOT, until
from fake_supabase import FakeSupabase

OURS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
GROUPED = dict(OURS, group={"url": "https://fake.supabase.co", "anon": "anon-key"})


def phone(app, fake, **kw):
    return app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake, **kw)


def test_login_then_state_is_cached_and_survives_offline(app):
    fake = FakeSupabase.seeded()
    a = phone(app, fake)
    r = a.page.evaluate(f"Api.login('{fake.host_id}', '{fake.host_pin}')")
    assert r["ok"] and a.page.evaluate("Api.me().name") == "Мирас"
    fake.fail_network = True
    a.page.reload()
    until(a.page, "window.Api && Api.state() && Api.state().me.name === 'Мирас'")


def test_outbox_survives_reload_and_sends_once(app):
    fake = FakeSupabase.seeded()
    a = phone(app, fake)
    a.page.evaluate(f"Api.login('{fake.host_id}', '{fake.host_pin}')")
    fake.fail_network = True
    a.page.evaluate("Api.call('set_join', {p_scope: 'part', p_ref: 'fuji', p_mode: 'in'}, s => s.joins.push({member: Api.me().id, scope: 'part', ref: 'fuji', mode: 'in'}))")
    assert a.page.evaluate("Api.status().pending") == 1
    a.page.reload()
    assert a.page.evaluate("Api.status().pending") == 1
    fake.fail_network = False
    a.page.evaluate("Api.flush()")
    until(a.page, "Api.status().pending === 0")
    assert [j for j in fake.joins if j["ref"] == "fuji"] == [{"member": fake.host_id, "scope": "part", "ref": "fuji", "mode": "in"}]


def test_expired_token_is_refreshed_and_a_rejected_write_is_dropped(app):
    fake = FakeSupabase.seeded()
    a = phone(app, fake)
    a.page.evaluate(f"Api.login('{fake.host_id}', '{fake.host_pin}')")
    fake.tokens.clear()                                     # every access token now invalid; refresh token still works
    a.page.evaluate("Api.call('set_task_state', {p_ref: 'bk:bus18', p_done: true}, () => {})")
    until(a.page, "Api.status().pending === 0")
    assert (fake.host_id, "bk:bus18") in fake.task_state
    a.page.evaluate("Api.call('save_attachment', {p_a: {id: 'a-x', ref: 'bk:bus18', kind: 'link', url: 'http://x'}}, () => {})")
    until(a.page, "Api.status().pending === 0 && /https/.test(Api.status().error || '')")


def test_disabled_without_group_config(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})
    assert a.page.evaluate("Api.enabled()") is False
    assert a.errors == []
```

In `conftest.app` add parameter `supabase=None`: after creating the page, `if supabase: pg.route("https://*.supabase.co/**", supabase.route)`. Expose `window.Api = Api` from `boot.js` only when `location.protocol === 'file:' || location.hostname === '127.0.0.1'` (test hook; inert on Pages).

- [ ] **Step 2: Run — fails** (`Api` undefined).

- [ ] **Step 3: Implement** (`src/today/group/api.js`)

```js
/* ---------- group API: Supabase over plain fetch — anonymous session, RPCs, outbox, polling ---------- */
const Api = (() => {
  const SES = 'japan2026.session.v1', ST = 'japan2026.group.v1', OUT = 'japan2026.outbox.v1';
  const get = k => { try { return JSON.parse(localStorage.getItem(k) || 'null'); } catch (e) { return null; } };
  const put = (k, v) => { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  let session = get(SES), state = get(ST), outbox = get(OUT) || [], flushing = null, timer = null;
  const status = { online: true, pending: outbox.length, at: state ? state._at || null : null, error: null };

  const cfg = () => (T && T.group && /^https:\/\/[a-z0-9-]+\.supabase\.co$/.test(T.group.url || '') && T.group.anon) ? T.group : null;
  const enabled = () => !!cfg() && !!T.id;
  const emit = () => window.dispatchEvent(new Event('japan2026:group'));

  async function http(path, body, auth, method = 'POST', raw = false, ctype) {
    const c = cfg();
    const res = await fetch(c.url + path, { method, headers: { apikey: c.anon, Authorization: 'Bearer ' + (auth || c.anon),
      'Content-Type': ctype || 'application/json' }, body: raw ? body : body == null ? undefined : JSON.stringify(body) });
    status.online = true;
    if (raw && method === 'GET') { if (!res.ok) throw Object.assign(new Error('HTTP ' + res.status), { status: res.status }); return res.blob(); }
    const j = await res.json().catch(() => null);
    if (!res.ok) throw Object.assign(new Error((j && (j.message || j.msg)) || 'HTTP ' + res.status), { status: res.status, body: j });
    return j;
  }
  async function ensureSession() {
    if (session && session.access_token) return session;
    const s = await http('/auth/v1/signup', {});
    session = { access_token: s.access_token, refresh_token: s.refresh_token }; put(SES, session);
    return session;
  }
  async function refreshToken() {
    if (!session || !session.refresh_token) throw Object.assign(new Error('login'), { status: 401 });
    const s = await http('/auth/v1/token?grant_type=refresh_token', { refresh_token: session.refresh_token });
    session = { ...session, access_token: s.access_token, refresh_token: s.refresh_token || session.refresh_token }; put(SES, session);
  }
  async function rpc(name, args, retried) {
    await ensureSession();
    try { return await http('/rest/v1/rpc/' + name, args || {}, session.access_token); }
    catch (e) {
      if (e.status === 401 && !retried) { await refreshToken(); return rpc(name, args, true); }
      throw e;
    }
  }
  const netErr = e => !e.status;            // fetch threw: no signal / blocked

  async function login(memberId, pin) {
    try {
      const r = await rpc('claim_member', { p_member: memberId, p_pin: pin });
      if (r && r.error) return { ok: false, error: r.error };
      session = { ...session, member: r }; put(SES, session);
      await refresh();
      return { ok: true };
    } catch (e) { return { ok: false, error: netErr(e) ? 'Нет сети' : e.message }; }
  }
  function logout() { session = null; state = null; outbox = []; put(SES, null); put(ST, null); put(OUT, null); status.pending = 0; emit(); }
  async function memberNames() { return rpc('member_names', { p_trip: T.id }); }

  async function refresh() {
    if (!enabled() || !session || !session.member) return false;
    try {
      const s = await rpc('group_state', { p_trip: T.id });
      // keep optimistic changes that are still waiting in the outbox
      const pend = outbox.slice(); const was = JSON.stringify(state && { ...state, _at: 0 });
      state = s; pend.forEach(p => { if (APPLY[p.id]) try { APPLY[p.id](state); } catch (e) {} });
      state._at = Date.now(); put(ST, state); status.at = state._at; status.error = status.error === 'login' ? null : status.error;
      const changed = was !== JSON.stringify({ ...state, _at: 0 });
      emit(); return changed;
    } catch (e) {
      if (netErr(e)) status.online = false; else if (e.status === 401 || e.message === 'login') status.error = 'login'; else status.error = e.message;
      emit(); return false;
    }
  }

  const APPLY = {};                         // outbox item id → optimistic change, replayed over refreshed state (this page load only)
  function call(name, args, apply) {
    const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
    if (state && apply) { try { apply(state); } catch (e) {} put(ST, state); APPLY[id] = apply; }
    outbox.push({ id, name, args }); put(OUT, outbox); status.pending = outbox.length; emit();
    flush();
  }
  function flush() {
    if (flushing || !outbox.length || !enabled()) return flushing || Promise.resolve();
    flushing = (async () => {
      while (outbox.length) {
        const it = outbox[0];
        try { await rpc(it.name, it.args); }
        catch (e) {
          if (netErr(e)) { status.online = false; setTimeout(flush, 15000); break; }
          if (e.status === 401 || e.message === 'login') { status.error = 'login'; break; }
          status.error = e.message;                        // rejected by the server: drop it, the refresh shows the truth
        }
        outbox.shift(); delete APPLY[it.id]; put(OUT, outbox); status.pending = outbox.length;
      }
      flushing = null; emit();
      if (!outbox.length) await refresh();
    })();
    return flushing;
  }
  function poll() {
    clearInterval(timer);
    timer = setInterval(() => { if (!document.hidden && session && session.member) { flush(); refresh(); } }, 30000);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden && enabled() && session && session.member) { flush(); refresh(); } });
  window.addEventListener('online', () => flush());

  async function upload(path, blob) {
    await ensureSession();
    await http('/storage/v1/object/tickets/' + path.split('/').map(encodeURIComponent).join('/'), blob, session.access_token, 'POST', true, blob.type || 'application/octet-stream');
    return path;
  }
  async function download(path) {
    await ensureSession();
    return http('/storage/v1/object/authenticated/tickets/' + path.split('/').map(encodeURIComponent).join('/'), null, session.access_token, 'GET', true);
  }

  if (enabled() && session && session.member) { poll(); setTimeout(() => { flush(); refresh(); }, 0); }
  return { enabled, me: () => (session && session.member) || null, state: () => state, status: () => ({ ...status }),
           login: (m, p) => login(m, p).then(r => { if (r.ok) poll(); return r; }), logout, memberNames, refresh, call, flush, upload, download };
})();
```

Add `member_names` to the fake (`rpc_member_names(self, token, p_trip)`: requires a valid token only; returns `[{id, name}]`) and to the SQL (security definer; `auth.uid() is not null`; `select jsonb_agg(jsonb_build_object('id', id, 'name', name)) from members where trip = p_trip`), add it to `RPCS` in `test_group_sql.py` and to the `grant` line.

- [ ] **Step 4: Run** `.venv/bin/pytest src/tests/test_group_api.py src/tests/test_group_contract.py src/tests/test_group_sql.py -q` → PASS; full suite green.
- [ ] **Step 5: Commit** `git commit -am "Group: Supabase client over fetch with an offline outbox and polling"` (add new files explicitly).

### Task 6: Login sheet and ⚙ group section

**Files:**
- Create: `src/today/group/ui_login.js`
- Modify: `src/today/ui/settings.js` (insert `groupSettingsHTML()` + `wireGroupSettings(m)` at the top of the sheet), `src/today/boot.js` (first-open prompt), `src/today/components.css`
- Test: `src/tests/test_group_login.py`

**Interfaces:**
- Consumes: `Api.memberNames/login/logout/me/state/status/call/refresh`, `sheet`, `closeSheet`, `icon`, `esc`.
- Produces: `openLogin()`; `groupSettingsHTML() -> html`; `wireGroupSettings(sheetEl)`; boot shows `openLogin()` once when `Api.enabled() && !Api.me()` and `localStorage 'japan2026.loginasked.v1'` is empty.

- [ ] **Step 1: Tests**

```python
import json
from conftest import ROOT, until
from fake_supabase import FakeSupabase
from test_group_api import GROUPED


def test_first_open_asks_who_you_are_then_pin(app):
    fake = FakeSupabase.seeded()
    san = fake._add("Сания", "guest")
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake)
    s = a.page.locator("#tcSheet")
    s.wait_for(state="visible")
    assert "Кто вы?" in s.inner_text() and "Сания" in s.inner_text()
    for b in s.locator("button").all():
        assert b.bounding_box()["height"] >= 44
    s.locator(f"[data-member='{san}']").click()
    a.page.fill("#grPin", "4821")                          # 4 digits submit by themselves
    until(a.page, "Api.me() && Api.me().name === 'Сания'")
    assert not s.is_visible()
    a.page.click("#tcGear")
    assert "Вы вошли как Сания" in a.page.inner_text("#tcSheet")


def test_just_look_skips_and_is_not_asked_again(app):
    fake = FakeSupabase.seeded()
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake)
    a.page.click("#grJustLook")
    a.page.reload()
    a.page.wait_for_selector(".tc-tab")
    assert not a.page.locator("#tcSheet").is_visible()


def test_wrong_pin_message_and_host_adds_member_and_resets_pin(app):
    fake = FakeSupabase.seeded()
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake)
    a.page.locator(f"[data-member='{fake.host_id}']").click()
    a.page.fill("#grPin", "0000")
    until(a.page, "/Неверный PIN/.test(document.getElementById('grMsg').textContent)")
    a.page.fill("#grPin", fake.host_pin)
    until(a.page, "Api.me() && Api.me().role === 'host'")
    a.page.click("#tcGear")
    a.page.fill("#grNewName", "Шахи")
    a.page.click("#grAdd")
    until(a.page, "Api.state().members.some(m => m.name === 'Шахи')")
    assert any(m["name"] == "Шахи" for m in fake.members.values())
```

- [ ] **Step 2: Run — fails.**
- [ ] **Step 3: Implement** `ui_login.js`:

```js
/* ---------- «Кто вы?» + PIN; the group part of ⚙ ---------- */
const LOGIN_ASKED = 'japan2026.loginasked.v1';
const PIN_ERR = { 'wrong PIN': 'Неверный PIN', 'locked, try later': 'Слишком много попыток — подождите 15 минут', 'Нет сети': 'Нет сети — попробуйте позже' };

async function openLogin() {
  try { localStorage.setItem(LOGIN_ASKED, '1'); } catch (e) {}
  sheet('Кто вы?', `<p class="tc-sub">Выберите себя — дальше PIN из 4 цифр. В первый раз вы его придумываете.</p>
    <div class="tc-group" id="grNames"><p class="tc-empty">Загружаю…</p></div>
    <button type="button" class="tc-btn wide" id="grJustLook">Просто посмотреть</button>`, async m => {
    m.querySelector('#grJustLook').addEventListener('click', closeSheet);
    let names = [];
    try { names = await Api.memberNames(); } catch (e) { names = ((Api.state() || {}).members || []); }
    const box = m.querySelector('#grNames');
    if (!names.length) { box.innerHTML = '<p class="tc-empty">Нет сети — войдите позже.</p>'; return; }
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
      pin.value = pin.value.replace(/\D/g, '').slice(0, 4);
      if (pin.value.length < 4) return;
      pin.disabled = true;
      const r = await Api.login(id, pin.value);
      pin.disabled = false;
      if (r.ok) { closeSheet(); renderShell(); return; }
      msg.textContent = PIN_ERR[r.error] || r.error; pin.value = ''; pin.focus();
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
        ${x.id !== me.id ? `<button type="button" class="tc-btn" data-reset="${esc(x.id)}">Сбросить PIN</button>` : ''}</div>`).join('')}</div>
      <div class="tc-form2">${fld('grNewName', 'Новый участник', '', 'text', 'maxlength="40"')}<button type="button" class="tc-btn primary" id="grAdd">${icon('plus')}Добавить</button></div>
      <p class="tc-foot">Если приложение долго не открывали, бесплатный Supabase «засыпает»: зайдите на supabase.com → проект → Restore.</p>` : ''}`;
}
function wireGroupSettings(m) {
  const on = (id, f) => { const b = m.querySelector(id); if (b) b.addEventListener('click', f); };
  on('#grLogin', () => { closeSheet(); openLogin(); });
  on('#grRelogin', () => { const me = Api.me(); Api.logout(); openPin(me.id, me.name); });
  on('#grLogout', () => twoTap(m.querySelector('#grLogout'), 'Точно выйти?', () => { Api.logout(); closeSheet(); renderShell(); }));
  on('#grAdd', () => {
    const name = m.querySelector('#grNewName').value.trim(); if (!name) return;
    Api.call('add_member', { p_name: name, p_role: 'guest' }, s => s.members.push({ id: 'pending-' + name, name, role: 'guest' }));
    closeSheet(); openSettings();
  });
  m.querySelectorAll('[data-reset]').forEach(b => b.addEventListener('click', () => twoTap(b, 'Точно?', () => {
    Api.call('reset_pin', { p_member: b.dataset.reset }); b.textContent = 'PIN сброшен';
  })));
}
```

In `settings.js` `openSettings`: prepend `${groupSettingsHTML()}` to the body and call `wireGroupSettings(m)` first in the ready callback. In `boot.js` after the first render: `if (Api.enabled() && !Api.me()) { let asked = null; try { asked = localStorage.getItem(LOGIN_ASKED); } catch (e) {} if (!asked) openLogin(); }`. Re-render on `japan2026:group`: `window.addEventListener('japan2026:group', () => { if (!document.getElementById('tcSheet') || document.getElementById('tcSheet').hidden) renderShell(); });`.

- [ ] **Step 4: Run** tests → PASS; full suite green.
- [ ] **Step 5: Commit** `git commit -m "Group: «Кто вы?» + PIN login and the group section in ⚙"` (add files).

### Task 7: Personal schedule and joining on «День»

**Files:**
- Create: `src/today/group/ui_join.js`
- Modify: `src/today/store.js` (`TV()`), `src/today/ui/shell.js`, `src/today/ui/now.js`, `src/today/ui/day.js`, `src/today/ui/stats.js` (use `TV()` for days), `src/today/ui/settings.js` (`openEditor` saves own stops / plan via Api), `src/today/components.css`
- Test: `src/tests/test_group_join.py`

**Interfaces:**
- Consumes: `Group.personalTrip/effective/overlaps`, `Api.*`.
- Produces:
  - `store.js`: `let VIEW_MODE = 'mine'` (persisted in `S.viewMode`); `TV() -> trip` = `Group.personalTrip(planDoc(), Api.state(), Api.me().id)` when logged in and `S.viewMode !== 'group'`, else `planDoc()`; `planDoc()` = `Api.state().plan.doc` (cleaned by `Core.cleanTrip`) when logged in, else `T`.
  - Every render path reads days from `TV().days` instead of `T.days` (shell `ctx`, `segmentsHTML`, `titleHTML`, now.js tomorrow/preview, day.js strip/swipe, stats bars, store `liveDayN`/`clock` prev-day). `bookingById` keeps using `planDoc().bookings`.
  - `joinBarHTML(x) -> html` (above the list on «День»): «Мой план / План группы» segmented control `#grView`; in group view, part chip(s) `[data-part]` with member initials and «Я с вами: <part>» `#grJoinPart`; in my view with no stops: «Свободный день» card with «＋ Пункт» and «Группа в этот день: …» hint.
  - Stop sheet additions via `stopJoinHTML(day, e)`: group stop → «Я еду» / «Без меня» (`[data-join=in|out]`), avatars; own stop → «Показать группе» switch `#grShare`; someone's shared stop → «Присоединиться» `[data-joinmine]`.
  - `openPart(partId)` sheet: days, stops, members going, «Я с вами на всю часть» / «Не еду».
  - Editor: saving a stop with `from === 'mine'` or adding in «Мой план» → `Api.call('save_my_stop', {p_stop}, apply)`; host editing a group stop in «План группы» → `Api.call('save_plan', {p_doc, p_version}, apply)`; a guest cannot open the editor on group stops.

- [ ] **Step 1: Tests** (multi-phone: two `app()` calls sharing one `FakeSupabase`)

```python
from conftest import until
from fake_supabase import FakeSupabase
from test_group_api import GROUPED


def logged(app, fake, member, pin, **kw):
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24", **kw.pop("state", {})}, supabase=fake, **kw)
    a.page.evaluate("localStorage.setItem('japan2026.loginasked.v1', '1')")
    assert a.page.evaluate(f"Api.login('{member}', '{pin}')")["ok"]
    a.page.evaluate("renderShell()")
    return a


def test_guest_joins_fuji_and_her_day_is_her_schedule(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='day']")
    assert "Свободный день" in g.page.inner_text("#todayBody")        # nothing joined yet
    g.page.click("#grView [data-view='group']")
    g.page.click("#grJoinPart")                                      # «Я с вами: Фудзи / Кавагутико»
    g.page.click("#grView [data-view='mine']")
    items = g.page.locator(".tc-item")
    assert items.count() == 10 and "Oishi Park" in g.page.inner_text("#tcList")
    assert "Мисима → Киото" not in g.page.inner_text("#tcList")
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.click(".tc-tab[data-tab='day']")
    h.page.click("#grView [data-view='group']")
    until(h.page, "document.querySelector('[data-part=\"fuji\"]').textContent.includes('С')")


def test_opt_out_of_the_boat_and_own_stop_on_a_free_day(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = logged(app, fake, san, "4821")
    g.page.evaluate("Api.call('set_join', {p_scope:'part', p_ref:'fuji', p_mode:'in'}, s => s.joins.push({member: Api.me().id, scope:'part', ref:'fuji', mode:'in'}))")
    g.page.click(".tc-tab[data-tab='day']")
    g.page.locator(".tc-item", has_text="Катер").locator(".tc-open").click()
    g.page.click("#tcSheet [data-join='out']")
    assert "Катер" not in g.page.inner_text("#tcList")
    g.page.click(".tc-daypick >> nth=2")                              # 19.10 — not with the group
    g.page.click("#tcAdd")
    g.page.fill("#edT", "Осака: Dotonbori"); g.page.fill("#edS", "10:00"); g.page.fill("#edE", "14:00")
    g.page.click("#edSave")
    assert "Осака: Dotonbori" in g.page.inner_text("#tcList")
    until(g.page, "Api.status().pending === 0")
    assert any(s["ev"]["t"] == "Осака: Dotonbori" and not s["shared"] for s in fake.my_stops.values())


def test_shared_own_stop_can_be_joined_by_another(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest"); am = fake._add("Аманжан", "guest")
    fake.my_stops["m-dt"] = {"id": "m-dt", "member": san, "day": 3, "ev": {"s": "10:00", "e": "14:00", "t": "Осака: Dotonbori"}, "shared": True}
    b = logged(app, fake, am, "1357")
    b.page.click(".tc-tab[data-tab='day']")
    b.page.click(".tc-daypick >> nth=2")
    b.page.click("#grView [data-view='group']")
    b.page.locator(".tc-item", has_text="Dotonbori").locator(".tc-open").click()
    assert "Сания" in b.page.inner_text("#tcSheet")
    b.page.click("#tcSheet [data-joinmine]")
    b.page.click("#grView [data-view='mine']")
    assert "Dotonbori" in b.page.inner_text("#tcList")


def test_host_moves_a_stop_and_the_guest_sees_it(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.click(".tc-tab[data-tab='day']")
    h.page.click("#grView [data-view='group']")
    h.page.locator(".tc-item", has_text="Oishi Park").locator(".tc-open").click()
    h.page.click("#tcSheet [data-edit]")
    h.page.fill("#edS", "13:30"); h.page.click("#edSave")
    until(h.page, "Api.status().pending === 0")
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='day']")
    assert "13:30" in g.page.locator(".tc-item", has_text="Oishi Park").inner_text()


def test_overlap_warning(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    fake.my_stops["m-x"] = {"id": "m-x", "member": san, "day": 2, "ev": {"s": "13:30", "e": "14:30", "t": "Свой обед"}, "shared": False}
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='day']")
    assert "пересекается" in g.page.locator(".tc-item", has_text="Свой обед").inner_text()


def test_unshared_stop_disappears_for_others_without_errors(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest"); am = fake._add("Аманжан", "guest")
    fake.my_stops["m-dt"] = {"id": "m-dt", "member": san, "day": 3, "ev": {"s": "10:00", "e": "14:00", "t": "Осака: Dotonbori"}, "shared": True}
    fake.joins.append({"member": am, "scope": "mine", "ref": "m-dt", "mode": "in"})
    b = logged(app, fake, am, "1357")
    b.page.click(".tc-tab[data-tab='day']"); b.page.click(".tc-daypick >> nth=2")
    assert "Dotonbori" in b.page.inner_text("#tcList")
    fake.my_stops["m-dt"]["shared"] = False
    b.page.evaluate("Api.refresh().then(() => renderShell())")
    until(b.page, "!document.getElementById('tcList') || !document.getElementById('tcList').textContent.includes('Dotonbori')")
    assert b.errors == []


def test_not_logged_in_is_unchanged(app):
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=FakeSupabase.seeded())
    a.page.click("#grJustLook")
    a.page.click(".tc-tab[data-tab='day']")
    assert a.page.locator("#grView").count() == 0 and a.page.locator(".tc-item").count() == 13
```

- [ ] **Step 2: Run — fails.**
- [ ] **Step 3: Implement.** `store.js`:

```js
/* the trip on screen: the group plan, or my own schedule (joined group stops + my stops) when logged in */
const planDoc = () => { const s = typeof Api !== 'undefined' && Api.me() && Api.state(); const d = s && s.plan && Core.cleanTrip(s.plan.doc); return d || T; };
function TV() {
  const s = typeof Api !== 'undefined' && Api.me() && Api.state();
  if (!s || S.viewMode === 'group') return planDoc();
  return Group.personalTrip(planDoc(), s, Api.me().id);
}
```

Replace `T.days` → `TV().days` in: `shell.js` (`ctx`, `segmentsHTML`, `titleHTML`), `now.js` (lines with `T.days.find` and the preview select), `day.js` (`dayStrip`, swipe), `stats.js` (`N`, `budgets`), `store.js` (`liveDayN`, `clock`). `bookingById` → `planDoc().bookings`. `ctx()` computes `const V = TV()` once and uses `V.days`.

`ui_join.js`:

```js
/* ---------- joining on «День»: my plan / group plan, parts, «Я еду / Без меня», own stops ---------- */
const initials = ids => { const s = Api.state(); return (ids || []).map(id => ((s.members.find(m => m.id === id) || {}).name || '?')[0]).join(' '); };
const setJoin = (scope, ref, mode) => Api.call('set_join', { p_scope: scope, p_ref: String(ref), p_mode: mode }, s => {
  const me = Api.me().id; s.joins = s.joins.filter(j => !(j.member === me && j.scope === scope && j.ref === String(ref)));
  if (mode !== 'none') s.joins.push({ member: me, scope, ref: String(ref), mode });
});
function joinBarHTML(x) {
  if (!Api.me()) return '';
  const s = Api.state(), group = S.viewMode === 'group';
  const parts = (s.parts || []).filter(p => p.days.includes(x.day.n));
  const inSet = Group.effective(planDoc(), s, Api.me().id);
  const partIn = p => (s.joins || []).some(j => j.member === Api.me().id && j.scope === 'part' && j.ref === p.id && j.mode === 'in');
  const who = p => s.members.filter(m => (s.joins || []).some(j => j.member === m.id && j.scope === 'part' && j.ref === p.id && j.mode === 'in') || m.role === 'host').map(m => m.id);
  let html = `<div class="tc-seg3s two" id="grView" role="radiogroup" aria-label="Чей план">
    <button type="button" data-view="mine" aria-pressed="${!group}">Мой план</button><button type="button" data-view="group" aria-pressed="${group}">План группы</button></div>`;
  if (group) html += parts.map(p => `<div class="tc-card tc-part"><button type="button" class="tc-part-chip" data-part="${esc(p.id)}">
      <b>${esc(p.title)}</b><small>едут: ${esc(initials(who(p)))}</small></button>
      ${Api.me().role === 'host' ? '' : partIn(p) ? `<button type="button" class="tc-btn" data-partjoin="${esc(p.id)}" data-mode="none">Не еду</button>`
        : `<button type="button" class="tc-btn primary" id="grJoinPart" data-partjoin="${esc(p.id)}" data-mode="in">Я с вами: ${esc(p.title)}</button>`}</div>`).join('');
  else if (!x.evs.length) html += `<div class="tc-card"><b>Свободный день — спланируйте сами</b>
      ${parts.length ? `<span class="tc-sub">Группа в этот день: ${esc(parts.map(p => p.title).join(', '))} — «План группы», чтобы присоединиться.</span>` : ''}</div>`;
  return html;
}
function wireJoinBar(root) {
  if (!Api.me()) return;
  root.querySelectorAll('#grView [data-view]').forEach(b => b.addEventListener('click', () => { S.viewMode = b.dataset.view; save(); renderShell(); }));
  root.querySelectorAll('[data-partjoin]').forEach(b => b.addEventListener('click', () => { setJoin('part', b.dataset.partjoin, b.dataset.mode); renderShell(); }));
  root.querySelectorAll('[data-part]').forEach(b => b.addEventListener('click', () => openPart(b.dataset.part)));
}
function openPart(id) {
  const s = Api.state(), p = s.parts.find(x => x.id === id); if (!p) return;
  const going = s.members.filter(m => m.role === 'host' || s.joins.some(j => j.member === m.id && j.scope === 'part' && j.ref === id && j.mode === 'in'));
  sheet(p.title, `<p class="tc-sub">Дни: ${p.days.map(n => Core.ddmmyyyy(dateOf(planDoc().days.find(d => d.n === n) || { n })).slice(0, 5)).join(', ')}</p>
    <p class="tc-sub">Едут: ${esc(going.map(m => m.name).join(', '))}</p>
    ${Api.me().role === 'host' ? '' : `<button type="button" class="tc-btn primary wide" data-in>Я с вами на всю часть</button><button type="button" class="tc-btn wide" data-none>Не еду</button>`}`, m => {
    const b1 = m.querySelector('[data-in]'), b2 = m.querySelector('[data-none]');
    if (b1) b1.addEventListener('click', () => { setJoin('part', id, 'in'); closeSheet(); renderShell(); });
    if (b2) b2.addEventListener('click', () => { setJoin('part', id, 'none'); closeSheet(); renderShell(); });
  });
}
/* extra block for the stop sheet */
function stopJoinHTML(day, e) {
  if (!Api.me()) return '';
  const me = Api.me().id, s = Api.state();
  if (e.from === 'mine' || String(e.id).startsWith('m-')) {
    const own = (s.my_stops.find(x => x.id === e.id) || {}).member === me;
    if (own) return `<label class="tc-act"><span>Показать группе<small>другие смогут присоединиться</small></span><input type="checkbox" switch id="grShare"${e.shared ? ' checked' : ''}></label>`;
    const author = (s.members.find(m => m.id === (s.my_stops.find(x => x.id === e.id) || {}).member) || {}).name || '';
    const joined = s.joins.some(j => j.member === me && j.scope === 'mine' && j.ref === e.id && j.mode === 'in');
    return `<p class="tc-sub">Планирует ${esc(author)}</p><button type="button" class="tc-btn ${joined ? '' : 'primary'} wide" data-joinmine="${joined ? 'none' : 'in'}">${joined ? 'Не пойду' : 'Присоединиться'}</button>`;
  }
  const going = Group.effective(planDoc(), s, me).has(e.id);
  const who = s.members.filter(m => Group.effective(planDoc(), s, m.id).has(e.id)).map(m => m.name);
  return `<p class="tc-sub">Идут: ${esc(who.join(', ') || '—')}</p>
    <div class="tc-actions two"><button type="button" class="tc-btn ${going ? '' : 'primary'}" data-join="in">Я еду</button>
      <button type="button" class="tc-btn ${going ? 'primary' : ''}" data-join="out">Без меня</button></div>`;
}
function wireStopJoin(m, day, e) {
  if (!Api.me()) return;
  m.querySelectorAll('[data-join]').forEach(b => b.addEventListener('click', () => { setJoin('stop', e.id, b.dataset.join); closeSheet(); renderShell(); }));
  const jm = m.querySelector('[data-joinmine]'); if (jm) jm.addEventListener('click', () => { setJoin('mine', e.id, jm.dataset.joinmine); closeSheet(); renderShell(); });
  const sh = m.querySelector('#grShare'); if (sh) sh.addEventListener('change', () => {
    const st = Api.state().my_stops.find(x => x.id === e.id); if (!st) return;
    const next = { ...st, shared: sh.checked };
    Api.call('save_my_stop', { p_stop: next }, s => { const i = s.my_stops.findIndex(x => x.id === e.id); if (i >= 0) s.my_stops[i] = next; });
  });
}
```

Wire into `day.js`: in `RENDER.day` insert `${joinBarHTML(x)}` after `dayStrip(x)` and call `wireJoinBar(root)`; in `itemRow` add `e.from === 'mine' ? '<span class="tc-st mine"><i></i>моё</span>' : ''` and, when `Api.me()`, compute `Group.overlaps(x.evs)` once in `RENDER.day` and show `<span class="tc-bad">пересекается с ${esc(other.t)}</span>` for items in a pair; in `openStop` append `${stopJoinHTML(day, e)}` before the actions and call `wireStopJoin(m, day, e)`. Guests: hide `[data-edit]` for `e.from === 'group'`.

`settings.js` `openEditor(day, id)`: when `Api.me()`:
- id starts with `m-` or (no id and `S.viewMode !== 'group'`) or the user is a guest → build `stop = {id: id || 'm-' + crypto.randomUUID(), day: day.n, ev: {t, s, e, st, cat, …}, shared: existing.shared || false}` and `Api.call('save_my_stop', {p_stop: stop}, s => upsert(s.my_stops, stop))`.
- host editing a group stop (or adding in «План группы») → take `doc = clone(Api.state().plan.doc)`, apply the edit to `doc.days[n].ev` exactly as today, then `Api.call('save_plan', {p_doc: doc, p_version: Api.state().plan.version}, s => { s.plan = {doc, version: s.plan.version + 1}; })`. A `plan version changed` error surfaces in ⚙ status and the next refresh shows the newer plan.
- Without `Api.me()` — unchanged (local trip copy).

- [ ] **Step 4: Run** `.venv/bin/pytest src/tests/test_group_join.py -q` → PASS, then the full suite (existing Day/Now/Stats tests must stay green: `TV()` equals `T` when not logged in).
- [ ] **Step 5: Commit** `git commit -m "Group: my schedule vs group plan, parts, joins and opt-outs, own stops on «День»"` (add files).

### Task 8: «Дела» — buying recipes, hosts' booking details, imported tasks

**Files:**
- Create: `src/today/group/ui_tasks.js`
- Modify: `src/today/ui/shell.js` (tab label «Дела»), `src/tests/test_shell.py` (expected labels), `src/today/ui/bookings.js` (render `tasksHTML()` above the bookings when logged in), `src/today/components.css`
- Test: `src/tests/test_group_tasks.py`

**Interfaces:**
- Consumes: `Group.tasks`, `Api.call/state/me`.
- Produces: `tasksHTML(nowMs) -> html` (sections «Мне купить», «Сделать»; each task `.tc-task[data-ref]` with recipe details, site button `a.tc-btn[href]`, «Куплено» switch `[data-done]`, «Прикрепить билет» `[data-attach-ref]` (Task 9 wires it), hosts see ✎ `[data-recipe]`); `wireTasks(root)`; `openRecipeEditor(bk)` (hosts: what, url, opens, opens_note, buy_by, price_pp, tips, **host_ref**); `openMyBooking(stopId)` (anyone: a booking for an own stop → `save_my_booking`); `importTasksSheet()` (hosts: paste JSON from the old tracker → `import_tasks`).

- [ ] **Step 1: Tests**

```python
import json
from conftest import until
from fake_supabase import FakeSupabase
from test_group_join import logged


def test_joining_fuji_gives_two_buying_tasks_with_recipes(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.recipes["bus18"]["host_ref"] = "рейс 1431, места рядом с нашими: 10A/10B свободны"
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821", now="2026-09-30T12:00:00+09:00")
    g.page.click(".tc-tab[data-tab='tix']")
    assert g.page.inner_text(".tc-tab[data-tab='tix']").strip() == "Дела"
    tasks = g.page.locator(".tc-task")
    refs = [t.get_attribute("data-ref") for t in tasks.all()]
    assert refs[:2] == ["bk:bus18", "bk:bus_mishima"] and "bk:shin18" not in refs
    first = tasks.first.inner_text()
    assert "Busta Shinjuku" in first and "¥2 200" in first.replace("\u00a0", " ") and "10A/10B" in first
    assert tasks.first.locator("a[href='https://www.highwaybus.com/']").count() == 1
    tasks.first.locator("[data-done]").click()
    until(g.page, "Api.status().pending === 0")
    assert fake.task_state[(san, "bk:bus18")]["done"] is True
    assert g.page.locator(".tc-task").last.get_attribute("data-ref") == "bk:bus18"   # done goes last


def test_sale_opening_is_shown_in_both_time_zones(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "tokyo", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='tix']")
    sky = g.page.locator(".tc-task[data-ref='bk:sky']").inner_text()
    assert "11.10 00:00 по Японии" in sky and "10.10 20:00 по Алматы" in sky


def test_host_edits_recipe_and_imports_old_tasks(app):
    fake = FakeSupabase.seeded()
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.click(".tc-tab[data-tab='tix']")
    h.page.locator(".tc-task[data-ref='bk:bus18'] [data-recipe]").click()
    h.page.fill("#rcHost", "рейс 1431, места 10A/10B рядом")
    h.page.click("#rcSave")
    until(h.page, "Api.status().pending === 0")
    assert "10A/10B" in fake.recipes["bus18"]["host_ref"]
    h.page.click("#tkImport")
    h.page.fill("#tkJson", json.dumps([{"title": "Оформить Suica в Wallet", "due": "2026-10-15"},
                                       {"title": "<img src=x onerror=window.__pwned=1>"}]))
    h.page.click("#tkImportGo")
    until(h.page, "Api.status().pending === 0")
    assert len(fake.tasks) == 2
    h.page.evaluate("Api.refresh()")
    until(h.page, "document.querySelectorAll('.tc-task[data-ref^=\"t:\"]').length === 2")
    assert h.page.evaluate("window.__pwned") is None
```

- [ ] **Step 2: Run — fails.**
- [ ] **Step 3: Implement.** Label: `TABS` entry `['tix', 'Дела']`; `test_shell.py` expects `["Сейчас", "День", "Дела", "Итоги", "Карта"]`. `ui_tasks.js`:

```js
/* ---------- «Дела»: what to buy (recipes), what to do (tasks) ---------- */
const almaty = iso => { const t = Date.parse(iso); if (!Number.isFinite(t)) return ''; const d = new Date(t + 5 * 3600e3), p = v => String(v).padStart(2, '0');
  return `${p(d.getUTCDate())}.${p(d.getUTCMonth() + 1)} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`; };
const japan = iso => { const t = Date.parse(iso); if (!Number.isFinite(t)) return ''; const d = new Date(t + 9 * 3600e3), p = v => String(v).padStart(2, '0');
  return `${p(d.getUTCDate())}.${p(d.getUTCMonth() + 1)} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`; };
function taskHTML(t, host) {
  const r = t.recipe || {}, k = t.task || {};
  const opens = r.opens ? `продажи: ${japan(r.opens)} по Японии = ${almaty(r.opens)} по Алматы` : r.opens_note ? `продажи: ${esc(r.opens_note)}` : '';
  const by = r.buy_by || k.due ? `купить до ${Core.ddmmyyyy(r.buy_by || k.due).slice(0, 5)}` : '';
  const url = Core.safeUrl(r.url || k.url);
  return `<div class="tc-card tc-task${t.done ? ' done' : ''}" data-ref="${esc(t.ref)}">
    <div class="tc-row"><b>${t.dropped ? 'Вы отписались — сдайте или перенесите билет: ' : ''}${esc(t.title)}</b>
      <label class="tc-check"><input type="checkbox" switch data-done="${esc(t.ref)}"${t.done ? ' checked' : ''} aria-label="${t.kind === 'task' ? 'Сделано' : 'Куплено'}"><span aria-hidden="true">${icon('check')}</span></label></div>
    ${[opens, by, r.price_pp ? money(r.price_pp) + ' на всех · ' + both(r.price_pp) + ' на человека' : ''].filter(Boolean).map(s => `<span class="tc-sub">${s}</span>`).join('')}
    ${r.tips || k.note ? `<p class="tc-notepara">${esc(r.tips || k.note)}</p>` : ''}
    ${r.host_ref ? `<p class="tc-note tc-hostref"><b>Бронь хозяев:</b> ${esc(r.host_ref)}</p>` : ''}
    <div class="tc-actions two">${url ? `<a class="tc-btn primary" href="${url}" target="_blank" rel="noopener">${icon('share')}${esc(r.site || Group.siteOf(url).site)}</a>` : ''}
      ${t.kind !== 'task' ? `<button type="button" class="tc-btn" data-attach-ref="${esc(t.ref)}">${icon('clip')}Билет</button>` : ''}
      ${host && t.kind === 'recipe' ? `<button type="button" class="tc-btn" data-recipe="${esc(r.bk)}">${icon('edit')}Рецепт</button>` : ''}</div>
  </div>`;
}
function tasksHTML(nowMs) {
  if (!Api.me()) return '';
  const all = Group.tasks(planDoc(), Api.state(), Api.me().id, nowMs), host = Api.me().role === 'host';
  const buy = all.filter(t => t.kind !== 'task'), todo = all.filter(t => t.kind === 'task');
  return `<section id="grTasks"><h2 class="tc-sech">Мне купить</h2>${buy.length ? buy.map(t => taskHTML(t, host)).join('') : '<p class="tc-empty">Присоединитесь к части поездки — здесь появятся билеты.</p>'}
    <h2 class="tc-sech">Сделать</h2>${todo.map(t => taskHTML(t, host)).join('') || '<p class="tc-empty">Пусто.</p>'}
    ${host ? '<button type="button" class="tc-btn wide" id="tkImport">Импорт задач из старого трекера</button>' : ''}</section>`;
}
function wireTasks(root) {
  if (!Api.me()) return;
  root.querySelectorAll('[data-done]').forEach(i => i.addEventListener('change', () => {
    const ref = i.dataset.done, done = i.checked;
    Api.call('set_task_state', { p_ref: ref, p_done: done }, s => { s.task_state = s.task_state.filter(x => x.ref !== ref).concat([{ ref, done }]); });
    renderShell();
  }));
  root.querySelectorAll('[data-recipe]').forEach(b => b.addEventListener('click', () => openRecipeEditor(b.dataset.recipe)));
  const im = root.querySelector('#tkImport'); if (im) im.addEventListener('click', importTasksSheet);
}
function openRecipeEditor(bk) {
  const r = { ...(Api.state().recipes.find(x => x.bk === bk) || { bk }) };
  sheet('Рецепт покупки', `<div class="tc-form">${fld('rcWhat', 'Что купить', r.what || '')}${fld('rcUrl', 'Сайт (https)', r.url || '', 'url')}
    ${fld('rcSite', 'Название сайта', r.site || '')}${fld('rcOpens', 'Продажи открываются (ISO, с поясом)', r.opens || '')}
    ${fld('rcOpensNote', 'Про продажи — текстом', r.opens_note || '')}${fld('rcBy', 'Купить до', r.buy_by || '', 'date')}
    ${fld('rcPrice', 'Цена на человека, ¥', r.price_pp ?? '', 'number', 'inputmode="numeric"')}</div>
    <label class="tc-f" for="rcTips"><span>Советы</span><textarea id="rcTips" rows="2">${esc(r.tips || '')}</textarea></label>
    <label class="tc-f" for="rcHost"><span>Наша бронь (видят только участники): рейс, места</span><textarea id="rcHost" rows="2">${esc(r.host_ref || '')}</textarea></label>
    <p class="tc-warn" id="rcMsg"></p><button type="button" class="tc-btn primary wide" id="rcSave">Сохранить</button>`, m => {
    m.querySelector('#rcSave').addEventListener('click', () => {
      const v = id => m.querySelector('#' + id).value.trim();
      if (v('rcUrl') && !Core.safeUrl(v('rcUrl'))) { m.querySelector('#rcMsg').textContent = 'Ссылка должна начинаться с https://'; return; }
      const next = { ...r, what: v('rcWhat'), url: v('rcUrl'), site: v('rcSite'), opens: v('rcOpens') || null, opens_note: v('rcOpensNote'),
        buy_by: v('rcBy') || null, price_pp: v('rcPrice') === '' ? null : +v('rcPrice'), tips: v('rcTips'), host_ref: v('rcHost') };
      Api.call('save_recipe', { p_r: next }, s => { s.recipes = s.recipes.filter(x => x.bk !== bk).concat([next]); });
      closeSheet(); renderShell();
    });
  });
}
function importTasksSheet() {
  sheet('Импорт задач', `<p class="tc-sub">Вставьте JSON-список задач: [{"title": "…", "due": "2026-10-15", "note": "…", "url": "https://…"}].</p>
    <label class="tc-f" for="tkJson"><span>JSON</span><textarea id="tkJson" rows="6" spellcheck="false"></textarea></label>
    <p class="tc-warn" id="tkMsg"></p><button type="button" class="tc-btn primary wide" id="tkImportGo">Импортировать</button>`, m => {
    m.querySelector('#tkImportGo').addEventListener('click', () => {
      let xs; try { xs = JSON.parse(m.querySelector('#tkJson').value); } catch (e) { m.querySelector('#tkMsg').textContent = 'Это не JSON.'; return; }
      xs = (Array.isArray(xs) ? xs : []).filter(t => t && String(t.title || '').trim()).map(t => ({ title: String(t.title).slice(0, 200),
        note: String(t.note || '').slice(0, 1000), due: /^\d{4}-\d{2}-\d{2}$/.test(t.due || '') ? t.due : null, url: Core.safeUrl(t.url) || null, assignee: null }));
      if (!xs.length) { m.querySelector('#tkMsg').textContent = 'Нет задач с названием.'; return; }
      Api.call('import_tasks', { p_tasks: xs }, null); closeSheet();
    });
  });
}
```

In `bookings.js` `RENDER.tix`: prepend `${tasksHTML(Date.now())}` inside `.tc-page` and call `wireTasks(root)`; when logged in, the existing «Сегодня/Вся поездка» bookings stay below as «Брони поездки».

Old tracker data: before Task 11 the executor exports the claude.ai tracker with the Artifact tool (`action: read_db`, url `https://claude.ai/artifact/Fefu1Uv2RvqppF1j8dpZpn`, collection `tasks`, `out_dir: survey/tracker`) and converts open items to the import JSON in `survey/tracker/import.json` (untracked); the host pastes it via «Импорт задач».

- [ ] **Step 4: Run** tests → PASS; full suite green (update `test_shell` labels).
- [ ] **Step 5: Commit** `git commit -m "Group: «Дела» with buying recipes, hosts' booking notes and imported tasks"` (add files).

### Task 9: Tickets as files or links — private or shared

**Files:**
- Create: `src/today/group/ui_attach.js`
- Modify: `src/today/ui/bookings.js` (booking rows get «Ссылка» next to «Файл»; show links), `src/today/store.js` (local links when not logged in: `localStorage 'japan2026.links.v1'` = `{bookingId: [{id, url, name, site}]}`), `src/today/components.css`
- Test: `src/tests/test_group_attach.py`

**Interfaces:**
- Consumes: `Group.siteOf`, `Api.call/upload/download/state/me`, existing `ticketPut/ticketGet`, `showTicket`.
- Produces: `openAttach(ref)` sheet: «Файл (PDF или картинка)» `#atFile`, «Ссылка» `#atUrl` + `#atAdd`, list of my attachments with «Показать группе» switches `[data-share]` (links: first switch-on shows a confirm block `#atWarn` with «Всё равно показать» `#atWarnGo`) and delete `[data-del]` (two taps), and «От группы» (shared attachments of others: open only). Opening: links → `window.open(url, '_blank', 'noopener')`; files → download blob (cache in IndexedDB under `att:<id>`) → existing full-screen ticket viewer.
  - Logged in: file → `Api.upload('<me>/<ref>/<id>.<ext>', blob)` then `save_attachment {id: 'a-<uuid>', ref, kind: 'file', path, name, site: '', shared: false}`; link → `save_attachment {kind: 'link', url, name: site, site}`.
  - Not logged in: file → existing IndexedDB ticket store (unchanged behaviour); link → `japan2026.links.v1`.

- [ ] **Step 1: Tests**

```python
import base64
from conftest import until
from fake_supabase import FakeSupabase
from test_group_join import logged

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==")
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def test_link_is_private_then_shared_with_a_warning(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='tix']")
    g.page.click(".tc-task[data-ref='bk:bus18'] [data-attach-ref]")
    g.page.fill("#atUrl", "https://www.highwaybus.com/gp/reserve/abc")
    g.page.click("#atAdd")
    assert "Highway Bus" in g.page.inner_text("#tcSheet")
    until(g.page, "Api.status().pending === 0")
    a = next(iter(fake.attachments.values()))
    assert a["kind"] == "link" and a["shared"] is False
    g.page.click("#tcSheet [data-share]")
    assert "работает как ключ" in g.page.inner_text("#atWarn")
    g.page.click("#atWarnGo")
    until(g.page, "Api.status().pending === 0")
    assert next(iter(fake.attachments.values()))["shared"] is True


def test_pdf_upload_private_and_host_sees_only_shared(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='tix']")
    g.page.click(".tc-task[data-ref='bk:bus18'] [data-attach-ref]")
    g.page.set_input_files("#atFile", files=[{"name": "ticket.pdf", "mimeType": "application/pdf", "buffer": PDF}])
    until(g.page, "Api.status().pending === 0 && Api.state().attachments.length === 1")
    path = next(iter(fake.attachments.values()))["path"]
    assert path.startswith(san + "/") and fake.files[path][0] == PDF
    h = logged(app, fake, fake.host_id, fake.host_pin)
    assert h.page.evaluate("Api.state().attachments.length") == 0


def test_bad_links_are_refused_and_offline_file_waits(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='tix']")
    g.page.click(".tc-task[data-ref='bk:bus18'] [data-attach-ref]")
    for bad in ("javascript:alert(1)", "http://booking.com/x", "https://x\" onclick=\"1"):
        g.page.fill("#atUrl", bad); g.page.click("#atAdd")
        assert "https://" in g.page.inner_text("#atMsg")


def test_not_logged_in_link_stays_on_the_phone(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})
    a.page.click(".tc-tab[data-tab='tix']")
    a.page.click("[data-link='bus18']")
    a.page.fill("#atUrl", "https://secure.booking.com/confirmation.html?x=1")
    a.page.click("#atAdd")
    assert "Booking.com" in a.page.inner_text("#tcSheet")
    assert "booking.com" in a.page.evaluate("localStorage.getItem('japan2026.links.v1')")
```

- [ ] **Step 2: Run — fails.**
- [ ] **Step 3: Implement** `ui_attach.js`:

```js
/* ---------- tickets: a file or a link; private unless shared ---------- */
const LINKS = 'japan2026.links.v1';
const localLinks = () => { try { return JSON.parse(localStorage.getItem(LINKS) || '{}') || {}; } catch (e) { return {}; } };
const putLocalLinks = v => { try { localStorage.setItem(LINKS, JSON.stringify(v)); } catch (e) {} };
const uid = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));

function openAttach(ref) {                     // ref: 'bk:<id>' | 'mb:<id>'
  const me = Api.me(), bk = ref.slice(3);
  const mine = me ? (Api.state().attachments || []).filter(a => a.ref === ref && a.member === me.id) : (localLinks()[bk] || []).map(l => ({ ...l, kind: 'link' }));
  const others = me ? (Api.state().attachments || []).filter(a => a.ref === ref && a.member !== me.id && a.shared) : [];
  const nameOf = id => ((Api.state() || { members: [] }).members.find(m => m.id === id) || {}).name || '';
  const row = (a, own) => `<div class="tc-flrow"><button type="button" class="tc-act" data-open="${esc(a.id)}">${icon(a.kind === 'link' ? 'share' : 'tix')}
      <span>${esc(a.kind === 'link' ? a.site || a.name : a.name)}<small>${own ? (a.shared ? 'видит группа' : 'только вы') : 'от ' + esc(nameOf(a.member))}</small></span></button>
      ${own && me ? `<label class="tc-share"><input type="checkbox" switch data-share="${esc(a.id)}"${a.shared ? ' checked' : ''} aria-label="Показать группе"></label>` : ''}
      ${own ? `<button type="button" class="tc-x" data-del="${esc(a.id)}" aria-label="Удалить">${icon('close')}</button>` : ''}</div>`;
  sheet('Билет', `
    ${mine.length ? `<div class="tc-group">${mine.map(a => row(a, true)).join('')}</div>` : ''}
    ${others.length ? `<span class="tc-sech">От группы</span><div class="tc-group">${others.map(a => row(a, false)).join('')}</div>` : ''}
    <div id="atWarn" class="tc-card tc-note" hidden><b>Ссылка на бронь часто работает как ключ</b>
      <span class="tc-sub">По ней можно открыть и иногда отменить бронь. Лучше покажите PDF без QR или данные текстом.</span>
      <button type="button" class="tc-btn" id="atWarnGo">Всё равно показать группе</button></div>
    <label class="tc-btn wide">${icon('clip')}Файл — PDF или картинка<input type="file" id="atFile" accept="image/*,application/pdf" hidden></label>
    <div class="tc-form2">${fld('atUrl', 'Или ссылка на бронь', '', 'url', 'placeholder="https://www.highwaybus.com/…"')}<button type="button" class="tc-btn primary" id="atAdd">${icon('plus')}Добавить</button></div>
    <p class="tc-warn" id="atMsg" role="status"></p>`, m => {
    const msg = t => { m.querySelector('#atMsg').textContent = t; };
    m.querySelector('#atAdd').addEventListener('click', () => {
      const url = m.querySelector('#atUrl').value.trim(), s = Group.siteOf(url);
      if (!s) { msg('Нужна ссылка, начинающаяся с https://'); return; }
      const a = { id: 'a-' + uid(), ref, kind: 'link', url, name: s.site, site: s.site, shared: false };
      if (me) Api.call('save_attachment', { p_a: a }, st => { st.attachments.push({ ...a, member: me.id }); });
      else { const all = localLinks(); all[bk] = (all[bk] || []).concat([{ id: a.id, url, name: s.site, site: s.site }]); putLocalLinks(all); }
      openAttach(ref); renderShell();
    });
    m.querySelector('#atFile').addEventListener('change', async e => {
      const f = e.target.files && e.target.files[0]; if (!f) return;
      if (!/^(image\/|application\/pdf$)/.test(f.type)) { msg('Только PDF или картинка.'); return; }
      if (!me) { await ticketPut(bk, f); await refreshTickets(); closeSheet(); renderShell(); return; }
      const id = 'a-' + uid(), path = `${me.id}/${ref.replace(':', '-')}/${id}.${f.type === 'application/pdf' ? 'pdf' : 'img'}`;
      try { await ticketPut('att:' + id, f); } catch (err) {}
      try { await Api.upload(path, f); } catch (err) { msg('Нет сети — файл сохранён на телефоне, отправьте позже.'); return; }
      const a = { id, ref, kind: 'file', path, name: f.name.slice(0, 80), site: '', shared: false };
      Api.call('save_attachment', { p_a: a }, st => { st.attachments.push({ ...a, member: me.id }); });
      openAttach(ref); renderShell();
    });
    let pending = null;
    m.querySelectorAll('[data-share]').forEach(sw => sw.addEventListener('change', () => {
      const a = Api.state().attachments.find(x => x.id === sw.dataset.share);
      if (sw.checked && a.kind === 'link' && !a.shared) { sw.checked = false; pending = a; m.querySelector('#atWarn').hidden = false; return; }
      const next = { ...a, shared: sw.checked }; Api.call('save_attachment', { p_a: next }, st => { Object.assign(st.attachments.find(x => x.id === a.id), next); });
    }));
    m.querySelector('#atWarnGo').addEventListener('click', () => {
      if (!pending) return; const next = { ...pending, shared: true };
      Api.call('save_attachment', { p_a: next }, st => { Object.assign(st.attachments.find(x => x.id === next.id), next); }); openAttach(ref);
    });
    m.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', () => twoTap(b, '?', () => {
      if (me) Api.call('delete_attachment', { p_id: b.dataset.del }, st => { st.attachments = st.attachments.filter(x => x.id !== b.dataset.del); });
      else { const all = localLinks(); all[bk] = (all[bk] || []).filter(x => x.id !== b.dataset.del); putLocalLinks(all); }
      openAttach(ref);
    })));
    m.querySelectorAll('[data-open]').forEach(b => b.addEventListener('click', async () => {
      const a = [...mine, ...others].find(x => x.id === b.dataset.open);
      if (a.kind === 'link') { const u = Core.safeUrl(a.url); if (u) window.open(u, '_blank', 'noopener'); return; }
      let rec = null; try { rec = await ticketGet('att:' + a.id); } catch (e) {}
      if (!rec) { try { const blob = await Api.download(a.path); await ticketPut('att:' + a.id, new File([blob], a.name, { type: blob.type })); } catch (e) { msg('Нет сети — файл ещё не на телефоне.'); return; } }
      closeSheet(); showTicket('att:' + a.id);
    }));
  });
}
function wireAttach(root) {
  root.querySelectorAll('[data-attach-ref]').forEach(b => b.addEventListener('click', () => openAttach(b.dataset.attachRef)));
  root.querySelectorAll('[data-link]').forEach(b => b.addEventListener('click', () => openAttach('bk:' + b.dataset.link)));
}
```

`bookings.js` `bkRow`: next to the «Файл»/«QR» control add `<button type="button" class="tc-file" data-link="${esc(b.id)}">${icon('share')}Ссылка</button>` and show saved links (logged-out: `localLinks()[b.id]`; logged-in: my + shared attachments for `bk:<id>`) as `a.tc-qr` buttons labelled by site. `RENDER.tix` calls `wireAttach(root)`. `showTicket(id)`: when `id` starts with `att:`, take the title from the attachment's booking.

- [ ] **Step 4: Run** tests → PASS; full suite green (old `test_bookings` untouched: no login).
- [ ] **Step 5: Commit** `git commit -m "Group: tickets as files or links, private unless shared, with a warning for booking links"` (add files).

### Task 10: CSP, docs, wiring checks

**Files:**
- Modify: `src/build_guide.py` (module list from «File Structure»; `connect-src 'self' https://*.open-meteo.com https://*.supabase.co`), `README.md` (section «Групповое планирование — настройка Supabase» with spec §13 steps and `python3 src/tests/group_contract.py <url> <anon> <host-id> <pin>`), `src/tests/test_trips.py` (CSP test: a fetch to `https://x.supabase.co` is allowed, to `https://example.com` blocked)
- Test: the CSP test addition

- [ ] **Step 1: Test** (append to `test_trips.py`):

```python
def test_csp_allows_supabase_only(app, site):
    a = app(state=NIGHT, url=site)
    a.page.evaluate("window.__csp = []; document.addEventListener('securitypolicyviolation', e => __csp.push(e.blockedURI))")
    a.page.route("https://x.supabase.co/**", lambda r: r.fulfill(status=200, body="{}", headers={"access-control-allow-origin": "*"}))
    a.page.evaluate("fetch('https://x.supabase.co/rest/v1/').catch(() => {}); fetch('https://example.com/').catch(() => {})")
    a.page.wait_for_timeout(300)
    blocked = a.page.evaluate("__csp")
    assert any("example.com" in b for b in blocked) and not any("supabase.co" in b for b in blocked)
```

- [ ] **Step 2: Run — fails** (supabase blocked).
- [ ] **Step 3: Update CSP and README; run the full suite and the map scripts** (`cd src && for t in test_v3 test_cluster test_kz test_overlap test_offline; do ../.venv/bin/python tests/$t.py; done`), remove screenshots they write into `src/`.
- [ ] **Step 4: Commit** `git commit -m "Group: allow Supabase in the CSP; setup guide"`.

### Task 11: Go live — project setup with the owner, contract run, reviews, publish

**Files:**
- Modify: `src/today_data.py` (`GROUP = {"url": ..., "anon": ...}` from the owner), `trips/*.json` (regenerated), `supabase/seed.sql` (regenerated), `index.html`
- Create: `survey/tracker/import.json` (untracked; from the old artifact)

- [ ] **Step 1:** Walk the owner through spec §13 (sign up — confirm no card; project `japan-2026`, region Tokyo; enable Anonymous sign-ins; SQL Editor: run `supabase/migrations/001_group.sql`, then `supabase/seed.sql`).
- [ ] **Step 2:** Owner opens the app, «Кто вы?» → Мирас → sets PIN (first claim sets it). Get Мирас's member id from the SQL editor: `select id, name from members;`.
- [ ] **Step 3:** Run the contract against the real project: `python3 src/tests/group_contract.py <url> <anon> <mirasId> <pin>` → `contract ok: True`. It creates a test guest «Сания» — delete test rows after: `delete from members where name = 'Сания' and pin_hash is not null and id not in (...)` (or reset her PIN from ⚙ so the real Сания sets her own).
- [ ] **Step 4:** Put `GROUP` into `src/today_data.py`, regenerate trips and seed, rebuild, full suite, map scripts.
- [ ] **Step 5:** Export the old tracker (`Artifact` tool: `action: read_db`, url `https://claude.ai/artifact/Fefu1Uv2RvqppF1j8dpZpn`, `db_op: list`, collection `tasks`, `out_dir: survey/tracker`), convert open tasks to `survey/tracker/import.json`, give it to the owner to paste into «Импорт задач».
- [ ] **Step 6:** Security review and code review (two fresh agents, as before) over `git diff <stage-start>..HEAD` + the SQL; fix confirmed findings with tests.
- [ ] **Step 7:** Publish: `cp src/Japan_Guide_2026.html index.html`, commit, push, wait for Pages, open `?trip=miras-aikosh` over the live site as host and as a test guest (Playwright against the real Supabase), then delete the test guest.
- [ ] **Step 8:** Log this plan's tasks as done; give the owner: the link, how to add Сания/Аманжан/Шахи in ⚙, and what each of them does first.
