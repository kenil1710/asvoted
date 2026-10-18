"""Regression tests for the steward's requested changes (docs/STEWARD_RESPONSE.md).

    cd test && python3 -m unittest -q test_steward
"""
import copy
import unittest

import fixtures as F
import stub
import world
from fixtures import (RG, SAFE, USDC, ALICE, MALLORY, CONTROLLER, FILER, STRANGER, TARGET, DAY, STAKE, BOND, GEN,
                      MONITOR, STALE_S, FIN)
import json
from test_asvoted import Base, U, model_says
from test_attacks_r3 import QUOTE, ROUTER_BODY, DEPOSIT, APPEAL_TEXT


def clone_checks(D, n, open_at):
    """n checks on the registry (copies of one real filing), open where listed."""
    reg = D.w.instances[D.rg]
    tmpl = reg.checks[1]
    for i in range(1, n + 1):
        c = copy.deepcopy(tmpl)
        c.check_id = i
        c.status = "CONTESTABLE" if i in open_at else "FINAL"
        reg.checks[i] = c
    reg.n_checks = n


class TestPagination(Base):
    def test_open_checks_cursor_crosses_the_scan_cap_and_misses_nothing(self):
        D = self.D
        self.flow("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)))
        open_at = {2, 499, 500, 501, 777, 1000, 1001, 1234, 1300}
        clone_checks(D, 1300, open_at)
        seen, off, calls = [], 0, 0
        while True:
            p = D.view(D.rg, "get_open_checks", off, 50)
            calls += 1
            seen += [c["check_id"] for c in p["checks"]]
            self.assertGreater(p["next_offset"], off - 1)
            if p["done"]:
                break
            off = p["next_offset"]
        self.assertEqual(seen, sorted(open_at))
        self.assertEqual(calls, 3)  # 1300 records, at most SCAN_CAP=500 each

    def test_open_checks_pages_of_fifty(self):
        D = self.D
        self.flow("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)))
        open_at = set(range(100, 700, 3))  # 200 open, spread over 600 records
        clone_checks(D, 700, open_at)
        seen, off = [], 0
        while True:
            p = D.view(D.rg, "get_open_checks", off, 50)
            self.assertLessEqual(len(p["checks"]), 50)
            seen += [c["check_id"] for c in p["checks"]]
            if p["done"]:
                break
            off = p["next_offset"]
        self.assertEqual(seen, sorted(open_at))

    def test_get_daos_pages_past_fifty(self):
        D = self.D
        ids = [self.dao]
        for i in range(1, 64):
            ids.append(D.list_dao(safe=F.addr(0x9000 + i), space_id="dao%d.eth" % i, treasuries=[[F.addr(0x9000 + i), "1"]]))
        seen, off = [], 0
        while True:
            p = D.view(D.rg, "get_daos", off, 50)
            seen += [d["dao_id"] for d in p["daos"]]
            if p["done"]:
                break
            off = p["next_offset"]
        self.assertEqual(seen, ids)
        self.assertEqual(p["total"], 64)



class TestRoundTwoDeadline(Base):
    """An appeal turns AS_VOTED into DEVIATES; the DAO responds; the original
    appeal_deadline passes while the response is still open."""
    RESPONSE = "The deposit is the swap the proposal describes; the earlier panel misread the router call entirely."

    def setUp(self):
        super().setUp()
        self.D.call(self.D.rg, "claim_dao", self.dao, sender=CONTROLLER)
        self.D.call(self.D.rg, "pledge", self.dao, sender=CONTROLLER, value=10 * GEN)

    def _responded(self):
        D = self.D
        stub.MODEL.answer = model_says("AUTHORIZED", QUOTE)
        cid, j, c = self.judged(ROUTER_BODY, to=TARGET, data=DEPOSIT)
        self.assertEqual(c["ruling"], "AS_VOTED")
        a = D.call(D.rg, "appeal", cid, APPEAL_TEXT, 0, sender=STRANGER, value=BOND)
        appeal_deadline = a["appeal_deadline"]
        D.w.advance(10)
        stub.MODEL.answer = model_says("NOT_AUTHORIZED", QUOTE)
        D.judge_rule(cid)
        c = D.view(D.rg, "get_check", cid)
        self.assertEqual((c["status"], c["appeal_ruling"]), ("CONTESTABLE", "DEVIATES"))
        D.w.advance(60)                                           # inside the DAO's 90 s window
        r = D.call(D.rg, "appeal", cid, self.RESPONSE, 0, sender=CONTROLLER, value=BOND)
        self.assertEqual(r["round"], 2)
        c = D.view(D.rg, "get_check", cid)
        self.assertEqual((c["status"], c["round"], c["appeal_deadline"]), ("APPEALED", 2, appeal_deadline))
        self.assertGreater(c["resp_deadline"], appeal_deadline)
        return cid, appeal_deadline, c["resp_deadline"]

    def test_open_checks_expose_the_round_and_the_active_deadline(self):
        D = self.D
        cid, appeal_deadline, resp_deadline = self._responded()
        row = [x for x in D.view(D.rg, "get_open_checks", 0, 50)["checks"] if x["check_id"] == cid][0]
        self.assertEqual((row["round"], row["resp_deadline"], row["active_deadline"]), (2, resp_deadline, resp_deadline))
        self.assertEqual(row["appeal_deadline"], appeal_deadline)
        self.assertEqual(D.view(D.rg, "get_check", cid)["active_deadline"], resp_deadline)

    def test_response_judged_and_settled_after_the_original_appeal_deadline_no_premature_expire(self):
        D = self.D
        cid, appeal_deadline, resp_deadline = self._responded()
        D.w.set_time(appeal_deadline + 5)                         # the original appeal deadline has passed
        self.assertLess(D.w.now(), resp_deadline)
        with self.assertRaisesRegex(world.Reverted, "RESPONSE_JUDGEABLE_UNTIL_" + str(resp_deadline)):
            D.call(D.rg, "expire", cid)
        self.assertEqual(D.view(D.rg, "get_check", cid)["status"], "APPEALED")
        stub.MODEL.answer = model_says("AUTHORIZED", QUOTE)
        D.judge_rule(cid)
        c = D.view(D.rg, "get_check", cid)
        self.assertEqual((c["status"], c["final_verdict"], c["final_how"], c["resp_ruling"], c["slash"]),
                         ("FINAL", "AS_VOTED", "RESPONSE_RULED", "AS_VOTED", "0"))
        moves = [m[0] for m in c["settlement"]]
        self.assertIn("response bond refunded", moves)
        self.assertIn("appeal bond to the DAO pledge", moves)
        self.assertEqual(D.view(D.rg, "claimable_of", CONTROLLER)["claimable"], str(BOND))
        self.assertLedger()

    def test_response_unjudged_expires_only_after_its_own_deadline(self):
        D = self.D
        cid, appeal_deadline, resp_deadline = self._responded()
        D.w.set_time(resp_deadline)
        with self.assertRaisesRegex(world.Reverted, "RESPONSE_JUDGEABLE_UNTIL"):
            D.call(D.rg, "expire", cid)
        D.w.set_time(resp_deadline + 1)
        r = D.call(D.rg, "expire", cid)
        self.assertEqual((r["how"], r["final"]), ("RESPONSE_EXPIRED", "DEVIATES"))
        self.assertLedger()



class TestStandingStates(Base):
    """DaoStanding never answers favourably on absence of data; GrantGate
    carries a request out only on COMPLIANT."""

    def state(self, dao=None, at=None):
        D = self.D
        return D.view(D.st, "standing", dao or self.dao, D.w.now() if at is None else at)

    def gate(self, dao=None):
        D = self.D
        return D.call(D.gate, "request_grant", dao or self.dao, "tranche")

    def assertRefused(self, state, dao=None):
        r = self.gate(dao)
        self.assertEqual((r["carried_out"], r["state"]), (False, state), r)
        self.assertFalse(self.D.view(self.D.st, "is_executing_as_voted", dao or self.dao, self.D.w.now()))
        return r

    def test_no_coverage_unlisted_dao(self):
        st = self.state(dao=99)
        self.assertEqual((st["state"], st["found"], st["ok"]), ("NO_COVERAGE", False, False))
        self.assertRefused("NO_COVERAGE", dao=99)

    def test_no_coverage_listed_with_no_data_at_all(self):
        st = self.state()
        self.assertEqual(st["state"], "NO_COVERAGE")
        self.assertIn("no coverage heartbeat from the monitor " + MONITOR, st["reasons"])
        self.assertIn("no FINAL AS_VOTED ruling on an execution from the last 30 days", st["reasons"])
        self.assertRefused("NO_COVERAGE")

    def test_no_coverage_heartbeat_but_nothing_verified(self):
        self.D.heartbeat(self.dao)
        st = self.state()
        self.assertEqual((st["state"], st["reasons"]), ("NO_COVERAGE", ["no FINAL AS_VOTED ruling on an execution from the last 30 days"]))
        self.assertTrue(st["coverage"]["found"])
        self.assertRefused("NO_COVERAGE")

    def test_no_coverage_as_voted_but_no_heartbeat(self):
        D = self.D
        cid = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)))[0]
        D.w.advance(91)
        D.call(D.rg, "finalize", cid)
        st = self.state()
        self.assertEqual((st["state"], st["last_as_voted_check"]), ("NO_COVERAGE", cid))
        self.assertRefused("NO_COVERAGE")

    def test_only_the_monitors_heartbeat_counts(self):
        D = self.D
        cid = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)))[0]
        D.w.advance(91)
        D.call(D.rg, "finalize", cid)
        D.heartbeat(self.dao, sender=STRANGER)
        self.assertEqual(self.state()["state"], "NO_COVERAGE")
        self.assertTrue(D.view(D.rg, "get_coverage", self.dao, STRANGER)["found"])

    def test_pending_while_a_check_is_open(self):
        D = self.D
        self.make_compliant()
        self.flow("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)), exec_kw={"nonce": 31})
        st = self.state()
        self.assertEqual(st["state"], "PENDING")
        self.assertRefused("PENDING")

    def test_pending_during_a_provisional_ruling(self):
        D = self.D
        self.make_compliant()
        cid, j, c = self.judged("Send 7 USDC to " + F.BOB, to=USDC, data=F.transfer(F.BOB, U(7)), exec_kw={"nonce": 31})
        self.assertEqual((c["status"], c["ruling"]), ("CONTESTABLE", "AS_VOTED"), c["ruling_summary"])
        self.assertRefused("PENDING")

    def test_deviates_final_in_window(self):
        D = self.D
        self.make_compliant()
        cid = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(MALLORY, U(5)), exec_kw={"nonce": 31})[0]
        D.w.advance(91)
        D.call(D.rg, "finalize", cid)
        D.heartbeat(self.dao, block=FIN + 1)
        st = self.state()
        self.assertEqual(st["state"], "DEVIATES")
        self.assertIn("FINAL DEVIATES ruling (check #%d)" % cid, st["reasons"][0])
        self.assertRefused("DEVIATES")

    def test_stale_monitoring(self):
        D = self.D
        self.make_compliant()
        D.w.advance(STALE_S + 120)
        st = self.state()
        self.assertEqual(st["state"], "STALE_MONITORING")
        self.assertRefused("STALE_MONITORING")
        D.heartbeat(self.dao, block=FIN + 100)
        self.assertEqual(self.state()["state"], "COMPLIANT")

    def test_compliant_grants(self):
        D = self.D
        self.make_compliant()
        st = self.state()
        self.assertEqual((st["state"], st["ok"], st["reasons"]), ("COMPLIANT", True, []))
        r = self.gate()
        self.assertEqual((r["carried_out"], r["state"], r["reasons"]), (True, "COMPLIANT", []))
        self.assertTrue(D.view(D.st, "is_executing_as_voted", self.dao, D.w.now()))
        g = D.view(D.gate, "get_requests", 0, 5)
        self.assertEqual((g["carried_out"], g["requests"][0]["state"]), (1, "COMPLIANT"))

    def test_as_voted_outside_the_window_is_no_coverage(self):
        D = self.D
        self.make_compliant()
        later = D.w.now() + 31 * DAY
        D.w.set_time(later)
        D.heartbeat(self.dao, block=FIN + 1000)
        self.assertEqual(self.state()["state"], "NO_COVERAGE")
        self.assertRefused("NO_COVERAGE")

    def test_every_state_listed_in_config(self):
        cfg = self.D.view(self.D.st, "get_config")
        self.assertEqual(set(cfg["states"]), {"COMPLIANT", "NO_COVERAGE", "PENDING", "DEVIATES", "STALE_MONITORING"})
        self.assertEqual((cfg["monitor"], cfg["stale_s"]), (MONITOR, STALE_S))


class TestCoverageHeartbeat(Base):
    def test_recorded_per_reporter_and_forward_only(self):
        D = self.D
        r = D.heartbeat(self.dao, block=100)
        self.assertEqual(r["recorded"], [self.dao])
        cov = D.view(D.rg, "get_coverage", self.dao, MONITOR)
        self.assertEqual((cov["found"], cov["block"], cov["recorded_at"]), (True, 100, D.w.now()))
        r = D.heartbeat(self.dao, block=90)
        self.assertEqual((r["recorded"], r["skipped"]), ([], [self.dao]))
        self.assertEqual(D.view(D.rg, "get_coverage", self.dao, MONITOR)["block"], 100)
        D.heartbeat(self.dao, block=150)
        self.assertEqual(D.view(D.rg, "get_coverage", self.dao, MONITOR)["block"], 150)
        self.assertFalse(D.view(D.rg, "get_coverage", self.dao, STRANGER)["found"])

    def test_refusals(self):
        D = self.D
        for entries, why in (("x", "JSON"), ("[]", "ONE_TO_50"), (json.dumps([[self.dao, 1]]), "ENTRY_MUST_BE"),
                             (json.dumps([[77, 1, D.w.now() - 1]]), "NO_SUCH_DAO"),
                             (json.dumps([[self.dao, 1, D.w.now() + 60]]), "BAD_BLOCK_OR_TIME"),
                             (json.dumps([[self.dao, -1, D.w.now() - 1]]), "BAD_BLOCK_OR_TIME")):
            with self.assertRaisesRegex(world.Reverted, why):
                D.call(D.rg, "record_coverage", entries, sender=MONITOR)
        self.assertFalse(D.view(D.rg, "get_coverage", self.dao, MONITOR)["found"])

    def test_one_bad_entry_writes_nothing(self):
        D = self.D
        with self.assertRaisesRegex(world.Reverted, "NO_SUCH_DAO"):
            D.call(D.rg, "record_coverage", json.dumps([[self.dao, 5, D.w.now() - 1], [42, 5, D.w.now() - 1]]), sender=MONITOR)
        self.assertFalse(D.view(D.rg, "get_coverage", self.dao, MONITOR)["found"])

    def test_dao_view_shows_last_as_voted(self):
        D = self.D
        cid = self.make_compliant()
        d = D.view(D.rg, "get_dao", self.dao)
        self.assertEqual(d["last_as_voted_check"], cid)
        self.assertGreater(d["last_as_voted_at"], 0)


if __name__ == "__main__":
    unittest.main()
