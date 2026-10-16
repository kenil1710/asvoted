"""Attack round 4: only the round-3 fixes (d51b8a7..HEAD in contracts/).
Every test here is a finding and fails on the code as committed; the report
is docs/ATTACK_REPORT_R4.md.

    cd test && python3 -m unittest test_attacks_r4
"""
import unittest

import fixtures as F
import stub
import world
from fixtures import (USDC, WETH, ALICE, BOB, MALLORY, TARGET, SAFE, OTHER_SAFE, CONTROLLER, ADMIN, STRANGER,
                      FILER, FILER2, BOND, GEN, DAY, NOW, FIN)
from test_asvoted import Base, U, model_says

QUOTE = "Swap through the router"
ROUTER_BODY = QUOTE + " " + TARGET + "."
APPEAL_TEXT = "This execution implements a different proposal, the one named here by its record id."
SOCK = F.addr(0x50c4)


def nest(inner, sel="1f0464d1"):
    """inner call -> outer(bytes) call carrying it."""
    return bytes.fromhex(sel) + F.w(32) + F.dyn(inner)


class R4(Base):
    def ruling(self, body, **k):
        return self.judged(body, **k)[2]["ruling"]


class Nested(R4):
    def _router(self, data):
        stub.MODEL.answer = model_says("AUTHORIZED", QUOTE)
        return self.judged(ROUTER_BODY, to=TARGET, data=data)[2]

    def test_r4_01_nested_address_with_a_zero_top_byte_is_not_seen(self):
        # nested_addresses only counts windows whose top address byte is not
        # 00. An address starting 0x00 takes ~256 tries to mine. The inner
        # transfer to it reaches the model, which says AUTHORIZED.
        zero_top = "0x00" + MALLORY[4:]
        inner = bytes.fromhex("a9059cbb") + F.wa(zero_top) + F.w(U(1_000_000))
        c = self._router(bytes.fromhex("ac9650d8") + F.w(32) + F.w(1) + F.w(32) + F.dyn(inner))
        self.assertEqual(self.outcomes(c), ["UNCLEAR"])
        self.assertNotEqual(c["ruling"], "AS_VOTED")

    def test_r4_02_payment_four_levels_down_is_not_seen(self):
        # NEST_DEPTH = 3 scans offsets 4, 8, 12. One more wrapper puts the
        # payee at 16 bytes off the grid; nothing flags the depth.
        inner = bytes.fromhex("a9059cbb") + F.wa(MALLORY) + F.w(U(1_000_000))
        data = nest(nest(nest(nest(inner))), sel="ac9650d8")
        c = self._router(data)
        self.assertEqual(self.outcomes(c), ["UNCLEAR"])
        self.assertNotEqual(c["ruling"], "AS_VOTED")


class NativeValue(R4):
    def test_r4_03_wrapping_eth_the_proposal_states_is_a_major_deviation(self):
        # The value leg to WETH is checked with mentioned() only; the call to
        # WETH itself is identified by its listed symbol. A wrap the proposal
        # states in words is NOT_AUTHORIZED, code-settled, MAJOR slash.
        stub.MODEL.answer = model_says("AUTHORIZED", "Wrap 100 ETH into WETH")
        c = self.judged("Wrap 100 ETH into WETH for the treasury.", to=WETH, value=100 * GEN,
                        data=bytes.fromhex("d0e30db0"))[2]
        self.assertNotEqual(c["ruling"], "DEVIATES")


class Turns(R4):
    def test_r4_04_unclaimed_listing_a_sock_appeal_takes_the_daos_turn(self):
        # Every canonical listing is unclaimed. The filer pairs a correct
        # execution with an unrelated passed proposal (DEVIATES), and their
        # second address appeals at once, without a better proposal (nobody
        # may name one on an unclaimed listing). The single appeal slot is
        # gone: the real space admin claims within the window and still has
        # no turn. The DEVIATES becomes final.
        D = self.D
        wrong = D.read_vote(F.proposal("Send 5 USDC to " + BOB))
        right = D.read_vote(F.proposal("Send 5 USDC to " + ALICE))
        tx, n = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(5)), nonce=60)
        cid = D.file(self.dao, D.read_exec(tx, n), wrong)["check_id"]
        D.judge_rule(cid)
        self.assertEqual(D.view(D.rg, "get_check", cid)["ruling"], "DEVIATES")
        r = D.call(D.rg, "appeal", cid, "Panel please read the proposal one more time, carefully, thanks.", 0,
                   sender=SOCK, value=BOND)
        self.assertTrue(r["ok"], r)
        D.call(D.rg, "claim_dao", self.dao, sender=ADMIN)
        r = D.call(D.rg, "appeal", cid, APPEAL_TEXT, right, sender=ADMIN, value=BOND)
        self.assertTrue(r["ok"], r)

    def test_r4_05_the_switch_launders_a_double_payment(self):
        # Two passed votes on one grant (temp check, then the final vote, as
        # many DAOs run). Alice is paid 100,000 twice. Filed under the final
        # vote, the second payment is DEVIATES (the first counts). The DAO
        # answers by naming the temp check: only filings under the temp check
        # count there, none, so AS_VOTED, no slash.
        D = self.D
        D.call(D.rg, "claim_dao", self.dao, sender=CONTROLLER)
        D.call(D.rg, "pledge", self.dao, sender=CONTROLLER, value=10 * GEN)
        body = "Send 100,000 USDC to " + ALICE + "."
        temp = D.read_vote(F.proposal(body, title="[Temp check] Alice grant", start=NOW - 40 * DAY, end=NOW - 35 * DAY))
        final = D.read_vote(F.proposal(body, title="Alice grant"))
        tx1, n1 = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(100_000)), nonce=61, block_ts=NOW - 5 * DAY)
        c1 = D.file(self.dao, D.read_exec(tx1, n1), final)["check_id"]
        D.judge_rule(c1)
        self.assertEqual(D.view(D.rg, "get_check", c1)["ruling"], "AS_VOTED")
        tx2, n2 = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(100_000)), nonce=62, block_ts=NOW - 4 * DAY)
        c2 = D.file(self.dao, D.read_exec(tx2, n2), final, sender=FILER2)["check_id"]
        D.judge_rule(c2)
        self.assertEqual(D.view(D.rg, "get_check", c2)["ruling"], "DEVIATES")
        D.call(D.rg, "appeal", c2, APPEAL_TEXT, temp, sender=CONTROLLER, value=BOND)
        D.judge_rule(c2)
        self.assertNotEqual(D.view(D.rg, "get_check", c2)["final_verdict"], "AS_VOTED")


class Caps(R4):
    def test_r4_06_an_amendment_off_the_recipients_line_is_ignored(self):
        # The cap must sit on the recipient's own line; an amount elsewhere
        # that names no address is not even a second candidate.
        body = ("Send 100,000 USDC to " + ALICE + ".\n\n"
                "Amendment (made before the vote opened): the grant above is reduced to 5,000 USDC.")
        self.assertNotEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(100_000))), "AS_VOTED")

    def test_r4_07_a_refusal_in_a_nested_bullet_is_ignored(self):
        # Negation is read per sentence of the amount's own line; the status
        # sub-bullet under it is another line.
        body = ("Applications:\n"
                "- Bob " + BOB + ": 100,000 USDC\n"
                "  - Status: rejected by the committee\n"
                "- Alice " + ALICE + ": 5,000 USDC\n"
                "  - Status: approved")
        self.assertNotEqual(self.ruling(body, to=USDC, data=F.transfer(BOB, U(100_000))), "AS_VOTED")

    def test_r4_08_the_against_options_text_sets_the_cap(self):
        # Losing-choice text is only dropped when two or more choices
        # approve something. "Against" never does, so the text under the
        # Against heading still caps after For wins.
        body = ("## For\nSend 5,000 USDC to " + BOB + " for the new audit.\n\n"
                "## Against\nKeep the current auditor: " + ALICE + " is paid 100,000 USDC for another year.")
        self.assertNotEqual(self.ruling(body, to=USDC, data=F.transfer(ALICE, U(100_000))), "AS_VOTED")


class Names(R4):
    SNAP = FIN - 50_000

    def test_r4_09_non_ethereum_space_name_repointed_after_the_vote(self):
        # read_names checks the vote's snapshot only when the space votes on
        # Ethereum (snap = 0 otherwise). For a space on Optimism, the a21
        # attack works again: the name is repointed to Mallory after the vote,
        # Mallory is paid, AS_VOTED.
        D = self.D
        dao = D.list_dao(space_id="opdao.eth", network="10")
        F.ens(D.mc, "grants.opdao.eth", MALLORY)
        F.ens(D.mc, "grants.opdao.eth", ALICE, block=self.SNAP)
        vid = D.read_vote(F.proposal("Send 5 USDC to grants.opdao.eth", space="opdao.eth", network="10"))
        tx, n = F.safe_exec(D.mc, USDC, 0, F.transfer(MALLORY, U(5)), nonce=70)
        r = D.file(dao, D.read_exec(tx, n), vid)
        self.assertTrue(r["ok"], r)
        D.judge_rule(r["check_id"])
        self.assertNotEqual(D.view(D.rg, "get_check", r["check_id"])["ruling"], "AS_VOTED")

    def test_r4_10_recipient_repoints_before_the_execution_and_a_correct_payment_deviates(self):
        # alice.eth was Alice at the vote; Alice repoints it before the Safe
        # pays. The Safe pays the address voters saw. The name is dropped
        # (the two blocks disagree) and the payment is to "an address the
        # proposal does not mention": code-settled NOT_AUTHORIZED, MAJOR
        # slash, and an appeal re-reads the same names.
        F.ens(self.D.mc, "alice.eth", F.addr(0xa11cf))
        F.ens(self.D.mc, "alice.eth", ALICE, block=self.SNAP)
        c = self.judged("Send 5 USDC to alice.eth", to=USDC, data=F.transfer(ALICE, U(5)))[2]
        self.assertNotEqual(c["ruling"], "DEVIATES")


class Badge(R4):
    def test_r4_11_one_signer_gets_the_verified_badge_for_a_rogue_space(self):
        # verified = the space's ENS owner is the Safe or ANY one of its
        # owners. One signer of a 3-owner Safe registers a look-alike name,
        # lists the real Safe under it and gets the badge.
        D = self.D
        node = F.VR.namehash("acme-dao.eth").hex()
        D.mc.calls[(F.VR.ENS_REGISTRY, "0x02571be3" + node)] = "0x" + "0" * 24 + MALLORY[2:]
        owners = [ADMIN, CONTROLLER, MALLORY]
        D.mc.calls[(SAFE, "0xa0e67e2b")] = "0x" + ("%064x" % 32) + ("%064x" % 3) + "".join("0" * 24 + o[2:] for o in owners)
        F.space("acme-dao.eth", treasuries=[[SAFE, "1"]], controllers=[MALLORY])
        D.call(D.vr, "read_space", "acme-dao.eth", "ethereum", SAFE)
        dao = D.call(D.rg, "list_dao", "acme-dao.eth", "ethereum", SAFE)["dao_id"]
        self.assertFalse(D.view(D.rg, "get_dao", dao)["verified"])


if __name__ == "__main__":
    unittest.main()
