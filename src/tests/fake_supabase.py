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
        self.events = set()         # (member, event) — the activation funnel
        self.proposals, self.push_subs = [], {}
        self.expenses = {}          # id -> {member, e, deleted, updated_at}
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
        f.host_id = f._add("Мирас", "host"); f.host2_id = f._add("Айкош", "host")
        f.host_pin, f.host2_pin = "2468", "1357"
        f.members[f.host_id]["pin_hash"] = _h(f.host_pin)
        f.members[f.host2_id]["pin_hash"] = _h(f.host2_pin)  # hosts' PINs are set at setup; nothing is claimable by default
        return f

    def _add(self, name, role):
        i = str(uuid.uuid4())
        self.members[i] = {"id": i, "name": name, "role": role, "pin_hash": None, "fails": 0, "locked_until": 0,
                           "invite": uuid.uuid4().hex[:12] if role == "guest" else None}
        return i

    def invite(self, member_id):
        """The one-time code a guest's invite link carries (tests use it as a host would share it)."""
        return self.members[member_id]["invite"]

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
        return {"id": m["id"], "name": m["name"], "role": m["role"], "emoji": m.get("emoji"), "partner": m.get("partner")}

    # ---------- RPCs ----------
    def rpc(self, token, name, a):
        fn = getattr(self, "rpc_" + name, None)
        if not fn: raise RpcError(404, "no such function")
        return fn(token, **a)

    def rpc_claim_member(self, token, p_member, p_pin, p_code=None):
        uid = self.tokens.get(token)
        if not uid: raise RpcError(401, "JWT expired or invalid")
        m = self.members.get(p_member)
        if not m: raise RpcError(400, "no such member")
        if m["locked_until"] > self.clock(): raise RpcError(400, "locked, try later")
        if not (isinstance(p_pin, str) and len(p_pin) == 4 and p_pin.isdigit()): raise RpcError(400, "PIN must be 4 digits")
        if m["pin_hash"] is None:
            # first claim of a PIN-less member: only a guest slot, and only from a device not already
            # bound to someone else (a claimed member's device cannot also take over a fresh slot).
            if m["role"] != "guest": raise RpcError(400, "PIN is set by the owner")
            existing = self.devices.get(uid)
            if existing is not None and existing != p_member: raise RpcError(400, "ask a host")
            if not m["invite"] or p_code != m["invite"]:
                m["fails"] += 1
                if m["fails"] >= 5: m["locked_until"], m["fails"] = self.clock() + 900, 0
                raise RpcError(400, "invite needed")
            m["pin_hash"], m["invite"] = _h(p_pin), None
        elif m["pin_hash"] != _h(p_pin):
            m["fails"] += 1
            if m["fails"] >= 5: m["locked_until"], m["fails"] = self.clock() + 900, 0
            raise RpcError(400, "wrong PIN")
        m["fails"] = 0
        mine = [u for u, x in self.devices.items() if x == p_member]
        if len(mine) >= 3: del self.devices[mine[0]]
        self.devices[uid] = p_member
        return self._pub(m)

    def rpc_member_names(self, token, p_trip):
        if not self.tokens.get(token): raise RpcError(401, "JWT expired or invalid")
        if p_trip != TRIP: return []
        return [{"id": m["id"], "name": m["name"], "emoji": m.get("emoji")} for m in self.members.values()]

    def rpc_group_state(self, token, p_trip):
        m = self._me(token); me = m["id"]
        if p_trip != TRIP: raise RpcError(400, "not a member")   # nulls must fail closed, not open
        return copy.deepcopy({
            "me": self._pub(m), "trip": {"id": TRIP, "name": self.plan["doc"]["name"]}, "plan": self.plan,
            "members": [self._pub(x) for x in self.members.values()], "parts": self.parts, "joins": self.joins,
            "recipes": [r if m["role"] == "host" or True else r for r in self.recipes.values()],
            "tasks": [t for t in self.tasks if t.get("assignee") in (None, me)],
            "my_stops": [s for s in self.my_stops.values() if s["member"] == me or s["shared"]],
            "my_bookings": [b for b in self.my_bookings.values() if b["member"] == me],
            "task_state": [dict(ref=k[1], **v) for k, v in self.task_state.items() if k[0] == me],
            "attachments": [x for x in self.attachments.values() if x["member"] == me or x["shared"]],
            "expenses": [dict(x["e"], member=x["member"], deleted=x["deleted"]) for x in self.expenses.values()
                         if x["member"] == me or (x["member"] == m.get("partner") and self.members.get(m.get("partner"), {}).get("partner") == me)],
            "spend_totals": [{"member": k, "jpy": round(v)} for k, v in self._totals().items()],
            "proposals": [p for p in sorted(self.proposals, key=lambda p: p["at"], reverse=True)
                          if p["member"] == me or m["role"] == "host"],
            "now": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.clock()))})

    def rpc_set_join(self, token, p_scope, p_ref, p_mode):
        me = self._me(token)["id"]
        if p_scope not in ("part", "day", "stop", "mine", "follow") or p_mode not in ("in", "out", "none"): raise RpcError(400, "bad join")
        if p_scope == "follow":
            import re
            t, _, d = str(p_ref).partition(":")
            if (not re.fullmatch(r"[0-9a-f-]{36}", t) or (d and not re.fullmatch(r"\d{1,2}", d)) or ":" in d
                    or t == me or t not in self.members): raise RpcError(400, "bad join")
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
        if x.get("url") and not str(x["url"]).startswith("https://"): raise RpcError(400, "links must be https")
        if x["kind"] == "file":
            if not str(x.get("path", "")).startswith(me + "/"): raise RpcError(400, "not your file")
        else:
            x.pop("path", None)   # a link never stores a path: it cannot be used to point at another member's file
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
        i = self._add(str(p_name).strip()[:40], p_role)
        return {"id": i, "code": self.members[i]["invite"]}

    def rpc_reset_pin(self, token, p_member):
        self._me(token, need_host=True)
        m = self.members[p_member]; m["pin_hash"], m["fails"], m["locked_until"] = None, 0, 0
        m["invite"] = uuid.uuid4().hex[:12] if m["role"] == "guest" else None
        return {"code": m["invite"]}

    FACES = ['😀', '😄', '😎', '🤓', '🥳', '😇', '🤠', '🧐', '😺', '🐼', '🦊', '🐨', '🐯', '🦁', '🐸', '🐵', '🐻', '🐰', '🦄', '🐧', '🐱', '🐶', '🐹', '🐙']

    def _totals(self):
        t = {}
        for x in self.expenses.values():
            if not x["deleted"]: t[x["member"]] = t.get(x["member"], 0) + float(x["e"]["jpy"])
        return t

    def rpc_save_expense(self, token, p_e):
        import re
        me = self._me(token)["id"]
        if (not re.fullmatch(r"[0-9a-f-]{36}", str(p_e.get("id", ""))) or len(json.dumps(p_e)) > 4000
                or not re.fullmatch(r"\d+(\.\d+)?", str(p_e.get("jpy", ""))) or float(p_e["jpy"]) > 1e8
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(p_e.get("date", "")))): raise RpcError(400, "bad expense")
        was = self.expenses.get(p_e["id"])
        if was and was["member"] != me: raise RpcError(400, "not yours")
        up = str(p_e.get("updatedAt", ""))
        if was and was["updated_at"] > up: return True
        self.expenses[p_e["id"]] = {"member": me, "e": {k: v for k, v in p_e.items() if k not in ("member", "deleted")},
                                    "deleted": bool(p_e.get("deleted")), "updated_at": up}
        return True

    def rpc_set_partner(self, token, p_member):
        m = self._me(token)
        if p_member is not None and (p_member == m["id"] or p_member not in self.members): raise RpcError(400, "bad partner")
        m["partner"] = p_member; return True

    def rpc_set_emoji(self, token, p_emoji):
        m = self._me(token)
        if p_emoji is not None and p_emoji not in self.FACES: raise RpcError(400, "bad emoji")
        m["emoji"] = p_emoji; return True

    def rpc_invite_link(self, token, p_member):
        me = self._me(token, need_host=True)
        g = self.members.get(p_member)
        if not g: raise RpcError(400, "no such member")
        if g["role"] != "guest" or g["pin_hash"] is not None: return {"code": None}
        if not g["invite"]: g["invite"] = uuid.uuid4().hex[:12]
        return {"code": g["invite"]}

    def rpc_track(self, token, p_event):
        me = self._me(token)["id"]
        if p_event not in ("login", "installed", "joined", "bought"): raise RpcError(400, "bad event")
        self.events.add((me, p_event))
        return True

    def rpc_funnel_counts(self, token):
        self._me(token, need_host=True)
        n = lambda ev: sum(1 for m, e in self.events if e == ev and m in self.members)
        return {"members": len(self.members), "login": n("login"), "installed": n("installed"), "joined": n("joined"), "bought": n("bought")}

    def rpc_propose(self, token, p_kind, p_ref, p_day, p_payload, p_note):
        m = self._me(token)
        if p_kind not in ("time", "remove", "add", "comment"): raise RpcError(400, "bad proposal")
        if p_kind == "add" and (p_day is None or not (p_payload or {}).get("t")): raise RpcError(400, "bad proposal")
        if p_kind != "add" and not p_ref: raise RpcError(400, "bad proposal")
        if len(json.dumps(p_payload or {})) > 4000 or len(p_note or "") > 500: raise RpcError(400, "too long")
        if (sum(1 for p in self.proposals if p["member"] == m["id"] and p["status"] == "open") >= 20
                or sum(1 for p in self.proposals if p["member"] == m["id"] and p["at"] > time.time() - 3600) >= 30): raise RpcError(400, "too many open proposals")
        i = str(uuid.uuid4())
        self.proposals.append({"id": i, "member": m["id"], "kind": p_kind, "ref": p_ref or None, "day": p_day, "payload": p_payload or {},
                               "note": (p_note or "").strip() or None, "status": "open", "at": time.time()})
        return i

    def rpc_withdraw_proposal(self, token, p_id):
        me = self._me(token)["id"]
        p = next((p for p in self.proposals if p["id"] == p_id and p["member"] == me and p["status"] == "open"), None)
        if not p: raise RpcError(400, "no such proposal")
        p["status"] = "withdrawn"; return True

    def rpc_decide_proposal(self, token, p_id, p_accept, p_doc=None, p_version=None):
        self._me(token, need_host=True)
        p = next((p for p in self.proposals if p["id"] == p_id and p["status"] == "open"), None)
        if not p: raise RpcError(400, "no such proposal")
        if p_accept is None: raise RpcError(400, "bad decision")
        if p_accept and p["kind"] != "comment":
            if p_doc is None or p_version is None: raise RpcError(400, "plan needed")
            if p_version != self.plan["version"]: raise RpcError(400, "plan version changed")
            self.plan = {"doc": p_doc, "version": p_version + 1}
        p["status"] = "accepted" if p_accept else "rejected"
        return self.plan["version"]

    def rpc_save_push(self, token, p_sub):
        me = self._me(token)["id"]
        import re
        e, k = (p_sub or {}).get("endpoint") or "", (p_sub or {}).get("keys") or {}
        ok = re.match(r"^https://(fcm\.googleapis\.com|updates\.push\.services\.mozilla\.com|([a-z0-9-]+\.)*push\.apple\.com|([a-z0-9-]+\.)*notify\.windows\.com)/", e)
        if not ok or len(e) > 1000 or not k.get("p256dh") or not k.get("auth"): raise RpcError(400, "bad subscription")
        if e in self.push_subs and self.push_subs[e]["member"] != me: return True          # never take over someone else's
        self.push_subs[e] = {"member": me, "sub": p_sub}
        return True

    def rpc_delete_push(self, token, p_endpoint):
        me = self._me(token)["id"]
        if self.push_subs.get(p_endpoint, {}).get("member") == me: del self.push_subs[p_endpoint]
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

    def remove(self, token, paths):
        me = self._me(token)["id"]
        gone = [p for p in paths if p.startswith(me + "/") and self.files.pop(p, None) is not None]   # others' files: silently kept, like RLS
        return [{"name": p} for p in gone]

    def download(self, token, path):
        me = self._me(token)["id"]
        ok = path.startswith(me + "/") or any(
            x["shared"] and x.get("kind") == "file" and x.get("path") == path and path.startswith(x["member"] + "/")
            for x in self.attachments.values())
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

            def seed_file(self, path):
                """Test-only: plant a file directly in storage, as if its owner had already uploaded it."""
                f.files[path] = (b"x", "application/octet-stream")

            def download(self, token, path):
                try: f.download(token, path); return 200, {"ok": True}
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
            if path.rstrip("/") == "/storage/v1/object/tickets" and req.method == "DELETE":
                return send(200, self.remove(tok, json.loads(req.post_data or "{}").get("prefixes") or []))
            if path.startswith("/storage/v1/object/tickets/") and req.method == "POST":
                return send(200, self.upload(tok, path.split("/tickets/", 1)[1], req.post_data_buffer, req.headers.get("content-type", "")))
            return send(404, {"message": "not found"})
        except RpcError as e:
            return send(e.status, {"code": "P0001", "message": e.message})
