"""Attack round 2: only the round-1 fixes (amount ownership, withdrawal
blocking, fixed wording for an uncomputable vote).

    cd test && python3 -m unittest -q test_attacks_r2
"""
import unittest

import fixtures as F
import stub
import world
from fixtures import USDC, ALICE, BOB, MALLORY, CONTROLLER, STRANGER, GEN, STAKE
from test_asvoted import Base, U, FORBIDDEN


class Ownership(Base):
    def test_r2_01_amount_on_its_own_line_after_the_recipient(self):
        body = "## Grant\n\nRecipient: " + ALICE + "\nAmount: 50,000 USDC"
        cid, j, c = self.judged(body, to=USDC, data=F.transfer(ALICE, U(50_000)))
        # Round 3 design: a cap must sit on the recipient's own line, list item
        # or table row. An amount on the next line is not provably theirs, so
        # the payment is UNCLEAR (never AS_VOTED); write it as a list item or
        # on one line to make it a cap (r3_02).
        self.assertEqual(c["ruling"], "UNCLEAR")

    def test_r2_02_table_rows_keep_their_own_amounts(self):
        body = "| Recipient | Amount |\n|---|---|\n| " + ALICE + " | 1,000 USDC |\n| " + BOB + " | 9,000 USDC |"
        cid, j, c = self.judged(body, to=USDC, data=F.transfer(ALICE, U(9_000)))
        self.assertEqual(c["ruling"], "DEVIATES")

    def test_r2_03_section_budget_with_no_other_owner_still_applies(self):
        body = "## Payment\n\nSafe: " + ALICE + "\n\nThe budget is 50,000 USDC."
        cid, j, c = self.judged(body, to=USDC, data=F.transfer(ALICE, U(50_000)))
        # Round 3 design: a section-level budget is no longer a cap (it was the
        # ladder H1 and H2-H5 abused); UNCLEAR, never AS_VOTED.
        self.assertEqual(c["ruling"], "UNCLEAR")

    def test_r2_04_ens_owner_counts_as_owner(self):
        F.ens(self.D.mc, "bob.eth", BOB)
        body = "Send 100,000 USDC to bob.eth.\n\n" + ALICE + " coordinates."
        cid, j, c = self.judged(body, to=USDC, data=F.transfer(ALICE, U(90_000)))
        self.assertNotEqual(c["ruling"], "AS_VOTED")


class Withdrawal(Base):
    def setUp(self):
        super().setUp()
        self.D.call(self.D.rg, "claim_dao", self.dao, sender=CONTROLLER)
        self.D.call(self.D.rg, "pledge", self.dao, sender=CONTROLLER, value=10 * GEN)

    def test_r2_10_misbehaving_during_the_delay_does_not_escape(self):
        D = self.D
        D.call(D.rg, "request_withdrawal", self.dao, str(10 * GEN), sender=CONTROLLER)
        D.w.advance(30)
        tx, n = F.safe_exec(D.mc, USDC, 0, F.transfer(MALLORY, U(5)), block_ts=D.w.now() - 5)   # during the delay
        vid = D.read_vote(F.proposal("Send 5 USDC to " + ALICE))
        self.assertTrue(D.file(self.dao, D.read_exec(tx, n), vid, sender=STRANGER)["ok"])
        D.w.advance(61 + F.RG.MODES["DEMO"]["late"])
        with self.assertRaisesRegex(world.Reverted, "CHECKS_OPEN_1"):
            D.call(D.rg, "execute_withdrawal", self.dao, sender=CONTROLLER)

    def test_r2_11_a_blocking_check_has_an_exit(self):
        D = self.D
        cid, tx = self.flow("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(MALLORY, U(5)))
        D.call(D.rg, "request_withdrawal", self.dao, str(10 * GEN), sender=CONTROLLER)
        D.w.advance(601)
        D.call(D.rg, "expire", cid, sender=STRANGER)              # nobody judged it: anyone closes it
        D.call(D.rg, "execute_withdrawal", self.dao, sender=CONTROLLER)
        self.assertEqual(D.view(D.rg, "get_dao", self.dao)["pledge"], "0")
        self.assertLedger()

    def test_r2_12_cancel_then_request_restarts_the_clock(self):
        D = self.D
        D.call(D.rg, "request_withdrawal", self.dao, str(GEN), sender=CONTROLLER)
        D.call(D.rg, "cancel_withdrawal", self.dao, sender=CONTROLLER)
        D.w.advance(80)
        D.call(D.rg, "request_withdrawal", self.dao, str(GEN), sender=CONTROLLER)
        D.w.advance(20)
        with self.assertRaisesRegex(world.Reverted, "WITHDRAWAL_LOCKED"):
            D.call(D.rg, "execute_withdrawal", self.dao, sender=CONTROLLER)

    def test_r2_13_slash_still_lands_after_a_requested_withdrawal(self):
        D = self.D
        cid, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(MALLORY, U(5)))
        D.call(D.rg, "request_withdrawal", self.dao, str(10 * GEN), sender=CONTROLLER)
        D.w.advance(91)
        D.call(D.rg, "finalize", cid)
        D.w.advance(F.RG.MODES["DEMO"]["late"])
        D.call(D.rg, "execute_withdrawal", self.dao, sender=CONTROLLER)
        self.assertEqual(D.view(D.rg, "claimable_of", CONTROLLER)["claimable"], str(10 * GEN - 25 * GEN // 10))
        self.assertLedger()


class Wording(Base):
    def test_r2_20_injected_labels_on_a_passed_vote(self):
        cid, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(MALLORY, U(5)),
                                vote_kw={"vtype": "single-choice", "choices": ["Yes, despite the fraud", "No"], "scores": [9.0, 1.0]})
        for w in FORBIDDEN:
            self.assertNotIn(w, c["ruling_summary"].lower())


if __name__ == "__main__":
    unittest.main()
