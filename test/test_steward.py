"""Regression tests for the steward's requested changes (docs/STEWARD_RESPONSE.md).

    cd test && python3 -m unittest -q test_steward
"""
import copy
import unittest

import fixtures as F
import world
from fixtures import RG, SAFE, USDC, ALICE, MALLORY, CONTROLLER, FILER, DAY, STAKE, BOND
from test_asvoted import Base, U, model_says


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


if __name__ == "__main__":
    unittest.main()
