# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *
import json
import typing

# DaoStanding - one question any contract can ask AsVotedRegistry:
#
#   is_executing_as_voted(dao_id, at_time) -> bool
#
# True iff the DAO is listed and has NO FINAL DEVIATES ruling within the last
# WINDOW days before `at_time` (unix seconds; a write method passes its own
# transaction time). standing(dao_id, at_time) gives the same answer with its
# reasons. Open checks are reported but do not by themselves cost standing: a
# PROVISIONAL ruling can still be appealed. This contract judges nothing,
# holds nothing and has no owner; the registry address and the window are
# fixed at deployment.

VERSION = "1.0.0"
DAY = 86400


class DaoStanding(gl.contract.Contract):
    registry: Address
    window_days: u64

    def __init__(self, registry: str, window_days: int) -> None:
        r = str(registry).strip().lower()
        if len(r) != 42 or not r.startswith("0x"):
            raise gl.vm.UserError("registry must be a 0x address")
        w = int(window_days)
        if w < 1 or w > 3650:
            raise gl.vm.UserError("window_days must be 1..3650")
        self.registry = Address(r)
        self.window_days = u64(w)

    def _standing(self, dao_id: int, at_time: int) -> dict:
        try:
            raw = gl.contract.get_at(self.registry).view().get_standing(int(dao_id))
            s = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return {"ok": False, "found": False, "reasons": ["the registry could not be read"]}
        if not isinstance(s, dict) or not s.get("found"):
            return {"ok": False, "found": False, "reasons": ["no such DAO in the registry"]}
        reasons = []
        last = int(s.get("last_deviates_at", 0))
        cutoff = int(at_time) - int(self.window_days) * DAY
        if last > 0 and last >= cutoff:
            reasons.append("a FINAL DEVIATES ruling (check #" + str(int(s.get("last_deviates_check", 0))) +
                           ") within the last " + str(int(self.window_days)) + " days")
        s["ok"] = len(reasons) == 0
        s["reasons"] = reasons
        s["window_days"] = int(self.window_days)
        s["at_time"] = int(at_time)
        return s

    @gl.public.view
    def is_executing_as_voted(self, dao_id: int, at_time: int) -> bool:
        return bool(self._standing(dao_id, at_time).get("ok"))

    @gl.public.view
    def standing(self, dao_id: int, at_time: int) -> typing.Any:
        return self._standing(dao_id, at_time)

    @gl.public.view
    def get_config(self) -> typing.Any:
        return {"version": VERSION, "contract": "DaoStanding", "registry": self.registry.as_hex.lower(),
                "window_days": int(self.window_days)}
