"""Offline suite for the six AsVoted contracts.

    cd test && python3 -m unittest -q test_asvoted
"""
import json
import unittest
from pathlib import Path

import fixtures as F
import stub
import world
from fixtures import (ER, VR, JG, RG, SAFE, OTHER_SAFE, USDC, COW, WETH, ALICE, BOB, MALLORY, TARGET, MS130,
                      MSCO130, FILER, FILER2, CONTROLLER, ADMIN, STRANGER, SPACE, STAKE, BOND, GEN, DAY, NOW, FIN)

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("stole", "steal", "fraud", "malicious", "theft", "scam", "guaranteed", "100%")


def U(n, dec=6):
    return n * 10 ** dec


def model_says(verdict, quote):
    def ans(prompt, n):
        out = []
        k = prompt.find("action ")
        while k >= 0:
            j = k + 7
            num = ""
            while j < len(prompt) and prompt[j].isdigit():
                num += prompt[j]
                j += 1
            if num != "" and prompt[j:j + 1] == ":":
                out.append({"i": int(num), "verdict": verdict, "quote": quote})
            k = prompt.find("action ", k + 1)
        return {"actions": out}
    return ans


class Base(unittest.TestCase):
    mode = "DEMO"

    def setUp(self):
        self.D = F.Deployment(self.mode)
        self.dao = self.D.list_dao()

    def flow(self, body, txs=None, data=None, to=None, op=0, value=0, vote_kw=None, exec_kw=None, note="n"):
        """Pins a proposal and an execution, reads both, files a check."""
        D = self.D
        cid = F.proposal(body, **(vote_kw or {}))
        if txs is not None:
            to, op, data = MSCO130, 1, F.multisend(txs)
        tx, n = F.safe_exec(D.mc, to, value, data, op=op, **(exec_kw or {}))
        eid = D.read_exec(tx, n)
        vid = D.read_vote(cid)
        r = D.file(self.dao, eid, vid, note)
        self.assertTrue(r["ok"], r)
        return r["check_id"], tx

    def judged(self, *a, **k):
        cid, tx = self.flow(*a, **k)
        j, r = self.D.judge_rule(cid)
        return cid, j, self.D.view(self.D.rg, "get_check", cid)

    def outcomes(self, check):
        return [a["outcome"] for a in check["ruling_detail"]["actions"]]

    def assertLedger(self):
        L = self.D.ledger()
        self.assertTrue(L["invariant_holds"], L)
        self.assertTrue(L["views_match_storage"], L)
        self.assertEqual(int(L["on_chain_balance"]) - int(L["held_now"]), 0, L)
        return L


# =============================================================================
# pure helpers
# =============================================================================

class TestPure(unittest.TestCase):
    def test_keccak_vectors(self):
        self.assertEqual(ER.keccak256(b"").hex(), "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")
        self.assertEqual(ER.keccak256(b"ExecutionSuccess(bytes32,uint256)").hex(), ER.TOPIC_SUCCESS[2:])
        self.assertEqual(ER.keccak256(b"a" * 135).hex(), ER.keccak256(b"a" * 135).hex())
        self.assertEqual(ER.keccak256(b"transfer(address,uint256)")[:4].hex(), "a9059cbb")

    def test_safe_tx_hash_real(self):
        # Aura Treasury Safe nonce 85 (Safe Transaction Service, mainnet)
        e = {"to": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "value": 0,
             "data": bytes.fromhex("a9059cbb0000000000000000000000005fea4413e3cc5cf3a29a49db41ac0c24850417a0"
                                   "00000000000000000000000000000000000000000000000dc48a835874561948"),
             "operation": 0, "safeTxGas": 0, "baseGas": 0, "gasPrice": 0, "gasToken": ER.ZERO, "refundReceiver": ER.ZERO}
        hs = ER.safe_tx_hashes(1, "0xfc78f8e1af80a3bf5a1783bb59ed2d1b10f78ca9", e, 85)
        self.assertEqual(hs[0], "0x379e3a9cf2fd24c81a54396b869a57b4f108ecb0236417b645ba342dc21a3a59")

    def test_cid(self):
        body = b'{"x":1}'
        cid = F.cid_raw(body)
        pc = VR.parse_cid(cid)
        self.assertTrue(VR.cid_matches(pc, body))
        self.assertFalse(VR.cid_matches(pc, body + b" "))
        self.assertIn("error", VR.parse_cid(cid.upper()))
        self.assertIn("error", VR.parse_cid(" " + cid))

    def test_amounts(self):
        A = JG.amounts_in
        self.assertEqual(A("Send 50,000 USDC to x"), [[5, 50000, 0, "USDC"]])
        self.assertEqual(A("$50,000 for grants")[0][3], "USD")
        self.assertEqual(A("USDC 25,000 to x")[0][1:], [25000, 0, "USDC"])
        self.assertEqual(A("1.5M COW")[0][1:], [15000000, 1, "COW"])
        self.assertEqual(A("2 million OP")[0][1:], [2000000, 0, "OP"])
        self.assertEqual(A("**50,000** USDC")[0][3], "USDC")
        self.assertEqual(A("CIP-48 on 2024-07-29 at 10:30, 50% of 5 signers"), [])
        self.assertEqual(A("40.203 wETH")[0][1:], [40203, 3, "WETH"])

    def test_addresses_and_ens(self):
        t = "pay " + ALICE + ", not x" + BOB[2:] + " nor " + MALLORY + "ff"
        m = JG.address_mentions(t)
        self.assertIn(ALICE, m)
        self.assertNotIn(BOB, m)
        self.assertNotIn(MALLORY, m)
        self.assertEqual(VR.ens_names("Pay alice.eth and Bob.ETH, not me@carol.eth or dave.eth.xyz"), ["alice.eth", "bob.eth"])

    def test_outcome(self):
        o = VR.outcome_of
        self.assertEqual(o("basic", ["For", "Against", "Abstain"], [10, 5, 1], 16, 0, "default")["outcome"], "PASSED")
        self.assertEqual(o("basic", ["For", "Against", "Abstain"], [5, 10, 1], 16, 0, "default")["outcome"], "FAILED")
        self.assertEqual(o("basic", ["For", "Against", "Abstain"], [10, 5, 1], 16, 100, "default")["outcome"], "FAILED")
        self.assertEqual(o("single-choice", ["Yes, fund it", "No"], [10, 5], 15, 0, "")["outcome"], "PASSED")
        self.assertEqual(o("single-choice", ["Yes", "Do not fund"], [1, 5], 6, 0, "")["outcome"], "FAILED")
        self.assertEqual(o("single-choice", ["Option A", "Option B"], [10, 5], 15, 0, "")["outcome"], "UNCLEAR")
        self.assertEqual(o("single-choice", ["Yes", "No"], [5, 5], 10, 0, "")["outcome"], "UNCLEAR")
        self.assertEqual(o("weighted", ["Yes", "No"], [5, 1], 6, 0, "")["outcome"], "UNCLEAR")
        self.assertEqual(o("basic", ["For", "Against", "Abstain"], [10, 5, 1], 16, 0, "rejection")["outcome"], "UNCLEAR")

    def test_shared_block_identical(self):
        import subprocess
        r = subprocess.run(["python3", str(ROOT / "tools" / "inline_shared.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


# =============================================================================
# ExecReader
# =============================================================================

class TestExecReader(unittest.TestCase):
    def setUp(self):
        self.D = F.Deployment()

    def read(self, tx, n, **k):
        return self.D.read_exec(tx, n, **k)

    def test_direct_transfer(self):
        tx, n = F.safe_exec(self.D.mc, USDC, 0, F.transfer(ALICE, U(5)))
        x = self.D.view(self.D.er, "get_execution", self.read(tx, n))
        a = x["actions"]
        self.assertEqual(len(a), 1)
        self.assertEqual((a[0]["kind"], a[0]["recipient"], a[0]["amount"], a[0]["token"]),
                         ("erc20_transfer", ALICE, str(U(5)), USDC))
        self.assertEqual(x["tokens"][USDC], {"symbol": "USDC", "decimals": 6})

    def test_multisend_every_inner_call(self):
        data = F.multisend([(0, USDC, 0, F.transfer(ALICE, 1)), (0, BOB, 5, b""),
                            (0, COW, 0, F.approve(BOB, 7)), (0, WETH, 0, F.transfer_from(ALICE, BOB, 9)),
                            (0, TARGET, 0, bytes.fromhex("deadbeef") + F.wa(MALLORY))])
        tx, n = F.safe_exec(self.D.mc, MSCO130, 0, data, op=1)
        a = self.D.view(self.D.er, "get_execution", self.read(tx, n))["actions"]
        self.assertEqual([x["kind"] for x in a], ["erc20_transfer", "native", "erc20_approve", "erc20_transfer_from", "call"])
        self.assertEqual(a[4]["addr_args"], [MALLORY])
        self.assertEqual(a[0]["batch"], "MultiSendCallOnly 1.3.0")

    def test_nested_multisend_and_delegatecall_flagged(self):
        inner = F.multisend([(0, USDC, 0, F.transfer(ALICE, 1))])
        data = F.multisend([(1, MS130, 0, inner), (1, TARGET, 0, b"\x12\x34\x56\x78")])
        tx, n = F.safe_exec(self.D.mc, MS130, 0, data, op=1)
        a = self.D.view(self.D.er, "get_execution", self.read(tx, n))["actions"]
        self.assertEqual([(x["kind"], x["path"]) for x in a], [("erc20_transfer", "0.0.0"), ("delegatecall", "0.1")])
        self.assertEqual(a[1]["op"], "DELEGATECALL")

    def test_fake_multisend_is_a_delegatecall(self):
        data = F.multisend([(0, USDC, 0, F.transfer(ALICE, 1))])
        tx, n = F.safe_exec(self.D.mc, TARGET, 0, data, op=1)
        a = self.D.view(self.D.er, "get_execution", self.read(tx, n))["actions"]
        self.assertEqual([x["kind"] for x in a], ["delegatecall"])

    def test_call_only_with_inner_delegatecall_refused(self):
        data = F.multisend([(1, USDC, 0, F.transfer(ALICE, 1))])
        tx, n = F.safe_exec(self.D.mc, MSCO130, 0, data, op=1)
        with self.assertRaisesRegex(world.Reverted, "BATCH_MALFORMED"):
            self.read(tx, n)

    def test_wrong_nonce_refused(self):
        tx, n = F.safe_exec(self.D.mc, USDC, 0, F.transfer(ALICE, 1))
        with self.assertRaisesRegex(world.Reverted, "SAFE_TX_HASH_MISMATCH"):
            self.read(tx, n + 1)

    def test_old_domain_and_indexed_topic(self):
        tx, n = F.safe_exec(self.D.mc, USDC, 0, F.transfer(ALICE, 1), old_domain=True, indexed=True)
        self.assertGreater(self.read(tx, n), 0)

    def test_not_direct_reverted_failed(self):
        tx, n = F.safe_exec(self.D.mc, USDC, 0, F.transfer(ALICE, 1), tx_to=TARGET)
        with self.assertRaisesRegex(world.Reverted, "NOT_A_DIRECT_CALL_TO_THE_SAFE"):
            self.read(tx, n)
        tx, n = F.safe_exec(self.D.mc, USDC, 0, F.transfer(ALICE, 1), ok=False)
        with self.assertRaisesRegex(world.Reverted, "TX_REVERTED"):
            self.read(tx, n)
        tx, n = F.safe_exec(self.D.mc, USDC, 0, F.transfer(ALICE, 1), safe_ok=False)
        with self.assertRaisesRegex(world.Reverted, "SAFE_EXECUTION_FAILED"):
            self.read(tx, n)

    def test_not_finalized(self):
        tx, n = F.safe_exec(self.D.mc, USDC, 0, F.transfer(ALICE, 1), block=FIN + 5)
        with self.assertRaisesRegex(world.Reverted, "TX_NOT_FINALIZED_YET"):
            self.read(tx, n)

    def test_rpc_disagreement_refused(self):
        a, b = F.chain("ethereum", same=False)
        F.tokens(a)
        F.tokens(b)
        tx, n = F.safe_exec(a, USDC, 0, F.transfer(ALICE, 1))
        b.set_block(FIN - 1000, a.blocks[FIN - 1000][1])
        b.txs[tx] = dict(a.txs[tx])
        b.receipts[tx] = dict(a.receipts[tx])
        b.txs[tx]["input"] = a.txs[tx]["input"][:-2] + "ff"
        with self.assertRaisesRegex(world.Reverted, "RPC_DISAGREE"):
            self.read(tx, n)

    def test_duplicate_read_refused(self):
        tx, n = F.safe_exec(self.D.mc, USDC, 0, F.transfer(ALICE, 1))
        self.read(tx, n)
        with self.assertRaisesRegex(world.Reverted, "ALREADY_READ_AS_1"):
            self.read(tx, n)

    def test_gas_refund_is_an_action(self):
        tx, n = F.safe_exec(self.D.mc, USDC, 0, F.transfer(ALICE, 1), gas_price=1, payment=12345, refund=BOB)
        a = self.D.view(self.D.er, "get_execution", self.read(tx, n))["actions"]
        self.assertEqual((a[-1]["kind"], a[-1]["recipient"], a[-1]["amount"]), ("gas_refund", BOB, "12345"))

    def test_leader_naming_an_old_block_is_rejected(self):
        tx, n = F.safe_exec(self.D.mc, USDC, 0, F.transfer(ALICE, 1), block=FIN - 5000)
        old = FIN - 3000
        self.D.mc.set_block(old, F.FIN_TS - 7200)
        stub.FORGE["mutate"] = lambda r: (r.__setitem__("pinned", {"number": old, "hash": self.D.mc.blocks[old][0],
                                                                    "timestamp": F.FIN_TS - 7200}) or r)
        try:
            with self.assertRaisesRegex(world.Reverted, "UNDETERMINED"):
                self.read(tx, n)
        finally:
            stub.FORGE["mutate"] = None
        self.assertEqual(self.D.view(self.D.er, "get_config")["executions"], 0)


# =============================================================================
# VoteReader
# =============================================================================

class TestVoteReader(unittest.TestCase):
    def setUp(self):
        self.D = F.Deployment()

    def test_happy_and_binding(self):
        cid = F.proposal("Send 10 USDC to " + ALICE)
        v = self.D.view(self.D.vr, "get_proposal", self.D.read_vote(cid))
        self.assertEqual((v["outcome"], v["listed"], v["space"]), ("PASSED", True, SPACE))
        cid2 = F.proposal("x", treasuries=[[OTHER_SAFE, "1"]])
        v2 = self.D.view(self.D.vr, "get_proposal", self.D.read_vote(cid2))
        self.assertFalse(v2["listed"])

    def test_gateway_serving_other_bytes_refused(self):
        cid = F.proposal("Send 10 USDC to " + ALICE)
        for g in VR.IPFS_GATEWAYS:
            stub.WEB.pages[g + cid] = (200, b'{"tampered": true}')
        with self.assertRaisesRegex(world.Reverted, "IPFS_CONTENT_DOES_NOT_MATCH_CID"):
            self.D.read_vote(cid)

    def test_hub_body_differs_refused(self):
        cid = F.proposal("Send 10 USDC to " + ALICE, hub_body="Send 10 USDC to " + MALLORY)
        with self.assertRaisesRegex(world.Reverted, "HUB_RECORD_DIFFERS_FROM_IPFS"):
            self.D.read_vote(cid)

    def test_edited_proposal_old_cid_refused(self):
        cid = F.proposal("Send 10 USDC to " + ALICE, hub_ipfs="bafkreiaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        with self.assertRaisesRegex(world.Reverted, "HUB_RECORD_DIFFERS_FROM_IPFS|CID_IS_NOT"):
            self.D.read_vote(cid)

    def test_not_closed_not_final(self):
        with self.assertRaisesRegex(world.Reverted, "PROPOSAL_NOT_CLOSED"):
            self.D.read_vote(F.proposal("a", state="active"))
        with self.assertRaisesRegex(world.Reverted, "SCORES_NOT_FINAL"):
            self.D.read_vote(F.proposal("b", scores_state="pending"))

    def test_ens_counted_only_if_stable(self):
        F.ens(self.D.mc, "alice.eth", ALICE)
        F.ens(self.D.mc, "bob.eth", BOB)
        F.ens(self.D.mc, "bob.eth", MALLORY, block=FIN - 50_000)       # bob.eth pointed elsewhere at the vote
        v = self.D.view(self.D.vr, "get_proposal", self.D.read_vote(F.proposal("Pay alice.eth and bob.eth")))
        self.assertEqual(v["ens"], {"alice.eth": ALICE})

    def test_reread_cooldown(self):
        cid = F.proposal("x")
        self.D.read_vote(cid)
        with self.assertRaisesRegex(world.Reverted, "READ_RECENTLY"):
            self.D.read_vote(cid)
        self.D.w.advance(VR.REREAD_S + 1)
        self.assertEqual(self.D.read_vote(cid), 2)


# =============================================================================
# Judge rules, through the registry
# =============================================================================

class TestJudge(Base):
    def test_as_voted(self):
        body = "Send 50,000 USDC to " + ALICE + ".\n\nSend 10 WETH to " + BOB + "."
        cid, j, c = self.judged(body, txs=[(0, USDC, 0, F.transfer(ALICE, U(50_000))),
                                           (0, WETH, 0, F.transfer(BOB, 10 * GEN))])
        self.assertEqual(c["ruling"], "AS_VOTED")
        self.assertEqual(self.outcomes(c), ["AUTHORIZED", "AUTHORIZED"])
        self.assertEqual(len(stub.MODEL.prompts), 0)

    def test_recipient_not_mentioned(self):
        cid, j, c = self.judged("Send 50,000 USDC to " + ALICE, to=USDC, data=F.transfer(MALLORY, U(50_000)))
        self.assertEqual((c["ruling"], self.outcomes(c)), ("DEVIATES", ["NOT_AUTHORIZED"]))
        self.assertIn("does not mention", c["ruling_summary"])
        self.assertEqual(c["severity"], "MAJOR")

    def test_over_amount_and_tolerance(self):
        cid, j, c = self.judged("Send 50,000 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(50_200)))
        self.assertEqual(self.outcomes(c), ["AUTHORIZED"])          # +0.4% is inside the 0.5% tolerance
        self.setUp()
        cid, j, c = self.judged("Send 50,000 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(60_000)))
        self.assertEqual((c["ruling"], self.outcomes(c), c["severity"]), ("DEVIATES", ["OVER_AMOUNT"], "MAJOR"))

    def test_split_transfers_are_summed(self):
        txs = [(0, USDC, 0, F.transfer(ALICE, U(30_000))), (0, USDC, 0, F.transfer(ALICE, U(30_000)))]
        cid, j, c = self.judged("Send 50,000 USDC to " + ALICE, txs=txs)
        self.assertEqual(self.outcomes(c), ["OVER_AMOUNT", "OVER_AMOUNT"])

    def test_cap_is_shared_across_executions_of_one_proposal(self):
        D = self.D
        body = "Send 50,000 USDC to " + ALICE
        cid = F.proposal(body)
        vid = D.read_vote(cid)
        tx1, n1 = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(50_000)), nonce=7)
        tx2, n2 = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(50_000)), nonce=8)
        c1 = D.file(self.dao, D.read_exec(tx1, n1), vid)["check_id"]
        c2 = D.file(self.dao, D.read_exec(tx2, n2), vid, sender=FILER2)["check_id"]
        D.judge_rule(c1)
        D.judge_rule(c2)
        self.assertEqual(D.view(D.rg, "get_check", c1)["ruling"], "AS_VOTED")
        k2 = D.view(D.rg, "get_check", c2)
        self.assertEqual((k2["ruling"], k2["prior_exec_ids"]), ("DEVIATES", [1]))
        self.assertIn("earlier executions", k2["ruling_detail"]["actions"][0]["reason"])

    def test_stablecoins_of_different_decimals_add_up(self):
        txs = [(0, USDC, 0, F.transfer(ALICE, U(30_000))), (0, F.addr(0xda1), 0, F.transfer(ALICE, 30_000 * GEN))]
        F.tokens(self.D.mc, {F.addr(0xda1): ("DAI", 18)})
        cid, j, c = self.judged("Grant of $50,000 to " + ALICE, txs=txs)
        self.assertEqual(self.outcomes(c), ["OVER_AMOUNT", "OVER_AMOUNT"])

    def test_other_token_for_the_recipient(self):
        body = "Send 100 USDC to " + ALICE + "\n\nSend 100 COW to " + BOB
        cid, j, c = self.judged(body, txs=[(0, COW, 0, F.transfer(ALICE, 100 * GEN)), (0, USDC, 0, F.transfer(BOB, U(100)))])
        self.assertEqual(self.outcomes(c), ["OVER_AMOUNT", "OVER_AMOUNT"])

    def test_usd_only_for_a_volatile_token_is_unclear(self):
        cid, j, c = self.judged("Pay " + ALICE + " $500 per epoch, half in COW", to=COW, data=F.transfer(ALICE, 900 * GEN))
        self.assertEqual(self.outcomes(c), ["UNCLEAR"])

    def test_no_amount_stated_is_unclear(self):
        cid, j, c = self.judged("Fund " + ALICE + " and " + BOB + " for their work.", to=USDC, data=F.transfer(ALICE, U(5)))
        self.assertEqual((c["ruling"], c["status"]), ("UNCLEAR", "FINAL"))

    def test_usd_amounts_cover_stablecoins(self):
        cid, j, c = self.judged("Grant of $25,000 to " + ALICE, to=USDC, data=F.transfer(ALICE, U(25_000)))
        self.assertEqual(c["ruling"], "AS_VOTED")

    def test_delegatecall_not_named(self):
        cid, j, c = self.judged("Send 1 USDC to " + ALICE, to=TARGET, op=1, data=b"\x12\x34\x56\x78")
        self.assertEqual((c["ruling"], c["severity"]), ("DEVIATES", "CRITICAL"))

    def test_call_to_unidentified_contract(self):
        cid, j, c = self.judged("Upgrade the staking contract.", to=TARGET, data=b"\x36\x59\xcf\xe6" + F.wa(ALICE))
        self.assertEqual((c["ruling"], self.outcomes(c)), ("DEVIATES", ["NOT_AUTHORIZED"]))

    def test_call_with_unmentioned_address_argument(self):
        body = "Call setRecipient on " + TARGET + " to route fees."
        cid, j, c = self.judged(body, to=TARGET, data=b"\xaa\xbb\xcc\xdd" + F.wa(MALLORY))
        self.assertIn("passes the address", c["ruling_detail"]["actions"][0]["reason"])

    def test_exact_calldata_quoted_in_proposal(self):
        data = b"\x02\xa8\x61\xa6" + F.wa(MALLORY) + F.w(5)
        body = "Execution: to " + TARGET + ' data: "0x' + data.hex() + '"'
        cid, j, c = self.judged(body, to=TARGET, data=data)
        self.assertEqual((c["ruling"], c["ruling_detail"]["actions"][0]["basis"]), ("AS_VOTED", "code"))
        self.assertEqual(len(stub.MODEL.prompts), 0)

    def test_model_settles_described_call(self):
        q = "Call pause() on " + TARGET + " until the audit is done"
        stub.MODEL.answer = model_says("AUTHORIZED", q)
        cid, j, c = self.judged(q + ".", to=TARGET, data=bytes.fromhex("8456cb59"))
        self.assertEqual((c["ruling"], c["ruling_detail"]["actions"][0]["basis"]), ("AS_VOTED", "model"))

    def test_model_quote_not_in_text_is_unclear(self):
        stub.MODEL.answer = model_says("AUTHORIZED", "the DAO approves everything the signers do")
        cid, j, c = self.judged("Call pause() on " + TARGET + ".", to=TARGET, data=bytes.fromhex("8456cb59"))
        self.assertEqual(c["ruling"], "UNCLEAR")

    def test_model_samples_disagreeing_is_unclear(self):
        q = "Call pause() on " + TARGET + " now"
        stub.MODEL.answer = lambda p, n: model_says("AUTHORIZED" if n % 2 else "NOT_AUTHORIZED", q)(p, n)
        cid, j, c = self.judged(q, to=TARGET, data=bytes.fromhex("8456cb59"))
        self.assertEqual(c["ruling"], "UNCLEAR")

    def test_validator_disagreement_writes_nothing(self):
        q = "Call pause() on " + TARGET + " now"
        stub.MODEL.answer = lambda p, n: model_says("AUTHORIZED" if n <= 2 else "NOT_AUTHORIZED", q)(p, n)
        cid, tx = self.flow(q, to=TARGET, data=bytes.fromhex("8456cb59"))
        with self.assertRaisesRegex(world.Reverted, "UNDETERMINED"):
            self.D.call(self.D.jg, "judge", self.D.rg, cid)
        self.assertEqual(self.D.view(self.D.jg, "get_judgments", 0, 10)["total"], 0)
        self.assertEqual(self.D.view(self.D.rg, "get_check", cid)["status"], "PROVISIONAL")

    def test_unlimited_approval(self):
        cid, j, c = self.judged("Approve " + ALICE + " to spend 1,000 USDC", to=USDC, data=F.approve(ALICE, 2 ** 256 - 1))
        self.assertEqual(self.outcomes(c), ["OVER_AMOUNT"])
        self.setUp()
        cid, j, c = self.judged("Give " + ALICE + " an unlimited approval on USDC", to=USDC, data=F.approve(ALICE, 2 ** 256 - 1))
        self.assertEqual(self.outcomes(c), ["AUTHORIZED"])

    def test_ens_recipient(self):
        F.ens(self.D.mc, "alice.eth", ALICE)
        cid, j, c = self.judged("Send 5,000 USDC to alice.eth", to=USDC, data=F.transfer(ALICE, U(5_000)))
        self.assertEqual(c["ruling"], "AS_VOTED")

    def test_unsupported_vote_type_is_unclear(self):
        cid, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)),
                                vote_kw={"vtype": "weighted", "choices": ["Yes", "No"], "scores": [9.0, 1.0]})
        self.assertEqual(c["ruling"], "UNCLEAR")
        self.assertIn("unclear", c["ruling_summary"])

    def test_wording_is_neutral_and_dated(self):
        for body, data in (("Send 5 USDC to " + ALICE, F.transfer(MALLORY, U(5))),
                           ("Send 5 USDC to " + ALICE, F.transfer(ALICE, U(9))),
                           ("Send 5 USDC to " + ALICE, F.transfer(ALICE, U(5)))):
            self.setUp()
            cid, j, c = self.judged(body, to=USDC, data=data)
            s = c["ruling_summary"].lower()
            for w in FORBIDDEN:
                self.assertNotIn(w, s)
            self.assertRegex(s, r"20\d\d-\d\d-\d\d")


# =============================================================================
# Registry lifecycle and money
# =============================================================================

class TestRegistry(Base):
    def test_listing_requires_treasury_binding(self):
        F.space("other.eth", treasuries=[[OTHER_SAFE, "137"]])
        self.D.call(self.D.vr, "read_space", "other.eth", "ethereum", OTHER_SAFE)
        with self.assertRaisesRegex(world.Reverted, "SAFE_NOT_LISTED"):
            self.D.call(self.D.rg, "list_dao", "other.eth", "ethereum", OTHER_SAFE)
        with self.assertRaisesRegex(world.Reverted, "NO_BINDING_READ"):
            self.D.call(self.D.rg, "list_dao", "nobody.eth", "ethereum", OTHER_SAFE)
        with self.assertRaisesRegex(world.Reverted, "ALREADY_LISTED"):
            self.D.call(self.D.rg, "list_dao", SPACE, "ethereum", SAFE)

    def test_binding_must_be_fresh(self):
        F.space("late.eth", treasuries=[[OTHER_SAFE, "1"]])
        self.D.call(self.D.vr, "read_space", "late.eth", "ethereum", OTHER_SAFE)
        self.D.w.advance(3601)
        with self.assertRaisesRegex(world.Reverted, "BINDING_TOO_OLD"):
            self.D.call(self.D.rg, "list_dao", "late.eth", "ethereum", OTHER_SAFE)

    def test_unauthorized_claim_refused(self):
        self.D.w.advance(VR.REREAD_S + 1)
        self.D.call(self.D.vr, "read_space", SPACE, "ethereum", SAFE)
        with self.assertRaisesRegex(world.Reverted, "NOT_AN_ADMIN"):
            self.D.call(self.D.rg, "claim_dao", self.dao, sender=STRANGER)
        self.assertEqual(self.D.call(self.D.rg, "claim_dao", self.dao, sender=ADMIN)["controller"], ADMIN)
        with self.assertRaisesRegex(world.Reverted, "ALREADY_CLAIMED"):
            self.D.call(self.D.rg, "claim_dao", self.dao, sender=CONTROLLER)

    def test_pledge_by_non_controller_is_credited_back(self):
        r = self.D.call(self.D.rg, "pledge", self.dao, sender=STRANGER, value=GEN)
        self.assertFalse(r["ok"])
        self.assertEqual(self.D.view(self.D.rg, "claimable_of", STRANGER)["claimable"], str(GEN))
        self.assertLedger()

    def test_filing_refusals_refund(self):
        D = self.D
        cid = F.proposal("Send 5 USDC to " + ALICE)
        tx, n = F.safe_exec(D.mc, USDC, 0, F.transfer(ALICE, U(5)))
        eid = D.read_exec(tx, n)
        vid = D.read_vote(cid)
        self.assertIn("STAKE_MUST_BE", D.file(self.dao, eid, vid, value=STAKE - 1)["reason"])
        early = F.proposal("Send 5 USDC to " + ALICE, end=F.FIN_TS - 60)          # vote ended after the execution
        self.assertEqual(D.file(self.dao, eid, D.read_vote(early))["reason"], "EXECUTED_BEFORE_THE_VOTE_ENDED")
        failed = F.proposal("Send 5 USDC to " + ALICE, scores=[1.0, 9.0, 0.0])
        self.assertEqual(D.file(self.dao, eid, D.read_vote(failed))["reason"], "PROPOSAL_DID_NOT_PASS")
        other = F.proposal("Send 5 USDC to " + ALICE, space="other.eth")
        self.assertEqual(D.file(self.dao, eid, D.read_vote(other))["reason"], "PROPOSAL_IS_NOT_IN_THE_DAOS_SPACE")
        D.w.advance(3601)
        self.assertEqual(D.file(self.dao, eid, vid)["reason"], "PROPOSAL_RECORD_TOO_OLD_REREAD_IT")
        self.assertEqual(int(D.view(D.rg, "claimable_of", FILER)["claimable"]), 5 * STAKE - 1)
        self.assertLedger()

    def test_duplicate_and_replay_refused(self):
        cid, tx = self.flow("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)))
        D = self.D
        eid = D.view(D.er, "get_execution_id", "ethereum", SAFE, tx)
        vid = D.read_vote(F.proposal("Send 5 USDC to " + ALICE + " (second)"))
        self.assertEqual(D.file(self.dao, eid, vid, sender=FILER2)["reason"], "DUPLICATE_OF_CHECK_1")

    def test_as_voted_final_stake_to_pledge(self):
        cid, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)))
        with self.assertRaisesRegex(world.Reverted, "CONTESTABLE_UNTIL"):
            self.D.call(self.D.rg, "finalize", cid)
        self.D.w.advance(91)
        self.D.call(self.D.rg, "finalize", cid)
        self.assertEqual(self.D.view(self.D.rg, "get_dao", self.dao)["pledge"], str(STAKE))
        self.assertLedger()

    def pledge(self, amount=10 * GEN):
        self.D.call(self.D.rg, "claim_dao", self.dao, sender=CONTROLLER)
        self.assertTrue(self.D.call(self.D.rg, "pledge", self.dao, sender=CONTROLLER, value=amount)["ok"])

    def test_deviates_final_slashes_pledge(self):
        self.pledge()
        cid, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(MALLORY, U(5)))
        self.D.w.advance(91)
        self.D.call(self.D.rg, "finalize", cid)
        c = self.D.view(self.D.rg, "get_check", cid)
        self.assertEqual((c["final_verdict"], c["slash"], c["bounty_to"]), ("DEVIATES", str(10 * GEN * 2500 // 10000), FILER))
        self.assertEqual(self.D.view(self.D.rg, "claimable_of", FILER)["claimable"], str(STAKE + 25 * GEN // 10))
        self.assertLedger()

    def test_appeal_with_the_right_proposal_wins(self):
        self.pledge()
        D = self.D
        cid, tx = self.flow("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(BOB, U(5)))
        D.judge_rule(cid)
        self.assertEqual(D.view(D.rg, "get_check", cid)["ruling"], "DEVIATES")
        right = D.read_vote(F.proposal("Pay " + BOB + " 5 USDC for the audit.", title="Audit payment"))
        text = "This execution implements the audit payment proposal, which names the recipient and the amount."
        r = D.call(D.rg, "appeal", cid, text, right, sender=CONTROLLER, value=BOND)
        self.assertTrue(r["ok"], r)
        D.judge_rule(cid)
        c = D.view(D.rg, "get_check", cid)
        self.assertEqual((c["appeal_ruling"], c["final_verdict"], c["final_how"]), ("AS_VOTED", "AS_VOTED", "APPEAL_RULED"))
        self.assertEqual(D.view(D.rg, "claimable_of", CONTROLLER)["claimable"], str(BOND))
        self.assertLedger()

    def test_appeal_lost_bond_to_filer(self):
        self.pledge()
        D = self.D
        cid, tx = self.flow("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(BOB, U(5)))
        D.judge_rule(cid)
        text = "The signers agreed in the forum that Bob should be paid instead; please look again at this."
        D.call(D.rg, "appeal", cid, text, 0, sender=CONTROLLER, value=BOND)
        D.judge_rule(cid)
        c = D.view(D.rg, "get_check", cid)
        self.assertEqual(c["final_verdict"], "DEVIATES")
        self.assertEqual(int(D.view(D.rg, "claimable_of", FILER)["claimable"]), STAKE + BOND + int(c["slash"]))
        self.assertLedger()

    def test_appeal_rules(self):
        D = self.D
        cid, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(BOB, U(5)), note="bob is not in it")
        text = "x" * 10
        self.assertIn("COUNTER_EVIDENCE_LENGTH", D.call(D.rg, "appeal", cid, text, 0, sender=STRANGER, value=BOND)["reason"])
        self.assertEqual(D.call(D.rg, "appeal", cid, "long enough text " * 4, 0, sender=FILER, value=BOND)["reason"],
                         "THE_FILER_CANNOT_APPEAL_THEIR_OWN_DEVIATES")
        same = c["ruling_summary"] + " " + c["ruling_summary"]
        self.assertEqual(D.call(D.rg, "appeal", cid, same, 0, sender=STRANGER, value=BOND)["reason"], "COUNTER_EVIDENCE_NOT_NEW")
        D.w.advance(91)
        self.assertEqual(D.call(D.rg, "appeal", cid, "a genuinely new argument about the recipient " * 2, 0,
                                sender=STRANGER, value=BOND)["reason"], "CONTEST_WINDOW_CLOSED")
        self.assertLedger()

    def test_expiries(self):
        D = self.D
        cid, tx = self.flow("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)))
        with self.assertRaisesRegex(world.Reverted, "JUDGEABLE_UNTIL"):
            D.call(D.rg, "expire", cid)
        D.w.advance(601)
        D.call(D.jg, "judge", D.rg, cid)
        with self.assertRaisesRegex(world.Reverted, "JUDGED_AFTER_THE_DEADLINE"):
            D.call(D.rg, "rule", cid)
        r = D.call(D.rg, "expire", cid)
        self.assertEqual((r["final"], r["how"]), ("UNCLEAR", "EXPIRED_UNJUDGED"))
        self.assertLedger()
        # an appeal nobody judges: the ruling stands, the bond comes back
        cid2, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(6)))
        D.call(D.rg, "appeal", cid2, "The proposal's budget table allows six, see the second table row.", 0,
               sender=CONTROLLER, value=BOND)
        D.w.advance(601)
        r = D.call(D.rg, "expire", cid2)
        self.assertEqual((r["final"], r["how"]), ("DEVIATES", "APPEAL_EXPIRED"))
        self.assertLedger()

    def test_rule_needs_matching_evidence(self):
        D = self.D
        cid, tx = self.flow("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)))
        with self.assertRaisesRegex(world.Reverted, "NOT_JUDGED_YET"):
            D.call(D.rg, "rule", cid)
        with self.assertRaisesRegex(world.Reverted, "ALREADY_JUDGED"):
            D.call(D.jg, "judge", D.rg, cid)
            D.call(D.jg, "judge", D.rg, cid)

    def test_withdrawal(self):
        self.pledge(5 * GEN)
        D = self.D
        cid, tx = self.flow("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(ALICE, U(5)))
        with self.assertRaisesRegex(world.Reverted, "CHECKS_OPEN_1"):
            D.call(D.rg, "request_withdrawal", self.dao, str(5 * GEN), sender=CONTROLLER)
        D.judge_rule(cid)
        D.w.advance(91)
        D.call(D.rg, "finalize", cid)
        D.call(D.rg, "request_withdrawal", self.dao, str(5 * GEN + STAKE), sender=CONTROLLER)
        with self.assertRaisesRegex(world.Reverted, "WITHDRAWAL_LOCKED"):
            D.call(D.rg, "execute_withdrawal", self.dao, sender=STRANGER)
        D.w.advance(91)
        D.call(D.rg, "execute_withdrawal", self.dao, sender=STRANGER)
        D.call(D.rg, "claim", sender=CONTROLLER)
        L = self.assertLedger()
        self.assertEqual(L["held_now"], "0")

    def test_canonical_refuses_demo_controllers(self):
        w = world.new_world()
        with self.assertRaisesRegex(stub._UserError, "CANONICAL takes no demo controllers"):
            w.deploy("AsVotedRegistry", "CANONICAL", F.addr(1), F.addr(2), F.addr(3), CONTROLLER)


class TestCanonical(Base):
    mode = "CANONICAL"

    def test_windows_and_no_seam(self):
        cfg = self.D.view(self.D.rg, "get_config")
        self.assertEqual((cfg["contest_s"], cfg["demo_controllers"]), (3600, []))
        with self.assertRaisesRegex(world.Reverted, "NOT_AN_ADMIN"):
            self.D.call(self.D.rg, "claim_dao", self.dao, sender=CONTROLLER)


# =============================================================================
# consumers
# =============================================================================

class TestStanding(Base):
    def test_gate_refuses_after_final_deviates(self):
        D = self.D
        r = D.call(D.gate, "request_grant", self.dao, "tranche 1")
        self.assertTrue(r["carried_out"])
        cid, j, c = self.judged("Send 5 USDC to " + ALICE, to=USDC, data=F.transfer(MALLORY, U(5)))
        D.w.advance(91)
        D.call(D.rg, "finalize", cid)
        r = D.call(D.gate, "request_grant", self.dao, "tranche 2")
        self.assertFalse(r["carried_out"])
        self.assertIn("FINAL DEVIATES", r["reasons"][0])
        self.assertFalse(D.view(D.st, "is_executing_as_voted", self.dao, D.w.now()))
        self.assertTrue(D.view(D.st, "is_executing_as_voted", self.dao, D.w.now() + 31 * DAY))
        g = D.view(D.gate, "get_requests", 0, 10)
        self.assertEqual((g["carried_out"], g["refused"]), (1, 1))


# =============================================================================
# static checks
# =============================================================================

class TestStatic(unittest.TestCase):
    def test_no_write_before_revert(self):
        import subprocess
        r = subprocess.run(["python3", str(ROOT / "tools" / "scan_writes.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_undefined_names(self):
        for f in sorted((ROOT / "contracts").glob("*.py")):
            self.assertEqual(stub.undefined_names(f), [], f.name)

    def test_views_do_not_write(self):
        import ast
        for f in sorted((ROOT / "contracts").glob("*.py")):
            tree = ast.parse(f.read_text())
            for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
                for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
                    if not any(ast.unparse(d) == "gl.public.view" for d in fn.decorator_list):
                        continue
                    for n in ast.walk(fn):
                        if isinstance(n, (ast.Assign, ast.AugAssign)):
                            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                                self.assertFalse(ast.unparse(t).startswith("self."), f.name + "." + fn.name)
                        if isinstance(n, ast.Call) and ast.unparse(n.func).endswith(("run_nondet", "exec_prompt", "web.get", "web.request")):
                            self.fail(f.name + "." + fn.name + " calls " + ast.unparse(n.func))

    def test_no_replace_and_no_owner(self):
        for f in sorted((ROOT / "contracts").glob("*.py")):
            t = f.read_text()
            self.assertNotIn(".replace(", t, f.name)
            self.assertNotIn("owner_only", t)
            self.assertNotIn("def set_", t, f.name)


if __name__ == "__main__":
    unittest.main()
