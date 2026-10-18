# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *
import json
import typing

# DaoStanding - one question any contract can ask AsVotedRegistry:
#
#   standing(dao_id, at_time) -> {"state": ..., "reasons": [...], ...}
#
# `at_time` is unix seconds (a write method passes its own transaction time).
# The state is the first of these that applies:
#
#   NO_COVERAGE        the DAO is not listed, or the registry cannot be read
#   DEVIATES           a FINAL DEVIATES ruling on an execution from the last
#                      WINDOW days
#   PENDING            a check of the DAO is open (a provisional ruling can
#                      still change)
#   NO_COVERAGE        the monitor has recorded no coverage heartbeat for the
#                      DAO (AsVotedRegistry.record_coverage)
#   STALE_MONITORING   the monitor's last heartbeat covers blocks older than
#                      STALE_S before at_time
#   NO_COVERAGE        no FINAL AS_VOTED ruling on an execution from the last
#                      WINDOW days: nothing has been verified, so nothing is
#                      vouched for
#   COMPLIANT          none of the above: at least one FINAL AS_VOTED in the
#                      window, no open check, no FINAL DEVIATES in the window,
#                      and fresh coverage
#
# is_executing_as_voted(dao_id, at_time) is True only for COMPLIANT. Absence
# of data is never a favourable answer. `reasons` lists every condition that
# fails, not only the first. This contract judges nothing, holds nothing and
# has no owner; the registry, the window, the monitor whose heartbeat counts
# and the staleness limit are fixed at deployment.

VERSION = "2.0.0"
DAY = 86400
COMPLIANT = "COMPLIANT"
NO_COVERAGE = "NO_COVERAGE"
PENDING = "PENDING"
DEVIATES = "DEVIATES"
STALE = "STALE_MONITORING"


class DaoStanding(gl.contract.Contract):
    registry: Address
    window_days: u64
    monitor: Address
    stale_s: u64

    def __init__(self, registry: str, window_days: int, monitor: str, stale_s: int) -> None:
        r = str(registry).strip().lower()
        if len(r) != 42 or not r.startswith("0x"):
            raise gl.vm.UserError("registry must be a 0x address")
        m = str(monitor).strip().lower()
        if len(m) != 42 or not m.startswith("0x"):
            raise gl.vm.UserError("monitor must be a 0x address")
        w = int(window_days)
        if w < 1 or w > 3650:
            raise gl.vm.UserError("window_days must be 1..3650")
        st = int(stale_s)
        if st < 60 or st > 30 * DAY:
            raise gl.vm.UserError("stale_s must be 60..2592000")
        self.registry = Address(r)
        self.window_days = u64(w)
        self.monitor = Address(m)
        self.stale_s = u64(st)

    def _standing(self, dao_id: int, at_time: int) -> dict:
        base = {"window_days": int(self.window_days), "at_time": int(at_time), "monitor": self.monitor.as_hex.lower(),
                "stale_s": int(self.stale_s)}
        reg = gl.contract.get_at(self.registry).view()
        try:
            raw = reg.get_standing(int(dao_id))
            s = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return {**base, "state": NO_COVERAGE, "ok": False, "found": False, "reasons": ["the registry could not be read"]}
        if not isinstance(s, dict) or not s.get("found"):
            return {**base, "state": NO_COVERAGE, "ok": False, "found": False, "reasons": ["no such DAO in the registry"]}
        try:
            cr = reg.get_coverage(int(dao_id), self.monitor.as_hex.lower())
            cov = json.loads(cr) if isinstance(cr, str) else cr
        except Exception:
            cov = None
        if not isinstance(cov, dict):
            cov = {"found": False}
        cutoff = int(at_time) - int(self.window_days) * DAY
        wd = str(int(self.window_days))
        failing = []
        last_dev = int(s.get("last_deviates_at", 0))
        if last_dev > 0 and last_dev >= cutoff:
            failing.append([DEVIATES, "a FINAL DEVIATES ruling (check #" + str(int(s.get("last_deviates_check", 0))) +
                            ") on an execution from the last " + wd + " days"])
        if int(s.get("open_checks", 0)) > 0:
            failing.append([PENDING, str(int(s.get("open_checks", 0))) + " check(s) of this DAO still open"])
        if not cov.get("found"):
            failing.append([NO_COVERAGE, "no coverage heartbeat from the monitor " + self.monitor.as_hex.lower()])
        elif int(at_time) - int(cov.get("block_time", 0)) > int(self.stale_s):
            failing.append([STALE, "the monitor's coverage ends at block " + str(int(cov.get("block", 0))) + " (time " +
                            str(int(cov.get("block_time", 0))) + "), more than " + str(int(self.stale_s)) + " s before"])
        last_as = int(s.get("last_as_voted_at", 0))
        if last_as <= 0 or last_as < cutoff:
            failing.append([NO_COVERAGE, "no FINAL AS_VOTED ruling on an execution from the last " + wd + " days"])
        state = failing[0][0] if len(failing) > 0 else COMPLIANT
        s.update(base)
        s["state"] = state
        s["ok"] = state == COMPLIANT
        s["reasons"] = [f[1] for f in failing]
        s["coverage"] = cov
        return s

    @gl.public.view
    def is_executing_as_voted(self, dao_id: int, at_time: int) -> bool:
        return self._standing(dao_id, at_time).get("state") == COMPLIANT

    @gl.public.view
    def standing(self, dao_id: int, at_time: int) -> typing.Any:
        return self._standing(dao_id, at_time)

    @gl.public.view
    def standing_state(self, dao_id: int, at_time: int) -> str:
        return str(self._standing(dao_id, at_time).get("state"))

    def _pair(self, space: str, chain: str, safe: str) -> int:
        try:
            return int(gl.contract.get_at(self.registry).view().get_dao_id(str(space), str(chain), str(safe)))
        except Exception:
            return 0

    @gl.public.view
    def is_executing_as_voted_for(self, space: str, chain: str, safe: str, at_time: int) -> bool:
        """Standing by identity: a DAO is the pair (Snapshot space, Safe on a
        chain). Another space listing the same Safe is another DAO."""
        d = self._pair(space, chain, safe)
        return d > 0 and self._standing(d, at_time).get("state") == COMPLIANT

    @gl.public.view
    def standing_for(self, space: str, chain: str, safe: str, at_time: int) -> typing.Any:
        d = self._pair(space, chain, safe)
        if d <= 0:
            return {"state": NO_COVERAGE, "ok": False, "found": False, "reasons": ["no such (space, chain, Safe) in the registry"]}
        return self._standing(d, at_time)

    @gl.public.view
    def get_config(self) -> typing.Any:
        return {"version": VERSION, "contract": "DaoStanding", "registry": self.registry.as_hex.lower(),
                "window_days": int(self.window_days), "monitor": self.monitor.as_hex.lower(), "stale_s": int(self.stale_s),
                "states": [COMPLIANT, NO_COVERAGE, PENDING, DEVIATES, STALE]}
