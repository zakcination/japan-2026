"""RPC scenarios shared by the fake (pytest) and the real Supabase project (python3 src/tests/group_contract.py)."""
import json, os, re, sys, urllib.request

TRIP = os.environ.get("CONTRACT_TRIP", "miras-aikosh")   # on the real project: a throwaway trip, never ours


def ok(r):
    st, body = r
    assert st == 200, (st, body)
    assert not (isinstance(body, dict) and "error" in body), (st, body)
    return body


def err(r, code_part):
    st, body = r
    text = json.dumps(body, ensure_ascii=False)
    assert (st >= 400 or (isinstance(body, dict) and "error" in body)) and code_part in text, (st, body)


def run_all(c, host_id, host_pin):
    """host_id/host_pin: a seeded host (seed sets PIN for the first host via the owner)."""
    host = c.signup(); ok(c.rpc(host, "claim_member", {"p_member": host_id, "p_pin": host_pin}))
    s = ok(c.rpc(host, "group_state", {"p_trip": TRIP}))
    assert s["me"]["role"] == "host" and s["plan"]["version"] >= 1
    # a null PIN must never be treated as "the right PIN" for an already-PIN'd member
    w = c.signup(); err(c.rpc(w, "claim_member", {"p_member": host_id, "p_pin": None}), "PIN")
    # nulls must fail closed, not open: a null trip is not the caller's trip
    err(c.rpc(host, "group_state", {"p_trip": None}), "not a member")
    # host adds Saniya; she sets her PIN on first claim
    added = ok(c.rpc(host, "add_member", {"p_name": "Сания", "p_role": "guest"}))
    san, code = added["id"], added["code"]
    # the id alone is not enough for a first sign-in: the invite code from the host's link is needed
    q = c.signup(); err(c.rpc(q, "claim_member", {"p_member": san, "p_pin": "9999"}), "invite")
    g = c.signup(); ok(c.rpc(g, "claim_member", {"p_member": san, "p_pin": "4821", "p_code": code}))
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
    # a missing/null kind must not skip the https check either
    err(c.rpc(g, "save_attachment", {"p_a": {"id": "a-badkind", "ref": "bk:bus18", "url": "javascript:alert(3)", "name": "n"}}), "kind")
    # a shared 'link' attachment with a crafted path must not leak another member's private ticket
    trap = f"{host_id}/ticket.pdf"
    ok(c.rpc(g, "save_attachment", {"p_a": {"id": "a-leak", "ref": "bk:bus18", "kind": "link",
                                             "url": "https://example.com/x", "path": trap, "name": "leak", "shared": True}}))
    hs = ok(c.rpc(host, "group_state", {"p_trip": TRIP}))
    leaked = next(a for a in hs["attachments"] if a["id"] == "a-leak")
    assert "path" not in leaked, leaked
    if hasattr(c, "seed_file"):   # the fake only: prove the crafted attachment cannot actually fetch the file
        c.seed_file(trap)
        st, _ = c.download(g, trap)
        assert st >= 400
    # nulls must fail closed, not open: a null id is not a valid id
    err(c.rpc(g, "save_my_stop", {"p_stop": {"id": None, "day": 1, "ev": {"s": "09:00", "e": "10:00", "t": "x"}}}), "bad id")
    err(c.rpc(g, "save_my_booking", {"p_b": {"id": None}}), "bad id")
    # host resets the PIN; the old device keeps working, a new claim needs the new PIN
    code2 = ok(c.rpc(host, "reset_pin", {"p_member": san}))["code"]
    z = c.signup(); ok(c.rpc(z, "claim_member", {"p_member": san, "p_pin": "1111", "p_code": code2}))
    # first-claim takeover: a claimed guest's device cannot also claim a fresh guest slot
    guest2 = ok(c.rpc(host, "add_member", {"p_name": "Гость2", "p_role": "guest"}))["id"]
    err(c.rpc(g, "claim_member", {"p_member": guest2, "p_pin": "1234"}), "ask a host")
    # first-claim takeover: a PIN-less host can only get its PIN set by the owner, never by a claim
    host2 = ok(c.rpc(host, "add_member", {"p_name": "Хост2", "p_role": "host"}))["id"]
    v2 = c.signup(); err(c.rpc(v2, "claim_member", {"p_member": host2, "p_pin": "1234"}), "owner")
    # up to 3 devices per member: claiming from 4 sessions evicts the oldest
    first_host = host  # save the first session's token
    h2 = c.signup(); ok(c.rpc(h2, "claim_member", {"p_member": host_id, "p_pin": host_pin}))
    h3 = c.signup(); ok(c.rpc(h3, "claim_member", {"p_member": host_id, "p_pin": host_pin}))
    h4 = c.signup(); ok(c.rpc(h4, "claim_member", {"p_member": host_id, "p_pin": host_pin}))
    # first session is now evicted
    err(c.rpc(first_host, "group_state", {"p_trip": TRIP}), "not a member")
    # newest session works
    ok(c.rpc(h4, "group_state", {"p_trip": TRIP}))
    # re-assign host to a still-valid session for any future use
    host = h4
    # invite links for an added guest: a PIN-less guest gets a code, a guest with a PIN gets none; guests can't ask
    g3 = ok(c.rpc(host, "add_member", {"p_name": "Гость3", "p_role": "guest"}))
    assert ok(c.rpc(host, "invite_link", {"p_member": g3["id"]}))["code"] == g3["code"]
    assert ok(c.rpc(host, "invite_link", {"p_member": san}))["code"] is None
    err(c.rpc(z, "invite_link", {"p_member": g3["id"]}), "host")
    # activation funnel: members only, known events, each counted once per member; counts only, hosts only
    err(c.rpc(x, "track", {"p_event": "login"}), "not a member")
    err(c.rpc(z, "track", {"p_event": "hacked"}), "bad event")
    before = ok(c.rpc(host, "funnel_counts", {}))
    ok(c.rpc(z, "track", {"p_event": "login"})); ok(c.rpc(z, "track", {"p_event": "login"}))
    after = ok(c.rpc(host, "funnel_counts", {}))
    assert after["login"] - before["login"] <= 1 and after["login"] >= 1
    assert set(after) == {"members", "login", "installed", "joined", "bought"} and all(isinstance(v, int) for v in after.values())
    err(c.rpc(z, "funnel_counts", {}), "host")
    # stage 2 — proposals: a member proposes, sees only their own; a host sees them and decides; plan changes need the version
    err(c.rpc(x, "propose", {"p_kind": "comment", "p_ref": "d3e3", "p_day": None, "p_payload": {}, "p_note": "x"}), "not a member")
    err(c.rpc(z, "propose", {"p_kind": "hack", "p_ref": "d3e3", "p_day": None, "p_payload": {}, "p_note": ""}), "bad proposal")
    err(c.rpc(z, "propose", {"p_kind": "add", "p_ref": None, "p_day": 3, "p_payload": {}, "p_note": ""}), "bad proposal")
    pid = ok(c.rpc(z, "propose", {"p_kind": "time", "p_ref": "d3e3", "p_day": 3, "p_payload": {"s": "10:00", "e": "11:00"}, "p_note": "позже"}))
    cid = ok(c.rpc(z, "propose", {"p_kind": "comment", "p_ref": "d3e4", "p_day": 3, "p_payload": {}, "p_note": "можно без меня?"}))
    hs = ok(c.rpc(host, "group_state", {"p_trip": TRIP}))
    assert {p["id"] for p in hs["proposals"]} >= {pid, cid}
    err(c.rpc(z, "decide_proposal", {"p_id": pid, "p_accept": True, "p_doc": hs["plan"]["doc"], "p_version": hs["plan"]["version"]}), "host")
    err(c.rpc(host, "decide_proposal", {"p_id": pid, "p_accept": True, "p_doc": None, "p_version": None}), "plan needed")
    err(c.rpc(host, "decide_proposal", {"p_id": pid, "p_accept": True, "p_doc": hs["plan"]["doc"], "p_version": hs["plan"]["version"] - 1}), "version")
    v = ok(c.rpc(host, "decide_proposal", {"p_id": pid, "p_accept": True, "p_doc": hs["plan"]["doc"], "p_version": hs["plan"]["version"]}))
    assert v == hs["plan"]["version"] + 1
    err(c.rpc(host, "decide_proposal", {"p_id": pid, "p_accept": False, "p_doc": None, "p_version": None}), "no such proposal")   # decided once
    ok(c.rpc(host, "decide_proposal", {"p_id": cid, "p_accept": False, "p_doc": None, "p_version": None}))                         # a comment needs no plan
    mine = ok(c.rpc(z, "group_state", {"p_trip": TRIP}))["proposals"]
    assert {p["id"]: p["status"] for p in mine if p["id"] in (pid, cid)} == {pid: "accepted", cid: "rejected"}
    wid = ok(c.rpc(z, "propose", {"p_kind": "remove", "p_ref": "d3e2", "p_day": 3, "p_payload": {}, "p_note": ""}))
    err(c.rpc(host, "withdraw_proposal", {"p_id": wid}), "no such proposal")                       # only the author withdraws
    ok(c.rpc(z, "withdraw_proposal", {"p_id": wid}))
    # push subscriptions: https endpoints only, members only
    err(c.rpc(x, "save_push", {"p_sub": {"endpoint": "https://push.example/1", "keys": {}}}), "not a member")
    err(c.rpc(z, "save_push", {"p_sub": {"endpoint": "http://push.example/1", "keys": {}}}), "bad subscription")
    ok(c.rpc(z, "save_push", {"p_sub": {"endpoint": "https://push.example/contract-1", "keys": {"p256dh": "x", "auth": "y"}}}))
    ok(c.rpc(z, "delete_push", {"p_endpoint": "https://push.example/contract-1"}))
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
    if not re.fullmatch(r"[0-9a-f-]{36}", host_id):          # a name: look the id up
        c = Real(url, anon); t = c.signup()
        host_id = next(m["id"] for m in c.rpc(t, "member_names", {"p_trip": TRIP})[1] if m["name"] == host_id)
    print("contract ok:", run_all(Real(url, anon), host_id, pin))
