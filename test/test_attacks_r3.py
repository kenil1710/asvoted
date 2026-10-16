"""Attack round 3, from outside: the code-first matching of amounts and
addresses. Each finding's test was written first and failed on the deployed
code (docs/research/attacks_r3_first_run.txt); the controls pinned behaviour
that already held.

    cd test && python3 -m unittest -q test_attacks_r3
"""
import unittest

import fixtures as F
from fixtures import USDC, COW, WETH, ALICE, BOB, MALLORY, DAY, NOW, FIN, GEN, RG
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

# =============================================================================
# Round 3, second attacker: decoding, binding, pairing, money, docs.
# Each test fails on the deployed code (93d5be9) for the reason in its name;
# docs/ATTACK_REPORT_R3.md has the table.
# =============================================================================

import json
import re
from pathlib import Path

import stub
import world
from fixtures import (SAFE, OTHER_SAFE, TARGET, FILER, FILER2, CONTROLLER, ADMIN, STRANGER, STAKE, BOND)
from test_asvoted import model_says

FAKE = F.addr(0xfa4e)
SPOOF = F.addr(0x5900f)
VANITY = "0x0000000000" + F.addr(0x7a71)[12:]
QUOTE = "Swap through the router"
APPEAL_TEXT = "This execution implements a different proposal, the one named here by its record id."


class Decoding(R3):
    def test_r3_50_eth_sent_with_a_token_call_is_not_counted(self):
        # A payable contract calling itself USDC: the Safe calls its transfer()
        # with 1,000 ETH attached. Only the 5 "USDC" leg is checked.
        F.tokens(self.D.mc, {FAKE: ("USDC", 6)})
        c = self.judged("Send 5 USDC to " + ALICE, to=FAKE, value=1_000 * GEN, data=F.transfer(ALICE, U(5)))[2]
        self.assertEqual(c["ruling"], "DEVIATES")

    def test_r3_51_transfer_from_an_unmentioned_holder(self):
        # transferFrom's `from` is never checked: the Safe pulls 1M USDC from
        # BOB (who had approved it) into itself, and that is "into the Safe".
        txs = [(0, USDC, 0, F.transfer(ALICE, U(5))), (0, USDC, 0, F.transfer_from(BOB, SAFE, U(1_000_000)))]
        self.assertEqual(self.ruling("Send 5 USDC to " + ALICE, txs=txs), "DEVIATES")

    def _router_call(self, data):
        stub.MODEL.answer = model_says("AUTHORIZED", QUOTE)
        return self.judged(QUOTE + " " + TARGET + ".", to=TARGET, data=data)[2]

    def test_r3_52_address_inside_nested_calldata_reaches_the_model(self):
        # multicall(bytes[]) with an inner call paying MALLORY: the inner words
        # sit 4 bytes off the 32-byte grid, so no address argument is found.
        inner = bytes.fromhex("04e45aaf") + F.wa(MALLORY) + F.w(U(5))
        data = bytes.fromhex("ac9650d8") + F.w(32) + F.w(1) + F.w(32) + F.dyn(inner)
        c = self._router_call(data)
        self.assertEqual(self.outcomes(c), ["NOT_AUTHORIZED"])

    def test_r3_53_vanity_address_argument_is_not_address_like(self):
        # ADDR_LIKE_MIN = 2**120: an address with ten leading zero hex digits
        # (minable in hours) is not treated as an address argument.
        c = self._router_call(F.call_with("f2fde38b", VANITY))
        self.assertEqual(self.outcomes(c), ["NOT_AUTHORIZED"])

    def test_r3_54_symbol_spoof_identifies_an_unmentioned_contract(self):
        # Any contract whose symbol() is a word of the proposal counts as named.
        F.tokens(self.D.mc, {SPOOF: ("router", 18)})
        c = self._router_call(F.call_with("f2fde38b", SPOOF))
        self.assertEqual(self.outcomes(c), ["NOT_AUTHORIZED"])

    def test_r3_55_quoted_calldata_replayed_on_another_token(self):
        # The proposal quotes a 100 COW transfer; the same bytes sent to USDC
        # (6 decimals) move 100,000,000,000,000 USDC and are "exact calldata".
        body = ("Transfer 100 COW (token " + COW + ") to " + ALICE + ", calldata 0x" +
                F.transfer(ALICE, 100 * GEN).hex() + "\n\nOur USDC is held at " + USDC + ".")
        self.assertNotEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, 100 * GEN)), "AS_VOTED")


class Caps(R3):
    def test_r3_56_two_recipients_on_one_line_share_the_larger_amount(self):
        body = "Pay " + ALICE + " 1,000 USDC and " + BOB + " 90,000 USDC."
        self.assertNotEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(90_000))), "AS_VOTED")

    def test_r3_57_largest_number_near_the_recipient_is_the_cap(self):
        body = "Send 5,000 USDC to " + ALICE + " from the 2,000,000 USDC treasury."
        self.assertNotEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(2_000_000))), "AS_VOTED")

    def test_r3_58_a_rejected_request_is_a_cap(self):
        body = "The request from " + MALLORY + " for 100,000 USDC is rejected."
        self.assertNotEqual(self.ruling(body, to=USDC, data=F.transfer(MALLORY, U(100_000))), "AS_VOTED")

    def test_r3_59_the_losing_option_sets_the_cap(self):
        body = "Option A: send 50,000 USDC to " + ALICE + ".\n\nOption B: send 100,000 USDC to " + ALICE + "."
        kw = {"vtype": "single-choice", "choices": ["Yes, option A", "Yes, option B", "No"], "scores": [600.0, 300.0, 100.0]}
        self.assertNotEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(100_000)), vote_kw=kw), "AS_VOTED")

    def test_r3_60_an_expired_check_hides_a_payment_from_the_cap(self):
        # Exec 1 is filed and left unjudged: it expires UNCLEAR, which drops it
        # from the priors, and (tx, proposal) can never be filed again.
        D = self.D
        vid = D.read_vote(F.proposal("Send 50,000 USDC to " + ALICE))
        t1, n1 = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(50_000)), nonce=20)
        first = D.file(self.dao, D.read_exec(t1, n1), vid, sender=FILER2)["check_id"]
        D.w.advance(601)
        D.call(D.rg, "expire", first, sender=STRANGER)
        t2, n2 = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(50_000)), nonce=21)
        second = D.file(self.dao, D.read_exec(t2, n2), vid)["check_id"]
        D.judge_rule(second)
        self.assertEqual(D.view(D.rg, "get_check", second)["ruling"], "DEVIATES")


class Binding(R3):
    def test_r3_61_ens_repointed_after_execution_turns_a_correct_payment_into_deviates(self):
        # alice.eth -> ALICE at the vote's snapshot AND at the execution block;
        # the owner repoints it before the read. The payment was right when made.
        for blk in (F.FIN - 50_000, F.FIN - 1000):
            F.ens(self.D.mc, "alice.eth", ALICE, block=blk)
        F.ens(self.D.mc, "alice.eth", BOB)
        self.assertEqual(self.ruling("Send 5 USDC to alice.eth", to=USDC, data=F.transfer(ALICE, U(5))), "AS_VOTED")

    def test_r3_62_any_space_can_list_any_safe(self):
        # Snapshot does not check treasury entries: evil.eth lists the DAO's
        # Safe, and its proposals can then be used to rule on that Safe.
        F.space("evil.eth", treasuries=[[SAFE, "1"]], controllers=[MALLORY])
        self.D.call(self.D.vr, "read_space", "evil.eth", "ethereum", SAFE)
        with self.assertRaises(world.Reverted):
            self.D.call(self.D.rg, "list_dao", "evil.eth", "ethereum", SAFE)

    def test_r3_63_unlisting_the_safe_blocks_every_filing(self):
        # The execution happened while listed; the space then drops the Safe
        # from its treasuries (one admin edit) and nothing can be filed.
        D = self.D
        tx, n = F.safe_exec(D.mc, USDC, 0, F.transfer(MALLORY, U(5)))
        vid = D.read_vote(F.proposal("Send 5 USDC to " + ALICE, treasuries=[[OTHER_SAFE, "1"]]))
        r = D.file(self.dao, D.read_exec(tx, n), vid)
        self.assertTrue(r["ok"], r.get("reason"))


class Pairing(R3):
    def setUp(self):
        super().setUp()
        self.D.call(self.D.rg, "claim_dao", self.dao, sender=CONTROLLER)
        self.D.call(self.D.rg, "pledge", self.dao, sender=CONTROLLER, value=10 * GEN)

    def test_r3_64_stranger_appeals_as_voted_with_an_unrelated_proposal(self):
        # A correct AS_VOTED is appealed by a stranger naming another passed
        # proposal; judged against that one it DEVIATES, final, no DAO appeal.
        D = self.D
        cid, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)))
        self.assertEqual(c["ruling"], "AS_VOTED")
        other = D.read_vote(F.proposal("Send 5 USDC to " + BOB))
        D.call(D.rg, "appeal", cid, APPEAL_TEXT, other, sender=STRANGER, value=BOND)
        if D.view(D.rg, "get_check", cid)["status"] == "APPEALED":
            D.judge_rule(cid)
        c = D.view(D.rg, "get_check", cid)
        self.assertNotEqual((c["final_verdict"], c["bounty_to"]), ("DEVIATES", STRANGER), c["settlement"])


class Money(R3):
    def setUp(self):
        super().setUp()
        self.D.call(self.D.rg, "claim_dao", self.dao, sender=CONTROLLER)
        self.D.call(self.D.rg, "pledge", self.dao, sender=CONTROLLER, value=10 * GEN)

    def test_r3_65_withdrawal_unlocks_before_a_late_execution_can_be_filed(self):
        # Execute off-proposal 60 s before the unlock: Ethereum takes ~13 min
        # to finalize, so no check can exist yet; the pledge leaves, the later
        # DEVIATES slashes nothing.
        D = self.D
        D.call(D.rg, "request_withdrawal", self.dao, str(10 * GEN), sender=CONTROLLER)
        D.w.advance(90)
        tx, n = F.safe_exec(D.mc, USDC, 0, F.transfer(MALLORY, U(5)), block_ts=D.w.now() - 60)
        D.w.advance(1)
        D.call(D.rg, "execute_withdrawal", self.dao, sender=CONTROLLER)
        cid = D.file(self.dao, D.read_exec(tx, n), D.read_vote(F.proposal("Send 5 USDC to " + ALICE)))["check_id"]
        D.judge_rule(cid)
        D.w.advance(91)
        D.call(D.rg, "finalize", cid)
        self.assertGreater(int(D.view(D.rg, "get_check", cid)["slash"]), 0)

    def test_r3_66_newer_checks_push_a_blocking_check_out_of_the_scan(self):
        # _blocking() looks at the newest SCAN_CAP checks only. After the unlock
        # the DAO files SCAN_CAP checks of fresh (non-blocking) executions.
        D = self.D
        vid = D.read_vote(F.proposal("Send 5 USDC to " + ALICE))
        tx, n = F.safe_exec(D.mc, USDC, 0, F.transfer(MALLORY, U(5)))
        D.file(self.dao, D.read_exec(tx, n), vid)                       # left open: it should block
        D.call(D.rg, "request_withdrawal", self.dao, str(10 * GEN), sender=CONTROLLER)
        D.w.advance(91)
        for k in range(RG.SCAN_CAP):
            t, m = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, 1), nonce=1000 + k, block_ts=D.w.now())
            D.file(self.dao, D.read_exec(t, m), vid, sender=CONTROLLER)
        with self.assertRaisesRegex(world.Reverted, "CHECKS_OPEN"):
            D.call(D.rg, "execute_withdrawal", self.dao, sender=CONTROLLER)

    def test_r3_67_standing_counts_when_a_ruling_lands_not_when_the_execution_ran(self):
        # A two-year-old execution ruled today makes the DAO "not executing as
        # voted" for the next 30 days.
        D = self.D
        vid = D.read_vote(F.proposal("Send 5 USDC to " + ALICE, start=NOW - 800 * DAY, end=NOW - 790 * DAY))
        tx, n = F.safe_exec(D.mc, USDC, 0, F.transfer(MALLORY, U(5)), block_ts=NOW - 730 * DAY)
        cid = D.file(self.dao, D.read_exec(tx, n), vid)["check_id"]
        D.judge_rule(cid)
        D.w.advance(91)
        D.call(D.rg, "finalize", cid)
        self.assertTrue(D.view(D.st, "is_executing_as_voted", self.dao, D.w.now()))


class Policy(unittest.TestCase):
    def test_r3_68_canonical_contest_window_is_too_short_for_a_dao_to_answer(self):
        # 1 h to notice a filing, read the right proposal and appeal; the
        # listings on the canonical registry are unclaimed real DAOs.
        self.assertGreaterEqual(RG.MODES["CANONICAL"]["contest"], DAY)


class Docs(unittest.TestCase):
    ROOT = Path(__file__).resolve().parent.parent

    def test_r3_69_readme_names_the_deployed_commit(self):
        readme = (self.ROOT / "README.md").read_text()
        addresses = (self.ROOT / "ADDRESSES.md").read_text()
        deployed = re.search(r"deployed from commit `([0-9a-f]{40})`", addresses).group(1)
        self.assertTrue("deployed from commit `" + deployed + "`" in readme,
                        "README names " + re.search(r"deployed from commit `([0-9a-f]{7})", readme).group(1))


if __name__ == "__main__":
    unittest.main()
