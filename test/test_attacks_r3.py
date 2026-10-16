"""Attack round 3, from outside: the code-first matching of amounts and
addresses. Each finding's test was written first and failed on the deployed
code (docs/research/attacks_r3_first_run.txt); the controls pinned behaviour
that already held.

    cd test && python3 -m unittest -q test_attacks_r3
"""
import unittest

import fixtures as F
from fixtures import USDC, COW, WETH, ALICE, BOB, MALLORY, DAY, NOW, FIN, GEN
from test_asvoted import Base, U

DAI = F.addr(0xda1)


class R3(Base):
    def ruling(self, body, **k):
        return self.judged(body, **k)[2]["ruling"]

    def series(self, body, legs, vote_kw=None):
        """One proposal, one execution per (to, data, days_before_now); each
        filed by its own filer in order. Returns the rulings in order."""
        D = self.D
        vid = D.read_vote(F.proposal(body, **(vote_kw or {"start": NOW - 120 * DAY, "end": NOW - 110 * DAY})))
        cids = []
        for n, (to, data, days) in enumerate(legs):
            tx, nonce = F.safe_exec(D.mc, to, 0, data, nonce=10 + n, block=FIN - 400_000 + n * 1000,
                                    block_ts=NOW - days * DAY)
            r = D.file(self.dao, D.read_exec(tx, nonce), vid, sender=F.addr(0xf300 + n))
            self.assertTrue(r["ok"], r)
            cids.append(r["check_id"])
            D.judge_rule(r["check_id"])
        return [D.view(D.rg, "get_check", c)["ruling"] for c in cids]


class Ownership(R3):
    """Whose amount is it, when the amount's own line names no address."""

    LIST = "Grants:\n- Alice: " + ALICE + "\n  Amount: 1,000 USDC\n- Bob: " + BOB + "\n  Amount: 9,000 USDC"

    def test_r3_01_list_item_keeps_its_own_amount(self):
        self.assertEqual(self.ruling(self.LIST, to=USDC, data=F.transfer(ALICE, U(9_000))), "DEVIATES")

    def test_r3_02_list_item_amount_still_authorizes(self):
        self.assertEqual(self.ruling(self.LIST, to=USDC, data=F.transfer(ALICE, U(1_000))), "AS_VOTED")

    def test_r3_03_table_column_keeps_its_own_amount(self):
        body = "| " + ALICE + " | " + BOB + " |\n|---|---|\n| 1,000 USDC | 9,000 USDC |"
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(9_000))), "DEVIATES")
        self.setUp()
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(BOB, U(9_000))), "AS_VOTED")

    def test_r3_04_unattributable_amount_is_not_a_cap(self):
        body = "Amount: 1,000 USDC\nTo: " + ALICE + "\nAmount: 9,000 USDC\nTo: " + BOB
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(9_000))), "UNCLEAR")

    def test_r3_05_one_amount_for_two_recipients_is_shared(self):
        body = "Send 10,000 USDC to " + ALICE + " and " + BOB + "."
        txs = [(0, USDC, 0, F.transfer(ALICE, U(10_000))), (0, USDC, 0, F.transfer(BOB, U(10_000)))]
        self.assertEqual(self.ruling(body, txs=txs), "DEVIATES")
        self.setUp()
        txs = [(0, USDC, 0, F.transfer(ALICE, U(4_000))), (0, USDC, 0, F.transfer(BOB, U(6_000)))]
        self.assertEqual(self.ruling(body, txs=txs), "AS_VOTED")

    def test_r3_06_each_means_per_recipient(self):
        body = "Send 10,000 USDC each to " + ALICE + " and " + BOB + "."
        txs = [(0, USDC, 0, F.transfer(ALICE, U(10_000))), (0, USDC, 0, F.transfer(BOB, U(10_000)))]
        self.assertEqual(self.ruling(body, txs=txs), "AS_VOTED")

    def test_r3_06b_each_elsewhere_in_the_line_is_not_per_recipient(self):
        body = "Send 10,000 USDC to " + ALICE + " and " + BOB + ", each of whom signs the release."
        txs = [(0, USDC, 0, F.transfer(ALICE, U(10_000))), (0, USDC, 0, F.transfer(BOB, U(10_000)))]
        self.assertNotEqual(self.ruling(body, txs=txs), "AS_VOTED")

    def test_r3_07_same_address_two_purposes_is_not_a_deviation(self):
        body = (ALICE + " receives 5,000 USDC for the audit.\n\n" +
                ALICE + " is also reimbursed 3,000 USDC for travel.")
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(8_000))), "UNCLEAR")
        self.setUp()
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(9_000))), "DEVIATES")
        self.setUp()
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(5_000))), "AS_VOTED")

    def test_r3_08_ens_and_hex_are_one_recipient(self):
        F.ens(self.D.mc, "alice.eth", ALICE)
        body = "alice.eth (" + ALICE + ") receives 5,000 USDC.\n\n" + BOB + " receives 50,000 USDC."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(5_000))), "AS_VOTED")
        self.setUp()
        F.ens(self.D.mc, "alice.eth", ALICE)
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(6_000))), "DEVIATES")

    def test_r3_09_ens_line_owns_its_amount(self):
        F.ens(self.D.mc, "alice.eth", ALICE)
        body = "- alice.eth: 1,000 USDC\n- " + BOB + ": 9,000 USDC\n\nAlice's address is " + ALICE + "."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(9_000))), "DEVIATES")


class Wording(R3):
    """What kind of number it is."""

    def test_r3_10_a_minimum_is_not_a_cap(self):
        body = "Pay " + ALICE + " at least 1,000 USDC."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(1_000_000))), "UNCLEAR")

    def test_r3_11_up_to_and_max_are_caps(self):
        for body in ("Pay " + ALICE + " up to 1,000 USDC.", "Max 1,000 USDC to " + ALICE + "."):
            self.setUp()
            self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(1_000))), "AS_VOTED", body)
            self.setUp()
            self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(1_100))), "DEVIATES", body)

    def test_r3_12_per_month_resets_each_calendar_month(self):
        body = "Pay " + ALICE + " 1,000 USDC per month."
        # 2026-08-07, 2026-09-07, then again in September
        legs = [(USDC, F.transfer(ALICE, U(1_000)), 61), (USDC, F.transfer(ALICE, U(1_000)), 30),
                (USDC, F.transfer(ALICE, U(1_000)), 29)]
        self.assertEqual(self.series(body, legs), ["AS_VOTED", "AS_VOTED", "DEVIATES"])

    def test_r3_12b_a_period_word_far_from_the_amount_is_not_a_period(self):
        body = "Grant of 12,000 USDC to " + ALICE + ", paid out in instalments per month."
        legs = [(USDC, F.transfer(ALICE, U(12_000)), 61), (USDC, F.transfer(ALICE, U(12_000)), 30)]
        self.assertEqual(self.series(body, legs), ["AS_VOTED", "DEVIATES"])

    def test_r3_12c_for_n_months_caps_the_total(self):
        body = "Pay " + ALICE + " 1,000 USDC per month for 2 months."
        legs = [(USDC, F.transfer(ALICE, U(1_000)), 91), (USDC, F.transfer(ALICE, U(1_000)), 61),
                (USDC, F.transfer(ALICE, U(1_000)), 30)]
        self.assertEqual(self.series(body, legs), ["AS_VOTED", "AS_VOTED", "DEVIATES"])

    def test_r3_13_unknown_period_with_earlier_payments_is_unclear(self):
        body = "Pay " + ALICE + " 500 USDC per epoch."
        legs = [(USDC, F.transfer(ALICE, U(500)), 40), (USDC, F.transfer(ALICE, U(500)), 20)]
        self.assertEqual(self.series(body, legs), ["AS_VOTED", "UNCLEAR"])

    def test_r3_14_per_month_still_sums_inside_one_execution(self):
        body = "Pay " + ALICE + " 1,000 USDC monthly."
        txs = [(0, USDC, 0, F.transfer(ALICE, U(1_000))), (0, USDC, 0, F.transfer(ALICE, U(1_000)))]
        self.assertEqual(self.ruling(body, txs=txs), "DEVIATES")

    def test_r3_15_dollar_figure_in_a_stablecoin_paid_in_a_volatile_token(self):
        body = "Send 50,000 USDC worth of COW to " + ALICE + "."
        self.assertEqual(self.ruling(body, to=COW, data=F.transfer(ALICE, 10_000_000 * GEN)), "UNCLEAR")


class Numbers(R3):
    def test_r3_20_dot_grouped_thousands(self):
        body = "Send 1.000.000 USDC to " + ALICE + "."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(1_000_000))), "AS_VOTED")

    def test_r3_21_european_decimal_comma(self):
        body = "Send 1.250.000,50 USDC to " + ALICE + "."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(1_250_000))), "AS_VOTED")

    def test_r3_22_space_grouped_thousands(self):
        for sep in (" ", " ", " ", " "):
            self.setUp()
            body = "Send 1" + sep + "000" + sep + "000 USDC to " + ALICE + "."
            self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(1_000_000))), "AS_VOTED", repr(sep))

    def test_r3_23_one_plain_space_group_is_no_amount(self):
        # "5 000" is 5,000 or a list number then 000; it is neither a cap of 0
        # (which made every payment OVER) nor a cap of 5,000.
        body = "Send 5 000 USDC to " + ALICE + "."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(5_000))), "UNCLEAR")

    def test_r3_24_one_dot_group_reads_as_a_decimal(self):
        # "50.000" is 50 or 50,000; the smaller reading is the one kept.
        body = "Send 50.000 USDC to " + ALICE + "."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(50_000))), "DEVIATES")

    def test_r3_25_suffixes(self):
        for body, amt in (("Send 1.5k USDC to " + ALICE, 1_500), ("Send 2.5M USDC to " + ALICE, 2_500_000),
                          ("Send $1.2m to " + ALICE, 1_200_000), ("Send 3 million USDC to " + ALICE, 3_000_000),
                          ("Send 1,250.75 USDC to " + ALICE, 1_250)):
            self.setUp()
            self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(amt))), "AS_VOTED", body)
            self.setUp()
            self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(amt * 11 // 10))), "DEVIATES", body)

    def test_r3_26_tokens_of_different_decimals(self):
        F.tokens(self.D.mc, {DAI: ("DAI", 18)})
        body = "Send 5,000 DAI to " + ALICE + "."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(5_000))), "AS_VOTED")
        self.setUp()
        F.tokens(self.D.mc, {DAI: ("DAI", 18)})
        txs = [(0, USDC, 0, F.transfer(ALICE, U(3_000))), (0, DAI, 0, F.transfer(ALICE, 3_000 * GEN))]
        self.assertEqual(self.ruling(body, txs=txs), "DEVIATES")


class Splitting(R3):
    def test_r3_30_many_legs_in_one_batch(self):
        txs = [(0, USDC, 0, F.transfer(ALICE, U(300)))] * 20
        self.assertEqual(self.ruling("Send 5,000 USDC to " + ALICE, txs=txs), "DEVIATES")

    def test_r3_31_dust_checks_cannot_push_real_ones_out_of_view(self):
        # Nine dust payments filed first, then two full ones: the second full
        # payment must still see the first.
        body = "Send 5,000 USDC to " + ALICE + "."
        legs = [(USDC, F.transfer(ALICE, 1), 60 - n) for n in range(9)]
        legs += [(USDC, F.transfer(ALICE, U(5_000)), 40), (USDC, F.transfer(ALICE, U(5_000)), 30)]
        out = self.series(body, legs)
        self.assertNotEqual(out[-1], "AS_VOTED", out)

    def test_r3_32_approve_and_transfer_to_one_recipient_add_up(self):
        txs = [(0, USDC, 0, F.approve(ALICE, U(5_000))), (0, USDC, 0, F.transfer(ALICE, U(5_000)))]
        self.assertEqual(self.ruling("Send 5,000 USDC to " + ALICE, txs=txs), "DEVIATES")

    def test_r3_33_approve_alone_within_the_amount(self):
        body = "Approve " + ALICE + " to spend 5,000 USDC."
        self.assertEqual(self.ruling(body, to=USDC, data=F.approve(ALICE, U(5_000))), "AS_VOTED")


class Hidden(R3):
    def test_r3_40_html_comment_is_not_part_of_the_proposal(self):
        body = "Grant for " + ALICE + ": 1,000 USDC\n\n<!-- " + MALLORY + " 9,000 USDC -->"
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(MALLORY, U(9_000))), "DEVIATES")

    def test_r3_41_html_comment_cannot_carry_an_amount(self):
        body = "Grant for " + ALICE + " <!-- 9,000 USDC -->: 1,000 USDC"
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(9_000))), "DEVIATES")

    def test_r3_42_address_only_inside_a_link_counts(self):
        # By design: a link's target is part of the text voters read (shown
        # on hover, in the raw proposal, and on every block explorer link).
        body = "Send 1,000 USDC to [the grants Safe](https://app.safe.global/home?safe=eth:" + ALICE + ")."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(1_000))), "AS_VOTED")

    def test_r3_43_amount_inside_a_link_target_is_not_an_amount(self):
        body = "Send 1,000 USDC to " + ALICE + " ([calc](https://x.example/?q=9000 USDC))."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(9_000))), "DEVIATES")


if __name__ == "__main__":
    unittest.main()
