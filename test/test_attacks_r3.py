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
        # Second pass (required design): only the recipient's own row caps, so
        # an amount in the column below the header is not a cap for anyone.
        # The attack (Alice taking Bob's 9,000) is still never AS_VOTED.
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(9_000))), "UNCLEAR")
        self.setUp()
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(BOB, U(9_000))), "UNCLEAR")

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
        # Second pass (required design): two different amounts for one
        # recipient is more than one candidate, so there is no cap at all:
        # UNCLEAR whatever is paid, never a wrong slash and never AS_VOTED.
        for amt in (8_000, 9_000, 5_000):
            self.setUp()
            self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(amt))), "UNCLEAR", amt)

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
        # Required design: an unnamed address inside a sub-call blocks
        # AS_VOTED; code cannot prove what the inner call does with it, so the
        # action is UNCLEAR (the attacker's test expected NOT_AUTHORIZED).
        self.assertEqual(self.outcomes(c), ["UNCLEAR"])
        self.assertNotEqual(c["ruling"], "AS_VOTED")

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
        # Snapshot does not check treasury entries: evil.eth can list the DAO's
        # Safe. Kept by design (README, Known limitations): Snapshot records
        # nothing about who controls a Safe. What this test pins is that the
        # rogue listing is its own record: its rulings and standing never touch
        # the real space's listing.
        D = self.D
        F.space("evil.eth", treasuries=[[SAFE, "1"]], controllers=[MALLORY])
        D.call(D.vr, "read_space", "evil.eth", "ethereum", SAFE)
        evil = D.call(D.rg, "list_dao", "evil.eth", "ethereum", SAFE)["dao_id"]
        self.assertNotEqual(evil, self.dao)
        tx, n = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(5)))
        vid = D.read_vote(F.proposal("Send 5 USDC to " + BOB, space="evil.eth", treasuries=[[SAFE, "1"]],
                                     controllers=[MALLORY]))
        cid = D.file(evil, D.read_exec(tx, n), vid)["check_id"]
        D.judge_rule(cid)
        D.w.advance(91)
        D.call(D.rg, "finalize", cid)
        self.assertEqual(D.view(D.rg, "get_check", cid)["final_verdict"], "DEVIATES")
        real = D.view(D.rg, "get_dao", self.dao)
        self.assertEqual((real["deviates"], real["n_checks"], real["last_deviates_at"]), (0, 0, 0))
        self.assertTrue(D.view(D.st, "is_executing_as_voted", self.dao, D.w.now()))
        # the real space's proposals cannot be filed on the rogue listing
        r = D.file(evil, D.read_exec(*F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(5)), nonce=31)),
                   D.read_vote(F.proposal("Send 5 USDC to " + ALICE)))
        self.assertEqual((r["ok"], r["reason"]), (False, "PROPOSAL_IS_NOT_IN_THE_DAOS_SPACE"))

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
        # fixed: the withdrawal waits RG late seconds past the unlock, so the
        # late execution can finalize and be filed first
        with self.assertRaisesRegex(world.Reverted, "WITHDRAWAL_LOCKED"):
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
        D.w.advance(RG.MODES["DEMO"]["late"])
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
        # Required design: 6 h canonical (the attacker proposed 72 h). An
        # appeal that produces DEVIATES opens a second 6 h window for the DAO.
        self.assertGreaterEqual(RG.MODES["CANONICAL"]["contest"], 6 * 3600)


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


# =============================================================================
# Second pass: the required design for round 3 (see docs/ATTACK_REPORT.md).
# =============================================================================

ROUTER_BODY = QUOTE + " " + TARGET + "."
DEPOSIT = bytes.fromhex("d0e30db0")


class DaoResponse(R3):
    """An appeal that produces DEVIATES gives the DAO its own window."""

    def setUp(self):
        super().setUp()
        self.D.call(self.D.rg, "claim_dao", self.dao, sender=CONTROLLER)
        self.D.call(self.D.rg, "pledge", self.dao, sender=CONTROLLER, value=10 * GEN)

    def _turned(self):
        D = self.D
        stub.MODEL.answer = model_says("AUTHORIZED", QUOTE)
        cid, j, c = self.judged(ROUTER_BODY, to=TARGET, data=DEPOSIT)
        self.assertEqual(c["ruling"], "AS_VOTED")
        D.call(D.rg, "appeal", cid, APPEAL_TEXT, 0, sender=STRANGER, value=BOND)
        stub.MODEL.answer = model_says("NOT_AUTHORIZED", QUOTE)
        D.judge_rule(cid)
        c = D.view(D.rg, "get_check", cid)
        self.assertEqual((c["status"], c["appeal_ruling"], c["final_verdict"]), ("CONTESTABLE", "DEVIATES", ""))
        return cid

    def test_r3_70_no_final_deviates_before_the_dao_answers(self):
        D = self.D
        cid = self._turned()
        with self.assertRaisesRegex(world.Reverted, "CONTESTABLE_UNTIL"):
            D.call(D.rg, "finalize", cid)
        D.w.advance(91)
        D.call(D.rg, "finalize", cid)                 # the DAO let its window pass
        c = D.view(D.rg, "get_check", cid)
        self.assertEqual((c["final_verdict"], c["bounty_to"]), ("DEVIATES", STRANGER))
        self.assertLedger()

    def test_r3_71_the_dao_answers_and_wins(self):
        D = self.D
        cid = self._turned()
        r = D.call(D.rg, "appeal", cid, "The deposit is the swap the proposal describes; the earlier panel misread it.",
                   0, sender=CONTROLLER, value=BOND)
        self.assertEqual(r["round"], 2)
        stub.MODEL.answer = model_says("AUTHORIZED", QUOTE)
        D.judge_rule(cid)
        c = D.view(D.rg, "get_check", cid)
        self.assertEqual((c["final_verdict"], c["final_how"], c["slash"]), ("AS_VOTED", "RESPONSE_RULED", "0"))
        moves = [m[0] for m in c["settlement"]]
        self.assertIn("response bond refunded", moves)
        self.assertIn("appeal bond to the DAO pledge", moves)
        self.assertLedger()

    def test_r3_72_only_the_dao_side_responds(self):
        D = self.D
        cid = self._turned()
        r = D.call(D.rg, "appeal", cid, "A third party would like yet another panel to read the proposal once more.",
                   0, sender=FILER2, value=BOND)
        self.assertEqual((r["ok"], r["reason"]), (False, "ONLY_THE_DAOS_CONTROLLER_MAY_RESPOND"))

    def test_r3_73_the_dao_may_name_the_proposal_it_implements(self):
        D = self.D
        cid = self._turned()
        other = D.read_vote(F.proposal(ROUTER_BODY + " Deposit is fine."))
        r = D.call(D.rg, "appeal", cid, "This deposit implements the other proposal, which describes it in its own words.",
                   other, sender=CONTROLLER, value=BOND)
        self.assertTrue(r["ok"], r)
        self.assertEqual(D.view(D.rg, "get_check", cid)["resp_vote_id"], other)


class Switching(R3):
    def test_r3_74_unclaimed_listing_nobody_switches_the_proposal(self):
        # Unclaimed: anyone but the filer may appeal a DEVIATES, but only the
        # DAO's controller may name another proposal.
        D = self.D
        cid, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(MALLORY, U(5)))
        other = D.read_vote(F.proposal("Send 5 USDC to " + MALLORY))
        r = D.call(D.rg, "appeal", cid, APPEAL_TEXT, other, sender=STRANGER, value=BOND)
        self.assertEqual((r["ok"], r["reason"]), (False, "ONLY_THE_DAOS_CONTROLLER_ANSWERING_DEVIATES_MAY_NAME_ANOTHER_PROPOSAL"))

    def test_r3_75_an_expired_check_can_be_refiled(self):
        D = self.D
        vid = D.read_vote(F.proposal("Send 5 USDC to " + ALICE))
        tx, n = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(5)), nonce=40)
        eid = D.read_exec(tx, n)
        first = D.file(self.dao, eid, vid)["check_id"]
        D.w.advance(601)
        D.call(D.rg, "expire", first, sender=STRANGER)
        r = D.file(self.dao, eid, vid, sender=FILER2)
        self.assertTrue(r["ok"], r)
        D.judge_rule(r["check_id"])
        self.assertEqual(D.view(D.rg, "get_check", r["check_id"])["ruling"], "AS_VOTED")


class Choices(R3):
    KW = {"vtype": "single-choice", "choices": ["Yes, option A", "Yes, option B", "No"], "scores": [600.0, 300.0, 100.0]}

    def test_r3_76_the_winning_option_sets_the_cap(self):
        body = "Option A: send 50,000 USDC to " + ALICE + ".\n\nOption B: send 100,000 USDC to " + ALICE + "."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(50_000)), vote_kw=self.KW), "AS_VOTED")
        self.setUp()
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(100_000)), vote_kw=self.KW), "DEVIATES")

    def test_r3_77_winner_text_not_found_is_unclear(self):
        body = "Send 50,000 USDC to " + ALICE + "."
        self.assertEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(50_000)), vote_kw=self.KW), "UNCLEAR")


class Tokens(R3):
    FOO = F.addr(0xf00)

    def test_r3_78_unlisted_token_named_by_address_counts(self):
        F.tokens(self.D.mc, {self.FOO: ("FOO", 18)})
        body = "Send 100 FOO (token " + self.FOO + ") to " + ALICE + "."
        self.assertEqual(self.ruling(body, to=self.FOO, data=F.transfer(ALICE, 100 * GEN)), "AS_VOTED")

    def test_r3_79_unlisted_token_by_symbol_alone_is_unclear(self):
        F.tokens(self.D.mc, {self.FOO: ("FOO", 18)})
        body = "Send 100 FOO to " + ALICE + "."
        self.assertEqual(self.ruling(body, to=self.FOO, data=F.transfer(ALICE, 100 * GEN)), "UNCLEAR")


class Identity(R3):
    def test_r3_80_names_unresolvable_at_the_execution_are_never_proof_of_absence(self):
        D = self.D
        cid, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(MALLORY, U(5)))
        inp = {"exec": D.view(D.er, "get_execution", 1), "prior": [],
               "vote": dict(D.view(D.vr, "get_proposal", 1), text="Send 5 USDC to alice.eth", ens={}, ens_unresolved=True),
               "allow": F.TOKEN_LIST}
        self.assertEqual([r["outcome"] for r in F.JG.code_rules(inp)], ["UNCLEAR"])

    def test_r3_81_verified_when_the_space_owner_owns_the_safe(self):
        D = self.D
        node = F.VR.namehash("verified.eth").hex()
        D.mc.calls[(F.VR.ENS_REGISTRY, "0x02571be3" + node)] = "0x" + "0" * 24 + CONTROLLER[2:]
        D.mc.calls[(OTHER_SAFE, "0xa0e67e2b")] = "0x" + ("%064x" % 32) + ("%064x" % 2) + "0" * 24 + ADMIN[2:] + "0" * 24 + CONTROLLER[2:]
        F.space("verified.eth", treasuries=[[OTHER_SAFE, "1"]])
        D.call(D.vr, "read_space", "verified.eth", "ethereum", OTHER_SAFE)
        dao = D.call(D.rg, "list_dao", "verified.eth", "ethereum", OTHER_SAFE)["dao_id"]
        self.assertTrue(D.view(D.rg, "get_dao", dao)["verified"])
        self.assertFalse(D.view(D.rg, "get_dao", self.dao)["verified"])

    def test_r3_82_standing_is_keyed_by_space_and_safe(self):
        D = self.D
        self.assertTrue(D.view(D.st, "is_executing_as_voted_for", F.SPACE, "ethereum", SAFE, D.w.now()))
        self.assertFalse(D.view(D.st, "is_executing_as_voted_for", "evil.eth", "ethereum", SAFE, D.w.now()))

    def test_r3_83_address_two_levels_down_is_found(self):
        inner2 = bytes.fromhex("a9059cbb") + F.wa(MALLORY) + F.w(5)
        inner1 = bytes.fromhex("1f0464d1") + F.w(32) + F.dyn(inner2)
        data = bytes.fromhex("ac9650d8") + F.w(32) + F.dyn(inner1)
        stub.MODEL.answer = model_says("AUTHORIZED", QUOTE)
        c = self.judged(ROUTER_BODY, to=TARGET, data=data)[2]
        self.assertEqual(self.outcomes(c), ["UNCLEAR"])
