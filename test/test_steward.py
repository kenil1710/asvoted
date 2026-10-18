"""Regression tests for the steward's requested changes (docs/STEWARD_RESPONSE.md).

    cd test && python3 -m unittest -q test_steward
"""
import copy
import unittest

import fixtures as F
import stub
import world
from fixtures import RG, SAFE, USDC, ALICE, MALLORY, CONTROLLER, FILER, STRANGER, TARGET, DAY, STAKE, BOND, GEN
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


if __name__ == "__main__":
    unittest.main()
