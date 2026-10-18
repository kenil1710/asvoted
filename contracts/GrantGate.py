# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *
from dataclasses import dataclass
import json
import typing

# GrantGate - a tiny consumer of DaoStanding. A DAO asks it to act (in a real
# integration: release a grant tranche, list a token, open a credit line);
# it carries the request out only if DaoStanding's state for the DAO at this
# transaction's time is COMPLIANT, and refuses with the state and
# DaoStanding's reasons otherwise (NO_COVERAGE, PENDING, DEVIATES,
# STALE_MONITORING, or an unreadable answer). Every request is logged either way. Nothing is written before
# DaoStanding has been read, and nothing after can revert. No value, no
# owner, no setter.

VERSION = "2.0.0"
MAX_PURPOSE = 200
MAX_PAGE = 50


def _epoch(value: typing.Any) -> int:
    if not isinstance(value, str) or len(value) < 19:
        return 0
    try:
        y = int(value[0:4])
        m = int(value[5:7])
        d = int(value[8:10])
        hh = int(value[11:13])
        mm = int(value[14:16])
        ss = int(value[17:19])
    except Exception:
        return 0
    y -= 1 if m <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return (era * 146097 + doe - 719468) * 86400 + hh * 3600 + mm * 60 + ss


@gl.storage.allow
@dataclass
class Request:
    request_id: u64
    sender: str
    dao_id: u64
    purpose: str
    carried_out: bool
    state: str
    reasons: str
    at: u64


class GrantGate(gl.contract.Contract):
    standing: Address
    n: u64
    carried: u64
    refused: u64
    requests: gl.storage.TreeMap[u64, Request]

    def __init__(self, standing: str) -> None:
        s = str(standing).strip().lower()
        if len(s) != 42 or not s.startswith("0x"):
            raise gl.vm.UserError("standing must be a 0x address")
        self.standing = Address(s)
        self.n = u64(0)
        self.carried = u64(0)
        self.refused = u64(0)

    @gl.public.write
    def request_grant(self, dao_id: int, purpose: str) -> typing.Any:
        now = _epoch(gl.message.raw.get("datetime", ""))
        try:
            raw = gl.contract.get_at(self.standing).view().standing(int(dao_id), now)
            s = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            s = {"state": "UNREADABLE", "reasons": ["DaoStanding could not be read"]}
        if not isinstance(s, dict):
            s = {"state": "UNREADABLE", "reasons": ["DaoStanding returned nothing usable"]}
        state = str(s.get("state") or "UNREADABLE")
        ok = state == "COMPLIANT" and now > 0
        reasons = [str(r) for r in (s.get("reasons") or [])]
        rid = int(self.n) + 1
        self.requests[u64(rid)] = Request(
            request_id=u64(rid), sender=gl.message.sender_address.as_hex.lower(), dao_id=u64(max(int(dao_id), 0)),
            purpose=" ".join(str(purpose).split())[:MAX_PURPOSE], carried_out=ok, state=state, reasons=json.dumps(reasons),
            at=u64(max(now, 0)))
        self.n = u64(rid)
        if ok:
            self.carried = u64(int(self.carried) + 1)
        else:
            self.refused = u64(int(self.refused) + 1)
        return {"request_id": rid, "carried_out": ok, "state": state, "reasons": reasons}

    @gl.public.view
    def get_requests(self, offset: int, limit: int) -> typing.Any:
        out = []
        i = int(self.n) - max(int(offset), 0)
        lim = min(max(int(limit), 0), MAX_PAGE)
        while i >= 1 and len(out) < lim:
            r = self.requests.get(u64(i))
            if r is not None:
                out.append({"request_id": int(r.request_id), "sender": r.sender, "dao_id": int(r.dao_id),
                            "purpose": r.purpose, "carried_out": bool(r.carried_out), "state": r.state,
                            "reasons": json.loads(r.reasons), "at": int(r.at)})
            i -= 1
        return {"total": int(self.n), "carried_out": int(self.carried), "refused": int(self.refused), "requests": out}

    @gl.public.view
    def get_config(self) -> typing.Any:
        return {"version": VERSION, "contract": "GrantGate", "standing": self.standing.as_hex.lower()}
