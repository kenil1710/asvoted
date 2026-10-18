"""Builders for the offline suite: Safe executions (execTransaction calldata,
MultiSend batches, receipts with ExecutionSuccess) on mock chains, Snapshot
proposals pinned on mock IPFS gateways with hub rows and space settings, ENS
records, and a fully wired deployment (readers, judge, registry, standing,
gate)."""
import hashlib
import json

import stub
import world

ER = world.module("ExecReader")
VR = world.module("VoteReader")
JG = world.module("AsVotedJudge")
RG = world.module("AsVotedRegistry")

NOW_ISO = "2026-10-07T12:00:00Z"
NOW = ER._epoch_from_iso(NOW_ISO)
FIN = 20_000_000
FIN_TS = NOW - 900
DAY = 86400
GEN = 10 ** 18
STAKE = RG.CHECK_STAKE
BOND = RG.APPEAL_BOND


def addr(n):
    """A full-width test address (as real ones are), derived from n."""
    return "0x" + hashlib.sha256(b"addr%d" % n).hexdigest()[:40]


SAFE = addr(0x5afe)
OTHER_SAFE = addr(0x5aff)
USDC = addr(0x0dc0)
COW = addr(0xc0c0)
WETH = addr(0xeeee)
ALICE = addr(0xa11ce)
BOB = addr(0xb0b)
MALLORY = addr(0x3a11)
TARGET = addr(0x7a7)
EXECUTOR = addr(0xe0e0)
MS130 = "0xa238cbeb142c10ef7ad8442c6d1f9e89e07e7761"
MSCO130 = "0x40a2accbd92bca938b02010e17a5b8929b49130d"

FILER = addr(0xf11e)
FILER2 = addr(0xf11f)
CONTROLLER = addr(0xc0de)
ADMIN = addr(0xad31)
STRANGER = addr(0x5745)
MONITOR = addr(0x3017)          # the monitor whose coverage heartbeat DaoStanding counts
STALE_S = 6 * 3600

SPACE = "acme.eth"
TOKENS = {USDC: ("USDC", 6), COW: ("COW", 18), WETH: ("WETH", 18)}
DAI = addr(0xda1)
# the tokens the test judge identifies by symbol (the real deployment's list is in test/token_list.json)
TOKEN_LIST = {"ethereum": {USDC: "USDC", COW: "COW", WETH: "WETH", DAI: "DAI"}}


# --- ABI -------------------------------------------------------------------

def w(n):
    return int(n).to_bytes(32, "big")


def wa(a):
    return bytes(12) + bytes.fromhex(a[2:])


def dyn(b):
    pad = (32 - len(b) % 32) % 32
    return w(len(b)) + b + bytes(pad)


def transfer(to, amount):
    return bytes.fromhex("a9059cbb") + wa(to) + w(amount)


def transfer_from(frm, to, amount):
    return bytes.fromhex("23b872dd") + wa(frm) + wa(to) + w(amount)


def approve(spender, amount):
    return bytes.fromhex("095ea7b3") + wa(spender) + w(amount)


def call_with(sel_hex, *addrs_and_ints):
    out = bytes.fromhex(sel_hex)
    for x in addrs_and_ints:
        out += wa(x) if isinstance(x, str) else w(x)
    return out


def multisend(txs, call_only=False):
    """txs: [(op, to, value, data)] -> multiSend(bytes) calldata."""
    packed = b""
    for op, to, value, data in txs:
        packed += bytes([op]) + bytes.fromhex(to[2:]) + w(value) + w(len(data)) + data
    return bytes.fromhex("8d80ff0a") + w(32) + dyn(packed)


def exec_calldata(to, value, data, op, safe_tx_gas=0, base_gas=0, gas_price=0, gas_token=None,
                  refund=None, sigs=b"\x11" * 65):
    gas_token = gas_token or ER.ZERO
    refund = refund or ER.ZERO
    head_n = 10
    head = b""
    tail = b""
    off = 32 * head_n
    d1 = dyn(data)
    d2 = dyn(sigs)
    head += wa(to) + w(value) + w(off) + w(op) + w(safe_tx_gas) + w(base_gas) + w(gas_price) + wa(gas_token) + \
        wa(refund) + w(off + len(d1))
    tail = d1 + d2
    return bytes.fromhex("6a761202") + head + tail


# --- mock chains --------------------------------------------------------------

_orig_answer = stub.MockChain.answer


def _answer(self, req):
    m = req["method"]
    p = req["params"]
    if m == "eth_getTransactionByHash":
        return {"jsonrpc": "2.0", "id": req["id"], "result": getattr(self, "txs", {}).get(p[0].lower())}
    if m == "eth_getTransactionReceipt":
        return {"jsonrpc": "2.0", "id": req["id"], "result": getattr(self, "receipts", {}).get(p[0].lower())}
    return _orig_answer(self, req)


stub.MockChain.answer = _answer


def chain(name="ethereum", same=True):
    """A MockChain behind BOTH RPCs of `name` (or two separate ones)."""
    cid = ER.CHAINS[name][0]
    urls = ER.CHAINS[name][1]
    a = stub.MockChain(cid, FIN, FIN_TS)
    a.txs = {}
    a.receipts = {}
    a.batch_cap = 10
    stub.WEB.chains[urls[0]] = a
    if same:
        stub.WEB.chains[urls[1]] = a
        return a
    b = stub.MockChain(cid, FIN, FIN_TS)
    b.txs = {}
    b.receipts = {}
    stub.WEB.chains[urls[1]] = b
    return (a, b)


def tokens(mc, toks=None):
    toks = toks or TOKENS
    for t, (sym, dec) in toks.items():
        mc.code[t] = "0x6080"
        b = sym.encode()
        mc.calls[(t, "0x95d89b41")] = "0x" + ("%064x" % 32) + ("%064x" % len(b)) + b.hex().ljust(64, "0")
        mc.calls[(t, "0x313ce567")] = "0x" + ("%064x" % dec)


_TX_N = [0]


def safe_exec(mc, to, value, data, op=0, safe=SAFE, nonce=7, block=FIN - 1000, block_ts=None, ok=True,
              safe_ok=True, payment=0, gas_price=0, refund=None, indexed=False, old_domain=False, tx_to=None,
              wrong_hash=False, chain_name="ethereum"):
    """Mines one Safe execution on `mc`; returns (tx_hash, nonce)."""
    _TX_N[0] += 1
    tx_hash = "0x" + hashlib.sha256(b"tx%d" % _TX_N[0]).hexdigest()
    block_ts = block_ts if block_ts is not None else FIN_TS - 3600
    mc.set_block(block, block_ts)
    inp = exec_calldata(to, value, data, op, gas_price=gas_price, refund=refund)
    e = ER.decode_exec(inp)
    hashes = ER.safe_tx_hashes(ER.CHAINS[chain_name][0], safe, e, nonce)
    sth = hashes[1] if old_domain else hashes[0]
    if wrong_hash:
        sth = "0x" + "ab" * 32
    bh = mc.blocks[block][0]
    mc.txs[tx_hash] = {"hash": tx_hash, "from": EXECUTOR, "to": tx_to or safe, "input": "0x" + inp.hex(),
                       "value": "0x0", "blockNumber": hex(block), "blockHash": bh}
    topic0 = ER.TOPIC_SUCCESS if safe_ok else ER.TOPIC_FAILURE
    if indexed:
        logs = [{"address": safe, "topics": [topic0, sth], "data": "0x" + ("%064x" % payment), "logIndex": "0x0"}]
    else:
        logs = [{"address": safe, "topics": [topic0], "data": "0x" + sth[2:] + ("%064x" % payment), "logIndex": "0x0"}]
    mc.receipts[tx_hash] = {"status": "0x1" if ok else "0x0", "blockNumber": hex(block), "blockHash": bh,
                            "to": safe, "logs": logs}
    return tx_hash, nonce


# --- Snapshot ----------------------------------------------------------------

def cid_raw(body: bytes) -> str:
    return "b" + VR.b32_encode(bytes([1, 0x55, 0x12, 0x20]) + hashlib.sha256(body).digest())


_P_N = [0]


def proposal(body_text, title="Fund the grants program", space=SPACE, choices=None, vtype="basic",
             scores=None, quorum=0, start=None, end=None, snapshot=FIN - 50_000, state="closed",
             scores_state="final", author=ADMIN, treasuries=None, controllers=None, hub_body=None,
             hub_ipfs=None, network="1", quorum_type="default", register=True, gateways=None):
    """Pins a Snapshot proposal; returns its CID."""
    _P_N[0] += 1
    choices = choices if choices is not None else ["For", "Against", "Abstain"]
    scores = scores if scores is not None else [1000.0, 10.0, 0.0][:len(choices)] + [0.0] * max(0, len(choices) - 3)
    start = start if start is not None else NOW - 20 * DAY
    end = end if end is not None else NOW - 10 * DAY
    msg = {"from": author, "space": space, "timestamp": start - 60 - _P_N[0], "type": vtype, "title": title,
           "body": body_text, "discussion": "", "choices": choices, "labels": [], "start": start, "end": end,
           "snapshot": snapshot, "plugins": "{}", "privacy": "", "app": "snapshot-v2"}
    env = {"address": author, "sig": "0x" + "11" * 65, "hash": "0x" + "22" * 32,
           "data": {"domain": {"name": "snapshot", "version": "0.1.4"},
                    "types": {"Proposal": [{"name": "from", "type": "string"}]}, "message": msg}}
    body = json.dumps(env).encode()
    cid = cid_raw(body)
    if not register:
        return cid
    for g in (gateways if gateways is not None else VR.IPFS_GATEWAYS):
        stub.WEB.pages[g + cid] = (200, body)
    pid = "0x" + hashlib.sha256(cid.encode()).hexdigest()
    row = {"id": pid, "ipfs": hub_ipfs or cid, "author": author, "space": {"id": space}, "type": vtype,
           "title": title, "body": hub_body if hub_body is not None else body_text, "choices": choices,
           "start": start, "end": end, "snapshot": snapshot, "state": state, "scores": scores,
           "scores_total": sum(scores), "scores_state": scores_state, "quorum": quorum, "quorumType": quorum_type,
           "network": network}
    sp = space_row(space, treasuries, controllers, network)
    stub.WEB.pages[VR.hub_query_proposal(cid, space)] = (200, json.dumps({"data": {"proposals": [row], "space": sp}}))
    return cid


def space_row(space=SPACE, treasuries=None, controllers=None, network="1"):
    tr = treasuries if treasuries is not None else [[SAFE, "1"]]
    ctl = controllers if controllers is not None else [ADMIN]
    return {"id": space, "network": network, "treasuries": [{"address": a, "network": n} for a, n in tr],
            "admins": ctl, "moderators": []}


def space(space=SPACE, treasuries=None, controllers=None, network="1"):
    stub.WEB.pages[VR.hub_query_space(space)] = (200, json.dumps({"data": {"space": space_row(space, treasuries,
                                                                                             controllers, network)}}))


def ens(mc, name, address, resolver=addr(0xe75), block=None):
    node = VR.namehash(name).hex()
    tgt = mc.at.setdefault(block, {"calls": {}})["calls"] if block is not None else mc.calls
    tgt[(VR.ENS_REGISTRY, "0x0178b8bf" + node)] = "0x" + "0" * 24 + resolver[2:]
    tgt[(resolver, "0x3b3b57de" + node)] = "0x" + "0" * 24 + address[2:]
    mc.code[VR.ENS_REGISTRY] = "0x60"
    mc.code[resolver] = "0x60"


# --- a wired deployment -----------------------------------------------------------

class Deployment:
    def __init__(self, mode="DEMO", demo_controllers=None):
        stub.WEB.reset()
        stub.MODEL.reset()
        stub.TRANSFERS.clear()
        stub.SKIPPED.clear()
        stub.EXTERNAL.clear()
        stub.BALANCES.clear()
        stub.IC_ADDRESSES.clear()
        self.w = world.new_world(now_iso=NOW_ISO)
        self.er = self.w.deploy("ExecReader")
        self.vr = self.w.deploy("VoteReader")
        self.jg = self.w.deploy("AsVotedJudge", json.dumps(TOKEN_LIST))
        dc = ",".join(demo_controllers if demo_controllers is not None else ([CONTROLLER] if mode == "DEMO" else []))
        self.rg = self.w.deploy("AsVotedRegistry", mode, self.er, self.vr, self.jg, dc)
        self.st = self.w.deploy("DaoStanding", self.rg, 30, MONITOR, STALE_S)
        self.gate = self.w.deploy("GrantGate", self.st)
        self.mc = chain("ethereum")
        tokens(self.mc)

    # convenience wrappers
    def call(self, which, method, *args, sender=FILER, value=0):
        return self.w.call(which, method, *args, sender=sender, value=value)

    def view(self, which, method, *args):
        return self.w.view(which, method, *args)

    def list_dao(self, safe=SAFE, space_id=SPACE, chain_name="ethereum", **k):
        space(space_id, **k)
        self.call(self.vr, "read_space", space_id, chain_name, safe)
        return self.call(self.rg, "list_dao", space_id, chain_name, safe)["dao_id"]

    def read_exec(self, tx, nonce, safe=SAFE, chain_name="ethereum"):
        return self.call(self.er, "read_execution", chain_name, safe, tx, nonce)["exec_id"]

    def read_vote(self, cid, safe=SAFE, chain_name="ethereum"):
        return self.call(self.vr, "read_proposal", cid, chain_name, safe)["vote_id"]

    def names_at_execution(self, exec_id, vote_id):
        """What the pipeline and the site do before filing: resolve the
        proposal's ENS names at the execution's L1 block."""
        v = self.view(self.vr, "get_proposal", vote_id)
        e = self.view(self.er, "get_execution", exec_id)
        if v.get("found") and e.get("found") and v["ens_names"] and e["l1_block"] > 0:
            self.call(self.vr, "read_names_at", vote_id, e["l1_block"])

    def file(self, dao_id, exec_id, vote_id, note="", sender=FILER, value=None):
        self.names_at_execution(exec_id, vote_id)
        return self.call(self.rg, "file_check", dao_id, exec_id, vote_id, note, sender=sender,
                         value=STAKE if value is None else value)

    def judge_rule(self, check_id):
        j = self.call(self.jg, "judge", self.rg, check_id)
        r = self.call(self.rg, "rule", check_id)
        return j, r

    def heartbeat(self, dao_id, block=FIN, block_time=None, sender=None):
        """The monitor records that it has scanned the DAO's Safe through `block`."""
        bt = self.w.now() - 60 if block_time is None else block_time
        return self.call(self.rg, "record_coverage", json.dumps([[dao_id, block, bt]]), sender=sender or MONITOR)

    def ledger(self):
        return self.view(self.rg, "get_ledger")

    def balance(self, which=None):
        return self.w.instances[which or self.rg].balance
