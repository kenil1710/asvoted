# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *
from dataclasses import dataclass
import hashlib
import json
import typing

# AsVotedRegistry - DAOs, pledges, checks, rulings, money.
#
# DAOs
#   list_dao(space, chain, safe)   anyone; refused unless a VoteReader binding
#       read in the last BINDING_MAX_AGE shows the Safe listed among the
#       space's own treasuries. A listing carries no rights.
#   claim_dao(dao_id)              the space's admins / moderators (from a
#       fresh VoteReader binding) may take control of a listing. Only the
#       controller may pledge or withdraw. DEMO deployments only: the
#       addresses fixed in the constructor may also claim (a test seam,
#       visible in get_config; CANONICAL refuses any).
#   pledge / request_withdrawal / execute_withdrawal / cancel_withdrawal
#       the pledge bond ("we execute only what passed"). A withdrawal waits
#       WITHDRAW_DELAY and is refused while any check of the DAO is open.
#
# CHECKS
#   file_check(dao_id, exec_id, vote_id, note) + CHECK_STAKE. Evidence is
#   bound at filing to (chain, Safe, tx, proposal CID, block) and the two
#   reader records' evidence hashes are snapshotted. Refused unless the
#   execution is the DAO's Safe on the DAO's chain, the proposal is in the
#   DAO's space, the Safe was listed in that space's treasuries when the
#   proposal was read (and that read is fresh), the vote did not FAIL, and
#   the execution's block is after the vote ended. One check per execution;
#   a (tx, proposal) pair is never filed twice.
#
#   PROVISIONAL  awaiting AsVotedJudge.judge + rule(). Exit after
#                JUDGE_DEADLINE: expire() -> FINAL UNCLEAR, refunds.
#   CONTESTABLE  a provisional AS_VOTED / DEVIATES ruling. One appeal, with
#                APPEAL_BOND and new counter-evidence (novelty gate), and
#                optionally a different proposal this execution implements,
#                goes to a fresh panel (a new judge() transaction). Exit after
#                CONTEST_WINDOW: finalize().
#   APPEALED     awaiting judge + rule(). Exit after APPEAL_DEADLINE: expire()
#                -> the provisional ruling stands, the appeal bond is refunded.
#   FINAL        money moves to pull balances; claim() pays out.
#   An UNCLEAR ruling is FINAL at once and refunds everything.
#
# MONEY (code; frozen severity table)
#   DEVIATES final  the pledge (as it stood at filing) is slashed by the
#                   severity of the worst action; the slash is the bounty of
#                   whoever proved the deviation; their stake is refunded.
#   AS_VOTED final  the challenger's stake goes to the DAO's pledge.
#   UNCLEAR         refunds.
#   Appeal lost     the bond goes to the other side; won: refunded.
#   Ledger invariant: received == pledges + open stakes and bonds +
#   claimable + claimed, recomputable from records (get_ledger).
#
# RULES
#   1. A payable method never raises: a refused payment is credited to the
#      sender's pull balance and the call returns ok:false.
#   2. Nothing is written before the last check that can revert.
#   3. Every state has a deadline and a permissionless exit.
#   4. No owner, no admin, no setter. Addresses and windows are fixed at
#      deployment.

VERSION = "1.0.0"

MODES = {
    "CANONICAL": {"contest": 3600, "judge": 86400, "appeal": 86400, "withdraw": 3600, "binding": 3600},
    "DEMO": {"contest": 90, "judge": 600, "appeal": 600, "withdraw": 90, "binding": 3600},
}

CHECK_STAKE = 10 ** 17          # 0.1 GEN, exact
APPEAL_BOND = 10 ** 17          # 0.1 GEN, exact
MIN_PLEDGE = 10 ** 17
MAX_VALUE = 10 ** 27
BPS = 10000

# Frozen severity table: the worst action of a DEVIATES ruling sets it.
SEVERITY = (
    ("CRITICAL", 5000, "a DELEGATECALL the proposal does not mention"),
    ("MAJOR", 2500, "value sent to an address the proposal does not mention"),
    ("MAJOR", 2500, "an amount more than 10% above what the proposal states"),
    ("MINOR", 1000, "an amount up to 10% above what the proposal states"),
    ("MINOR", 1000, "a call the proposal does not mention"),
)
VALUE_KINDS = ("native", "erc20_transfer", "erc20_transfer_from", "erc20_approve", "gas_refund")

ST_PROVISIONAL = "PROVISIONAL"
ST_CONTESTABLE = "CONTESTABLE"
ST_APPEALED = "APPEALED"
ST_FINAL = "FINAL"
OPEN = (ST_PROVISIONAL, ST_CONTESTABLE, ST_APPEALED)

V_AS = "AS_VOTED"
V_DEV = "DEVIATES"
V_UNCLEAR = "UNCLEAR"

MIN_NOTE = 0
MAX_NOTE = 500
MIN_COUNTER = 40
MAX_COUNTER = 2000
NOVEL_JACCARD_BPS = 6000
NOVEL_CONTAIN_BPS = 8000
MAX_PAGE = 50
SCAN_CAP = 500

# ==== shared helpers: generated from contracts/shared/common.py by tools/inline_shared.py; edit there ====
# The runner rejects the str replace method; slice around find() instead.

# chain -> (chain id, (RPC A, RPC B), native symbol). Every node reads BOTH
# RPCs of a chain and refuses unless they answer identically. The two are run
# by different operators (docs/RESEARCH.md); both serve JSON-RPC batches, the
# "finalized" tag and transactions by hash from any height.
CHAINS = {
    "ethereum": (1, ("https://eth-pokt.nodies.app", "https://rpc.mevblocker.io"), "ETH"),
    "arbitrum": (42161, ("https://arb1.arbitrum.io/rpc", "https://arb-pokt.nodies.app"), "ETH"),
    "optimism": (10, ("https://mainnet.optimism.io", "https://optimism.drpc.org"), "ETH"),
    "base": (8453, ("https://mainnet.base.org", "https://base-pokt.nodies.app"), "ETH"),
    "polygon": (137, ("https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org"), "POL"),
}
# Largest JSON-RPC batch each endpoint accepts (measured).
RPC_BATCH = {"https://polygon.drpc.org": 3, "https://optimism.drpc.org": 3}
NETWORK_OF = {"1": "ethereum", "42161": "arbitrum", "10": "optimism", "8453": "base", "137": "polygon"}
LEADER_LAG_S = 1800           # a leader-named block may be this much older than a validator's own finalized block
RPC_TRIES = 3
ZERO = "0x" + "0" * 40


def _as_int(v: typing.Any, default: int = -1) -> int:
    if isinstance(v, bool):
        return default
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        t = v.strip()
        if t != "" and t.isdigit() and len(t) <= 78:
            return int(t)
    return default


def _is_hex(s: typing.Any, n: int = -1) -> bool:
    if not isinstance(s, str) or (n >= 0 and len(s) != n):
        return False
    for ch in s:
        if ch not in "0123456789abcdef":
            return False
    return True


def _addr(v: typing.Any) -> str:
    """A lowercase 0x address, or "" if v is not one."""
    t = str(v).strip().lower()
    if len(t) != 42 or not t.startswith("0x"):
        return ""
    return t if _is_hex(t[2:], 40) else ""


def _hash32(v: typing.Any) -> str:
    t = str(v).strip().lower()
    if len(t) != 66 or not t.startswith("0x") or not _is_hex(t[2:], 64):
        return ""
    return t


def _sha(text: typing.Any) -> str:
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _canon(obj: typing.Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _days_from_civil(y: int, m: int, d: int) -> int:
    y -= 1 if m <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _civil_from_days(z: int) -> tuple:
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return (y + (1 if m <= 2 else 0), m, d)


def _epoch_from_iso(value: typing.Any) -> int:
    """Seconds since the epoch from gl.message.raw["datetime"]
    ("2026-10-07T12:00:00Z"), identical on every validator."""
    if not isinstance(value, str) or len(value) < 19:
        return 0
    try:
        year = int(value[0:4])
        month = int(value[5:7])
        day = int(value[8:10])
        hour = int(value[11:13])
        minute = int(value[14:16])
        second = int(value[17:19])
    except Exception:
        return 0
    if month < 1 or month > 12 or day < 1 or day > 31 or hour > 23 or minute > 59 or second > 60:
        return 0
    return _days_from_civil(year, month, day) * 86400 + hour * 3600 + minute * 60 + second


def _two(n: int) -> str:
    return ("0" + str(n))[-2:]


def iso_date(epoch: int) -> str:
    y, m, d = _civil_from_days(int(epoch) // 86400)
    return str(y) + "-" + _two(m) + "-" + _two(d)


def iso_minute(epoch: int) -> str:
    s = int(epoch) % 86400
    return iso_date(epoch) + " " + _two(s // 3600) + ":" + _two((s % 3600) // 60) + " UTC"


# --- keccak-256 (Ethereum's, not NIST SHA3-256) ------------------------------

_KRC = (
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
)
_KROT = (0, 1, 62, 28, 27, 36, 44, 6, 55, 20, 3, 10, 43, 25, 39, 41, 45, 15, 21, 8, 18, 2, 61, 56, 14)
_M64 = (1 << 64) - 1


def _keccak_f(s: list) -> None:
    for rc in _KRC:
        c = [s[x] ^ s[x + 5] ^ s[x + 10] ^ s[x + 15] ^ s[x + 20] for x in range(5)]
        for x in range(5):
            v = c[(x + 1) % 5]
            d = c[(x - 1) % 5] ^ (((v << 1) | (v >> 63)) & _M64)
            for y in range(0, 25, 5):
                s[x + y] ^= d
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                v = s[x + 5 * y]
                r = _KROT[x + 5 * y]
                b[y + 5 * ((2 * x + 3 * y) % 5)] = (((v << r) | (v >> (64 - r))) & _M64) if r else v
        for y in range(0, 25, 5):
            for x in range(5):
                s[x + y] = b[x + y] ^ ((~b[(x + 1) % 5 + y]) & b[(x + 2) % 5 + y] & _M64)
        s[0] ^= rc


def keccak256(data: bytes) -> bytes:
    rate = 136
    p = bytearray(data)
    p.append(0x01)
    while len(p) % rate != 0:
        p.append(0)
    p[-1] |= 0x80
    s = [0] * 25
    for off in range(0, len(p), rate):
        for i in range(rate // 8):
            s[i] ^= int.from_bytes(bytes(p[off + 8 * i:off + 8 * i + 8]), "little")
        _keccak_f(s)
    return b"".join(s[i].to_bytes(8, "little") for i in range(4))


# --- ABI ----------------------------------------------------------------------

def _word(b: bytes, i: int) -> int:
    """The i-th 32-byte word of b as an unsigned int; ValueError if short."""
    if len(b) < 32 * (i + 1):
        raise ValueError("short")
    return int.from_bytes(b[32 * i:32 * (i + 1)], "big")


def _w_addr(b: bytes, i: int) -> str:
    v = _word(b, i)
    if v >> 160 != 0:
        raise ValueError("dirty address")
    return "0x" + ("0" * 40 + hex(v)[2:])[-40:]


def _w_bytes(b: bytes, i: int) -> bytes:
    off = _word(b, i)
    if off % 32 != 0 or off + 32 > len(b):
        raise ValueError("bad offset")
    n = int.from_bytes(b[off:off + 32], "big")
    if off + 32 + n > len(b):
        raise ValueError("bad length")
    return b[off + 32:off + 32 + n]


def enc_word(v: int) -> bytes:
    return int(v).to_bytes(32, "big")


def enc_addr(a: str) -> bytes:
    return bytes(12) + bytes.fromhex(a[2:])


def hexb(s: typing.Any) -> bytes:
    t = str(s)
    if t.startswith("0x"):
        t = t[2:]
    if len(t) % 2 == 1:
        raise ValueError("odd hex")
    return bytes.fromhex(t)


def fmt_units(raw: int, decimals: int) -> str:
    """A raw token amount as a decimal string with thousands separators,
    at most 4 decimals."""
    if decimals < 0:
        return str(raw) + " (raw)"
    whole = raw // (10 ** decimals) if decimals > 0 else raw
    frac = raw - whole * (10 ** decimals) if decimals > 0 else 0
    w = str(whole)
    g = ""
    while len(w) > 3:
        g = "," + w[-3:] + g
        w = w[:-3]
    g = w + g
    if decimals > 0 and frac > 0:
        f = ("0" * decimals + str(frac))[-decimals:][:4]
        while f.endswith("0"):
            f = f[:-1]
        if f != "":
            g = g + "." + f
    return g
# ==== end shared ====


def _words(text: str) -> list:
    out = []
    cur = ""
    for ch in str(text).lower():
        if ch.isalnum():
            cur += ch
        else:
            if cur != "":
                out.append(cur)
            cur = ""
    if cur != "":
        out.append(cur)
    return out


def _shingles(text: str) -> dict:
    w = _words(text)
    out = {}
    for i in range(len(w) - 2):
        out[w[i] + " " + w[i + 1] + " " + w[i + 2]] = True
    return out


def too_similar(new: str, old: str) -> bool:
    """Word 3-gram overlap: Jaccard >= 60% or >= 80% of the new text's
    3-grams already on record -> not new counter-evidence."""
    a = _shingles(new)
    b = _shingles(old)
    if len(a) == 0:
        return True
    inter = 0
    for k in a:
        if k in b:
            inter += 1
    union = len(a) + len(b) - inter
    if union > 0 and inter * BPS >= NOVEL_JACCARD_BPS * union:
        return True
    return inter * BPS >= NOVEL_CONTAIN_BPS * len(a)


def clean_text(s: typing.Any, limit: int) -> str:
    out = ""
    for ch in str(s):
        if ch == "\n" or ch == "\t" or ord(ch) >= 32:
            out += ch
    return out.strip()[:limit]


def severity_of(actions: list, exec_actions: list) -> list:
    """[label, bps, reason] of the worst NOT_AUTHORIZED / OVER_AMOUNT action,
    by the frozen table. Kinds come from the ExecReader record, not the
    judge."""
    by_i = {}
    for a in exec_actions:
        by_i[a["i"]] = a
    best = None
    for r in actions:
        a = by_i.get(r.get("i"))
        if a is None:
            continue
        o = r.get("outcome")
        row = None
        if o == "NOT_AUTHORIZED":
            if a["op"] == "DELEGATECALL":
                row = SEVERITY[0]
            elif a["kind"] in VALUE_KINDS or int(a.get("value", "0")) > 0:
                row = SEVERITY[1]
            else:
                row = SEVERITY[4]
        elif o == "OVER_AMOUNT":
            row = SEVERITY[2] if int(r.get("over_bps", 0)) > 1000 else SEVERITY[3]
        if row is not None and (best is None or row[1] > best[1]):
            best = row
    if best is None:
        return ["NONE", 0, ""]
    return [best[0], best[1], best[2]]


# =============================================================================
# storage
# =============================================================================

@gl.storage.allow
@dataclass
class Dao:
    dao_id: u64
    space: str
    chain: str
    safe: str
    listed_at: u64
    bind_id: u64
    lister: str
    controller: str
    pledge: u256
    withdraw_amount: u256
    withdraw_at: u64
    open_checks: u64
    n_checks: u64
    as_voted: u64
    deviates: u64
    unclear: u64
    last_deviates_at: u64
    last_deviates_check: u64
    slashed_total: u256


@gl.storage.allow
@dataclass
class Check:
    check_id: u64
    dao_id: u64
    chain: str
    safe: str
    tx: str
    block: u64
    exec_id: u64
    vote_id: u64
    cid: str
    exec_sha: str
    vote_sha: str
    filer: str
    stake: u256
    note: str
    filed_at: u64
    status: str
    round: u64
    judge_deadline: u64
    ruling: str
    ruling_summary: str
    ruling_json: str
    ruled_at: u64
    contest_deadline: u64
    appellant: str
    appeal_bond: u256
    appeal_text: str
    appeal_vote_id: u64
    appeal_cid: str
    appeal_vote_sha: str
    appeal_deadline: u64
    appeal_ruling: str
    appeal_summary: str
    appeal_json: str
    final_verdict: str
    final_how: str
    final_at: u64
    severity: str
    severity_bps: u64
    pledge_at_filing: u256
    slash: u256
    bounty_to: str
    settlement_json: str


class AsVotedRegistry(gl.contract.Contract):
    mode: str
    exec_reader: Address
    vote_reader: Address
    judge: Address
    demo_controllers_json: str
    contest_s: u64
    judge_s: u64
    appeal_s: u64
    withdraw_s: u64
    binding_s: u64
    n_daos: u64
    n_checks: u64
    daos: gl.storage.TreeMap[u64, Dao]
    dao_by_key: gl.storage.TreeMap[str, u64]
    checks: gl.storage.TreeMap[u64, Check]
    check_by_tx: gl.storage.TreeMap[str, u64]
    pair_seen: gl.storage.TreeMap[str, u64]
    dao_check_n: gl.storage.TreeMap[u64, u64]
    dao_check_at: gl.storage.TreeMap[str, u64]
    counts: gl.storage.TreeMap[str, u64]
    claimable: gl.storage.TreeMap[str, u256]
    claimed: gl.storage.TreeMap[str, u256]
    payees: gl.storage.DynArray[str]
    payee_seen: gl.storage.TreeMap[str, bool]
    received_total: u256
    pledges_total: u256
    open_total: u256
    claimable_total: u256
    claimed_total: u256

    def __init__(self, mode: str, exec_reader: str, vote_reader: str, judge: str, demo_controllers: str) -> None:
        m = str(mode).strip().upper()
        if m not in MODES:
            raise gl.vm.UserError("mode must be CANONICAL or DEMO")
        er = _addr(exec_reader)
        vr = _addr(vote_reader)
        jg = _addr(judge)
        if er == "" or vr == "" or jg == "":
            raise gl.vm.UserError("reader and judge addresses must be 0x addresses")
        ctl = []
        for part in str(demo_controllers).split(","):
            if part.strip() == "":
                continue
            a = _addr(part)
            if a == "":
                raise gl.vm.UserError("demo_controllers must be comma-separated 0x addresses")
            ctl.append(a)
        if m == "CANONICAL" and len(ctl) > 0:
            raise gl.vm.UserError("CANONICAL takes no demo controllers")
        cfg = MODES[m]
        self.mode = m
        self.exec_reader = Address(er)
        self.vote_reader = Address(vr)
        self.judge = Address(jg)
        self.demo_controllers_json = _canon(ctl)
        self.contest_s = u64(cfg["contest"])
        self.judge_s = u64(cfg["judge"])
        self.appeal_s = u64(cfg["appeal"])
        self.withdraw_s = u64(cfg["withdraw"])
        self.binding_s = u64(cfg["binding"])
        self.n_daos = u64(0)
        self.n_checks = u64(0)
        self.received_total = u256(0)
        self.pledges_total = u256(0)
        self.open_total = u256(0)
        self.claimable_total = u256(0)
        self.claimed_total = u256(0)

    # --- helpers --------------------------------------------------------------

    def _now(self) -> int:
        return _epoch_from_iso(gl.message.raw.get("datetime", ""))

    def _sender(self) -> str:
        return gl.message.sender_address.as_hex.lower()

    def _ext(self, which: Address, fn: str, args: list) -> typing.Any:
        try:
            v = gl.contract.get_at(which).view()
            raw = getattr(v, fn)(*args)
        except Exception:
            return None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return None
        return raw

    def _binding(self, space: str, chain: str, safe: str) -> typing.Any:
        bid = self._ext(self.vote_reader, "get_binding_id", [space, chain, safe])
        if not isinstance(bid, int) or bid <= 0:
            return None
        b = self._ext(self.vote_reader, "get_binding", [bid])
        if not isinstance(b, dict) or not b.get("found"):
            return None
        return b

    def _credit(self, who: str, amount: int) -> None:
        if amount <= 0:
            return
        k = str(who).lower()
        if not bool(self.payee_seen.get(k, False)):
            self.payee_seen[k] = True
            self.payees.append(k)
        self.claimable[k] = u256(int(self.claimable.get(k, u256(0))) + int(amount))
        self.claimable_total = u256(int(self.claimable_total) + int(amount))

    def _refuse(self, sender: str, value: int, reason: str) -> typing.Any:
        """A refused payable call: the value is credited to the sender's pull
        balance and the call returns ok:false. Never a raise."""
        if value > 0:
            self.received_total = u256(int(self.received_total) + value)
            self._credit(sender, value)
        return {"ok": False, "reason": reason, "refunded_to_claimable": str(value)}

    def _dao(self, dao_id: typing.Any) -> typing.Any:
        d = _as_int(dao_id, -1)
        if d <= 0:
            return None
        return self.daos.get(u64(d))

    def _check(self, check_id: typing.Any) -> typing.Any:
        c = _as_int(check_id, -1)
        if c <= 0:
            return None
        return self.checks.get(u64(c))

    def _bump(self, key: str) -> None:
        self.counts[key] = u64(int(self.counts.get(key) or 0) + 1)

    def _drop(self, key: str) -> None:
        self.counts[key] = u64(max(int(self.counts.get(key) or 0) - 1, 0))

    def _vote_problem(self, d: Dao, vote: typing.Any, ex: dict, now: int) -> str:
        if not isinstance(vote, dict) or not vote.get("found"):
            return "NO_SUCH_PROPOSAL_RECORD"
        if vote["space"] != d.space:
            return "PROPOSAL_IS_NOT_IN_THE_DAOS_SPACE"
        if vote["chain"] != d.chain or vote["safe"] != d.safe:
            return "PROPOSAL_RECORD_READ_FOR_ANOTHER_SAFE"
        if not vote["listed"]:
            return "SAFE_NOT_LISTED_IN_SPACE_TREASURIES_AT_READ"
        if now - int(vote["read_at"]) > int(self.binding_s):
            return "PROPOSAL_RECORD_TOO_OLD_REREAD_IT"
        if vote["outcome"] == "FAILED":
            return "PROPOSAL_DID_NOT_PASS"
        if int(ex["block_time"]) <= int(vote["end"]):
            return "EXECUTED_BEFORE_THE_VOTE_ENDED"
        return ""

    # --- DAOs -----------------------------------------------------------------

    @gl.public.write
    def list_dao(self, space: str, chain: str, safe: str) -> typing.Any:
        """List a DAO: (Snapshot space, chain, Safe). Refused unless a fresh
        VoteReader binding shows the Safe in the space's own treasuries."""
        now = self._now()
        if now <= 0:
            raise gl.vm.UserError("REFUSED: NO_CLOCK")
        sp = str(space).strip().lower()
        ch = str(chain).strip().lower()
        sf = _addr(safe)
        if ch not in CHAINS:
            raise gl.vm.UserError("REFUSED: UNSUPPORTED_CHAIN")
        if sf == "" or sf == ZERO:
            raise gl.vm.UserError("REFUSED: BAD_SAFE_ADDRESS")
        key = ch + "|" + sf + "|" + sp
        if int(self.dao_by_key.get(key) or 0) != 0:
            raise gl.vm.UserError("REFUSED: ALREADY_LISTED_AS_" + str(int(self.dao_by_key.get(key))))
        b = self._binding(sp, ch, sf)
        if b is None:
            raise gl.vm.UserError("REFUSED: NO_BINDING_READ_CALL_VOTEREADER_READ_SPACE")
        if now - int(b["read_at"]) > int(self.binding_s):
            raise gl.vm.UserError("REFUSED: BINDING_TOO_OLD_REREAD_IT")
        if not b["listed"]:
            raise gl.vm.UserError("REFUSED: SAFE_NOT_LISTED_IN_SPACE_TREASURIES")
        # --- writes
        did = int(self.n_daos) + 1
        self.daos[u64(did)] = Dao(
            dao_id=u64(did), space=sp, chain=ch, safe=sf, listed_at=u64(now), bind_id=u64(int(b["bind_id"])),
            lister=self._sender(), controller="", pledge=u256(0), withdraw_amount=u256(0), withdraw_at=u64(0),
            open_checks=u64(0), n_checks=u64(0), as_voted=u64(0), deviates=u64(0), unclear=u64(0),
            last_deviates_at=u64(0), last_deviates_check=u64(0), slashed_total=u256(0))
        self.dao_by_key[key] = u64(did)
        self.n_daos = u64(did)
        return {"ok": True, "dao_id": did}

    @gl.public.write
    def claim_dao(self, dao_id: int) -> typing.Any:
        """Take control of a listing: the sender must be an admin or moderator
        of the DAO's Snapshot space in a fresh VoteReader binding."""
        now = self._now()
        if now <= 0:
            raise gl.vm.UserError("REFUSED: NO_CLOCK")
        d = self._dao(dao_id)
        if d is None:
            raise gl.vm.UserError("REFUSED: NO_SUCH_DAO")
        me = self._sender()
        b = self._binding(d.space, d.chain, d.safe)
        if b is None or now - int(b["read_at"]) > int(self.binding_s):
            raise gl.vm.UserError("REFUSED: BINDING_TOO_OLD_REREAD_IT")
        if not b["listed"]:
            raise gl.vm.UserError("REFUSED: SAFE_NO_LONGER_LISTED")
        ctl = [str(x) for x in b["controllers"]]
        demo = json.loads(self.demo_controllers_json) if self.mode == "DEMO" else []
        if me not in ctl and me not in demo:
            raise gl.vm.UserError("REFUSED: NOT_AN_ADMIN_OR_MODERATOR_OF_THE_SPACE")
        if d.controller != "" and d.controller != me and (d.controller in ctl or d.controller in demo):
            raise gl.vm.UserError("REFUSED: ALREADY_CLAIMED_BY_A_CURRENT_ADMIN")
        # --- writes
        d.controller = me
        return {"ok": True, "dao_id": int(d.dao_id), "controller": me}

    @gl.public.write.payable
    def pledge(self, dao_id: int) -> typing.Any:
        """Add to the DAO's pledge bond. Controller only."""
        value = int(gl.message.value)
        me = self._sender()
        d = self._dao(dao_id)
        problem = ""
        if d is None:
            problem = "NO_SUCH_DAO"
        elif d.controller == "" or d.controller != me:
            problem = "ONLY_THE_DAOS_CONTROLLER_MAY_PLEDGE"
        elif value < MIN_PLEDGE or value > MAX_VALUE:
            problem = "PLEDGE_OUT_OF_RANGE"
        if problem != "":
            return self._refuse(me, value, problem)
        # --- writes
        self.received_total = u256(int(self.received_total) + value)
        d.pledge = u256(int(d.pledge) + value)
        self.pledges_total = u256(int(self.pledges_total) + value)
        return {"ok": True, "dao_id": int(d.dao_id), "pledge": str(int(d.pledge))}

    @gl.public.write
    def request_withdrawal(self, dao_id: int, amount: str) -> typing.Any:
        now = self._now()
        if now <= 0:
            raise gl.vm.UserError("REFUSED: NO_CLOCK")
        d = self._dao(dao_id)
        if d is None:
            raise gl.vm.UserError("REFUSED: NO_SUCH_DAO")
        if d.controller == "" or d.controller != self._sender():
            raise gl.vm.UserError("REFUSED: ONLY_THE_DAOS_CONTROLLER")
        amt = _as_int(amount, -1)
        if amt <= 0 or amt > int(d.pledge):
            raise gl.vm.UserError("REFUSED: AMOUNT_OUT_OF_RANGE")
        if int(d.open_checks) > 0:
            raise gl.vm.UserError("REFUSED: CHECKS_OPEN_" + str(int(d.open_checks)))
        # --- writes
        d.withdraw_amount = u256(amt)
        d.withdraw_at = u64(now + int(self.withdraw_s))
        return {"ok": True, "unlocks_at": now + int(self.withdraw_s)}

    @gl.public.write
    def cancel_withdrawal(self, dao_id: int) -> typing.Any:
        d = self._dao(dao_id)
        if d is None:
            raise gl.vm.UserError("REFUSED: NO_SUCH_DAO")
        if d.controller == "" or d.controller != self._sender():
            raise gl.vm.UserError("REFUSED: ONLY_THE_DAOS_CONTROLLER")
        if int(d.withdraw_amount) == 0:
            raise gl.vm.UserError("REFUSED: NO_WITHDRAWAL_PENDING")
        d.withdraw_amount = u256(0)
        d.withdraw_at = u64(0)
        return {"ok": True}

    @gl.public.write
    def execute_withdrawal(self, dao_id: int) -> typing.Any:
        """Anyone, after the delay: the requested amount moves to the
        controller's pull balance."""
        now = self._now()
        if now <= 0:
            raise gl.vm.UserError("REFUSED: NO_CLOCK")
        d = self._dao(dao_id)
        if d is None:
            raise gl.vm.UserError("REFUSED: NO_SUCH_DAO")
        amt = int(d.withdraw_amount)
        if amt == 0:
            raise gl.vm.UserError("REFUSED: NO_WITHDRAWAL_PENDING")
        if now < int(d.withdraw_at):
            raise gl.vm.UserError("REFUSED: WITHDRAWAL_LOCKED_UNTIL_" + str(int(d.withdraw_at)))
        if int(d.open_checks) > 0:
            raise gl.vm.UserError("REFUSED: CHECKS_OPEN_" + str(int(d.open_checks)))
        amt = min(amt, int(d.pledge))
        # --- writes
        d.pledge = u256(int(d.pledge) - amt)
        self.pledges_total = u256(int(self.pledges_total) - amt)
        d.withdraw_amount = u256(0)
        d.withdraw_at = u64(0)
        self._credit(d.controller, amt)
        return {"ok": True, "withdrawn": str(amt), "to": d.controller}

    # --- checks ---------------------------------------------------------------

    @gl.public.write.payable
    def file_check(self, dao_id: int, exec_id: int, vote_id: int, note: str) -> typing.Any:
        """File a check of one execution against one proposal, with exactly
        CHECK_STAKE. Both records must already be read (ExecReader /
        VoteReader)."""
        value = int(gl.message.value)
        me = self._sender()
        now = self._now()
        problem = ""
        d = self._dao(dao_id)
        ex = None
        vote = None
        if now <= 0:
            problem = "NO_CLOCK"
        elif value != CHECK_STAKE:
            problem = "STAKE_MUST_BE_EXACTLY_" + str(CHECK_STAKE)
        elif d is None:
            problem = "NO_SUCH_DAO"
        if problem == "":
            ex = self._ext(self.exec_reader, "get_execution", [_as_int(exec_id, 0)])
            if not isinstance(ex, dict) or not ex.get("found"):
                problem = "NO_SUCH_EXECUTION_RECORD"
            elif ex["chain"] != d.chain or ex["safe"] != d.safe:
                problem = "EXECUTION_IS_NOT_THE_DAOS_SAFE"
        if problem == "":
            vote = self._ext(self.vote_reader, "get_proposal", [_as_int(vote_id, 0)])
            problem = self._vote_problem(d, vote, ex, now)
        txk = ""
        if problem == "":
            txk = ex["chain"] + "|" + ex["safe"] + "|" + ex["tx"]
            prev = int(self.check_by_tx.get(txk) or 0)
            if prev != 0:
                pc = self.checks[u64(prev)]
                if pc.status != ST_FINAL or pc.final_verdict != V_UNCLEAR:
                    problem = "DUPLICATE_OF_CHECK_" + str(prev)
            if problem == "" and int(self.pair_seen.get(txk + "|" + vote["cid"]) or 0) != 0:
                problem = "THIS_EXECUTION_AND_PROPOSAL_WERE_ALREADY_CHECKED"
        if problem != "":
            return self._refuse(me, value, problem)
        # --- writes (nothing below can refuse)
        cid = int(self.n_checks) + 1
        self.received_total = u256(int(self.received_total) + value)
        self.open_total = u256(int(self.open_total) + value)
        self.checks[u64(cid)] = Check(
            check_id=u64(cid), dao_id=d.dao_id, chain=d.chain, safe=d.safe, tx=ex["tx"], block=u64(int(ex["block"])),
            exec_id=u64(int(ex["exec_id"])), vote_id=u64(int(vote["vote_id"])), cid=vote["cid"],
            exec_sha=ex["evidence_sha256"], vote_sha=vote["evidence_sha256"], filer=me, stake=u256(value),
            note=clean_text(note, MAX_NOTE), filed_at=u64(now), status=ST_PROVISIONAL, round=u64(0),
            judge_deadline=u64(now + int(self.judge_s)), ruling="", ruling_summary="", ruling_json="", ruled_at=u64(0),
            contest_deadline=u64(0), appellant="", appeal_bond=u256(0), appeal_text="", appeal_vote_id=u64(0),
            appeal_cid="", appeal_vote_sha="", appeal_deadline=u64(0), appeal_ruling="", appeal_summary="",
            appeal_json="", final_verdict="", final_how="", final_at=u64(0), severity="", severity_bps=u64(0),
            pledge_at_filing=d.pledge, slash=u256(0), bounty_to="", settlement_json="")
        self.check_by_tx[txk] = u64(cid)
        self.pair_seen[txk + "|" + vote["cid"]] = u64(cid)
        n = int(self.dao_check_n.get(d.dao_id) or 0)
        self.dao_check_at[str(int(d.dao_id)) + "#" + str(n)] = u64(cid)
        self.dao_check_n[d.dao_id] = u64(n + 1)
        d.open_checks = u64(int(d.open_checks) + 1)
        d.n_checks = u64(int(d.n_checks) + 1)
        self.n_checks = u64(cid)
        self._bump("status:" + ST_PROVISIONAL)
        return {"ok": True, "check_id": cid, "judge_deadline": now + int(self.judge_s)}

    def _input(self, c: Check) -> dict:
        """The evidence for the open round, read back from the readers and
        compared with what was snapshotted at filing."""
        rnd = int(c.round)
        ex = self._ext(self.exec_reader, "get_execution", [int(c.exec_id)])
        vid = int(c.appeal_vote_id) if rnd == 1 and int(c.appeal_vote_id) > 0 else int(c.vote_id)
        want_vsha = c.appeal_vote_sha if rnd == 1 and int(c.appeal_vote_id) > 0 else c.vote_sha
        vote = self._ext(self.vote_reader, "get_proposal", [vid])
        if not isinstance(ex, dict) or not ex.get("found") or not isinstance(vote, dict) or not vote.get("found"):
            return {"error": "READER_UNREADABLE"}
        if ex["evidence_sha256"] != c.exec_sha or vote["evidence_sha256"] != want_vsha:
            return {"error": "SNAPSHOT_MISMATCH"}
        counter = c.appeal_text if rnd == 1 else ""
        sha = _sha(_canon({"exec": ex, "vote": vote, "counter_evidence": counter, "round": rnd}))
        return {"exec": ex, "vote": vote, "counter_evidence": counter, "round": rnd, "input_sha256": sha}

    @gl.public.view
    def get_judge_input(self, check_id: int) -> typing.Any:
        """Everything AsVotedJudge needs for the open round of a check."""
        c = self._check(check_id)
        if c is None:
            return {"found": False}
        is_open = (c.status == ST_PROVISIONAL and int(c.round) == 0) or (c.status == ST_APPEALED and int(c.round) == 1)
        out = {"found": True, "check_id": int(c.check_id), "round": int(c.round), "open": is_open,
               "status": c.status}
        if not is_open:
            return out
        inp = self._input(c)
        if "error" in inp:
            out["open"] = False
            out["why"] = inp["error"]
            return out
        for k in inp:
            out[k] = inp[k]
        return out

    @gl.public.write
    def rule(self, check_id: int) -> typing.Any:
        """Apply the judge's ruling for the open round. Anyone."""
        now = self._now()
        if now <= 0:
            raise gl.vm.UserError("REFUSED: NO_CLOCK")
        c = self._check(check_id)
        if c is None:
            raise gl.vm.UserError("REFUSED: NO_SUCH_CHECK")
        rnd = int(c.round)
        if not ((c.status == ST_PROVISIONAL and rnd == 0) or (c.status == ST_APPEALED and rnd == 1)):
            raise gl.vm.UserError("REFUSED: NOTHING_TO_RULE_ON_IN_" + c.status)
        j = self._ext(self.judge, "get_judgment", [gl.message.contract_address.as_hex.lower(), int(c.check_id), rnd])
        if not isinstance(j, dict) or not j.get("found"):
            raise gl.vm.UserError("REFUSED: NOT_JUDGED_YET")
        deadline = int(c.judge_deadline) if rnd == 0 else int(c.appeal_deadline)
        if int(j["judged_at"]) > deadline:
            raise gl.vm.UserError("REFUSED: JUDGED_AFTER_THE_DEADLINE_USE_EXPIRE")
        inp = self._input(c)
        if "error" in inp:
            raise gl.vm.UserError("REFUSED: " + inp["error"])
        if j["input_sha256"] != inp["input_sha256"]:
            raise gl.vm.UserError("REFUSED: JUDGMENT_IS_FOR_OTHER_EVIDENCE")
        verdict = str(j["overall"])
        if verdict not in (V_AS, V_DEV, V_UNCLEAR):
            raise gl.vm.UserError("REFUSED: JUDGMENT_UNREADABLE")
        d = self.daos[c.dao_id]
        sev = severity_of(j["actions"], inp["exec"]["actions"]) if verdict == V_DEV else ["NONE", 0, ""]
        doc = _canon({"actions": j["actions"], "counts": j["counts"], "judged_at": j["judged_at"],
                      "judged_by": j["judged_by"], "input_sha256": j["input_sha256"], "severity": sev})
        # --- writes (nothing below can refuse)
        if rnd == 0:
            c.ruling = verdict
            c.ruling_summary = str(j["summary"])
            c.ruling_json = doc
            c.ruled_at = u64(now)
            c.severity = sev[0]
            c.severity_bps = u64(sev[1])
            self._drop("status:" + ST_PROVISIONAL)
            if verdict == V_UNCLEAR:
                self._settle(c, d, V_UNCLEAR, "RULED_UNCLEAR", now)
            else:
                c.status = ST_CONTESTABLE
                c.contest_deadline = u64(now + int(self.contest_s))
                self._bump("status:" + ST_CONTESTABLE)
            return {"ok": True, "check_id": int(c.check_id), "ruling": verdict, "status": c.status}
        c.appeal_ruling = verdict
        c.appeal_summary = str(j["summary"])
        c.appeal_json = doc
        self._drop("status:" + ST_APPEALED)
        c.severity = sev[0]
        c.severity_bps = u64(sev[1])
        self._settle(c, d, verdict, "APPEAL_RULED", now)
        return {"ok": True, "check_id": int(c.check_id), "appeal_ruling": verdict, "final": c.final_verdict}

    @gl.public.write.payable
    def appeal(self, check_id: int, counter_evidence: str, alt_vote_id: int) -> typing.Any:
        """One appeal of a CONTESTABLE ruling, with exactly APPEAL_BOND and new
        counter-evidence. A DEVIATES ruling is appealed by the DAO's
        controller (anyone but the filer if the listing is unclaimed); an
        AS_VOTED ruling by anyone but the controller. alt_vote_id (0 = none):
        a different proposal record this execution implements."""
        value = int(gl.message.value)
        me = self._sender()
        now = self._now()
        c = self._check(check_id)
        problem = ""
        text = clean_text(counter_evidence, MAX_COUNTER + 1)
        alt = _as_int(alt_vote_id, -1)
        vote = None
        d = None
        if now <= 0:
            problem = "NO_CLOCK"
        elif value != APPEAL_BOND:
            problem = "BOND_MUST_BE_EXACTLY_" + str(APPEAL_BOND)
        elif c is None:
            problem = "NO_SUCH_CHECK"
        elif c.status != ST_CONTESTABLE:
            problem = "NOT_CONTESTABLE"
        elif now > int(c.contest_deadline):
            problem = "CONTEST_WINDOW_CLOSED"
        if problem == "":
            d = self.daos[c.dao_id]
            if c.ruling == V_DEV:
                if d.controller != "" and me != d.controller:
                    problem = "ONLY_THE_DAOS_CONTROLLER_MAY_APPEAL_DEVIATES"
                elif d.controller == "" and me == c.filer:
                    problem = "THE_FILER_CANNOT_APPEAL_THEIR_OWN_DEVIATES"
            elif c.ruling == V_AS:
                if d.controller != "" and me == d.controller:
                    problem = "THE_CONTROLLER_CANNOT_APPEAL_AS_VOTED"
            else:
                problem = "NOT_APPEALABLE"
        if problem == "":
            if len(text) < MIN_COUNTER or len(text) > MAX_COUNTER:
                problem = "COUNTER_EVIDENCE_LENGTH_" + str(MIN_COUNTER) + "_TO_" + str(MAX_COUNTER)
            elif too_similar(text, c.note + "\n" + c.ruling_summary):
                problem = "COUNTER_EVIDENCE_NOT_NEW"
        if problem == "" and alt > 0:
            ex = self._ext(self.exec_reader, "get_execution", [int(c.exec_id)])
            vote = self._ext(self.vote_reader, "get_proposal", [alt])
            if not isinstance(ex, dict) or not ex.get("found"):
                problem = "READER_UNREADABLE"
            else:
                problem = self._vote_problem(d, vote, ex, now)
            if problem == "" and vote["cid"] == c.cid:
                problem = "ALT_PROPOSAL_IS_THE_SAME_PROPOSAL"
        elif problem == "" and alt < 0:
            problem = "BAD_ALT_VOTE_ID"
        if problem != "":
            return self._refuse(me, value, problem)
        # --- writes
        self.received_total = u256(int(self.received_total) + value)
        self.open_total = u256(int(self.open_total) + value)
        c.appellant = me
        c.appeal_bond = u256(value)
        c.appeal_text = text
        if alt > 0:
            c.appeal_vote_id = u64(alt)
            c.appeal_cid = vote["cid"]
            c.appeal_vote_sha = vote["evidence_sha256"]
        c.status = ST_APPEALED
        c.round = u64(1)
        c.appeal_deadline = u64(now + int(self.appeal_s))
        self._drop("status:" + ST_CONTESTABLE)
        self._bump("status:" + ST_APPEALED)
        return {"ok": True, "check_id": int(c.check_id), "appeal_deadline": now + int(self.appeal_s)}

    @gl.public.write
    def finalize(self, check_id: int) -> typing.Any:
        """CONTESTABLE past its window, no appeal: the ruling becomes FINAL."""
        now = self._now()
        if now <= 0:
            raise gl.vm.UserError("REFUSED: NO_CLOCK")
        c = self._check(check_id)
        if c is None:
            raise gl.vm.UserError("REFUSED: NO_SUCH_CHECK")
        if c.status != ST_CONTESTABLE:
            raise gl.vm.UserError("REFUSED: NOT_CONTESTABLE")
        if now <= int(c.contest_deadline):
            raise gl.vm.UserError("REFUSED: CONTESTABLE_UNTIL_" + str(int(c.contest_deadline)))
        d = self.daos[c.dao_id]
        # --- writes
        self._drop("status:" + ST_CONTESTABLE)
        self._settle(c, d, c.ruling, "NO_APPEAL", now)
        return {"ok": True, "check_id": int(c.check_id), "final": c.final_verdict}

    @gl.public.write
    def expire(self, check_id: int) -> typing.Any:
        """The deadline exits. PROVISIONAL past its judge deadline -> FINAL
        UNCLEAR with refunds. APPEALED past its appeal deadline -> the
        provisional ruling stands and the appeal bond is refunded."""
        now = self._now()
        if now <= 0:
            raise gl.vm.UserError("REFUSED: NO_CLOCK")
        c = self._check(check_id)
        if c is None:
            raise gl.vm.UserError("REFUSED: NO_SUCH_CHECK")
        if c.status == ST_PROVISIONAL:
            if now <= int(c.judge_deadline):
                raise gl.vm.UserError("REFUSED: JUDGEABLE_UNTIL_" + str(int(c.judge_deadline)))
            how = "EXPIRED_UNJUDGED"
        elif c.status == ST_APPEALED:
            if now <= int(c.appeal_deadline):
                raise gl.vm.UserError("REFUSED: APPEAL_JUDGEABLE_UNTIL_" + str(int(c.appeal_deadline)))
            how = "APPEAL_EXPIRED"
        else:
            raise gl.vm.UserError("REFUSED: NOTHING_TO_EXPIRE_IN_" + c.status)
        d = self.daos[c.dao_id]
        # --- writes
        self._drop("status:" + c.status)
        if how == "EXPIRED_UNJUDGED":
            self._settle(c, d, V_UNCLEAR, how, now)
        else:
            self._settle(c, d, c.ruling, how, now)
        return {"ok": True, "check_id": int(c.check_id), "final": c.final_verdict, "how": how}

    def _settle(self, c: Check, d: Dao, verdict: str, how: str, now: int) -> None:
        """Move every coin of a check, by the rules in the header. Only ever
        called after the last check that can revert."""
        stake = int(c.stake)
        bond = int(c.appeal_bond)
        moves = []
        appealed = c.appellant != "" and how in ("APPEAL_RULED", "APPEAL_EXPIRED")
        # release what this check held
        self.open_total = u256(int(self.open_total) - stake - bond)
        if how == "APPEAL_EXPIRED":
            # the appeal was never ruled on: the bond goes back, the ruling stands
            self._credit(c.appellant, bond)
            moves.append(["appeal bond refunded", c.appellant, str(bond)])
            bond = 0
            appealed = False
        if verdict == V_UNCLEAR:
            self._credit(c.filer, stake)
            moves.append(["stake refunded", c.filer, str(stake)])
            if bond > 0:
                self._credit(c.appellant, bond)
                moves.append(["appeal bond refunded", c.appellant, str(bond)])
        elif verdict == V_AS:
            d.pledge = u256(int(d.pledge) + stake)
            self.pledges_total = u256(int(self.pledges_total) + stake)
            moves.append(["stake to the DAO pledge", "dao#" + str(int(d.dao_id)), str(stake)])
            if bond > 0:
                if c.ruling == V_DEV:
                    # the DAO appealed a DEVIATES ruling and won
                    self._credit(c.appellant, bond)
                    moves.append(["appeal bond refunded", c.appellant, str(bond)])
                else:
                    d.pledge = u256(int(d.pledge) + bond)
                    self.pledges_total = u256(int(self.pledges_total) + bond)
                    moves.append(["appeal bond to the DAO pledge", "dao#" + str(int(d.dao_id)), str(bond)])
        else:
            winner = c.filer
            if appealed and c.ruling == V_AS:
                winner = c.appellant
            self._credit(c.filer, stake)
            moves.append(["stake refunded", c.filer, str(stake)])
            if bond > 0:
                if c.ruling == V_DEV:
                    self._credit(c.filer, bond)
                    moves.append(["appeal bond to the filer", c.filer, str(bond)])
                else:
                    self._credit(c.appellant, bond)
                    moves.append(["appeal bond refunded", c.appellant, str(bond)])
            slash = int(c.pledge_at_filing) * int(c.severity_bps) // BPS
            slash = min(slash, int(d.pledge))
            if slash > 0:
                d.pledge = u256(int(d.pledge) - slash)
                self.pledges_total = u256(int(self.pledges_total) - slash)
                d.slashed_total = u256(int(d.slashed_total) + slash)
                self._credit(winner, slash)
                moves.append(["pledge slashed, bounty", winner, str(slash)])
            c.slash = u256(slash)
            c.bounty_to = winner
            d.last_deviates_at = u64(now)
            d.last_deviates_check = c.check_id
        c.status = ST_FINAL
        c.final_verdict = verdict
        c.final_how = how
        c.final_at = u64(now)
        c.settlement_json = _canon(moves)
        d.open_checks = u64(max(int(d.open_checks) - 1, 0))
        if verdict == V_AS:
            d.as_voted = u64(int(d.as_voted) + 1)
        elif verdict == V_DEV:
            d.deviates = u64(int(d.deviates) + 1)
        else:
            d.unclear = u64(int(d.unclear) + 1)
        self._bump("status:" + ST_FINAL)
        self._bump("final:" + verdict)
        self._bump("how:" + how)

    @gl.public.write
    def claim(self) -> typing.Any:
        """Pull payment of everything credited to the caller. The balance is
        zeroed before the transfer is posted."""
        who = self._sender()
        owed = int(self.claimable.get(who, u256(0)))
        if owed <= 0:
            raise gl.vm.UserError("REFUSED: NOTHING_TO_CLAIM")
        # --- writes
        self.claimable[who] = u256(0)
        self.claimable_total = u256(int(self.claimable_total) - owed)
        self.claimed[who] = u256(int(self.claimed.get(who, u256(0))) + owed)
        self.claimed_total = u256(int(self.claimed_total) + owed)
        gl.chain.Account(Address(who)).emit_transfer(u256(owed))
        return {"ok": True, "claimed": str(owed)}

    # --- views (storage only) -------------------------------------------------

    def _dao_view(self, d: Dao) -> dict:
        return {"dao_id": int(d.dao_id), "space": d.space, "chain": d.chain, "safe": d.safe,
                "listed_at": int(d.listed_at), "bind_id": int(d.bind_id), "lister": d.lister,
                "controller": d.controller, "pledge": str(int(d.pledge)),
                "withdraw_amount": str(int(d.withdraw_amount)), "withdraw_at": int(d.withdraw_at),
                "open_checks": int(d.open_checks), "n_checks": int(d.n_checks), "as_voted": int(d.as_voted),
                "deviates": int(d.deviates), "unclear": int(d.unclear),
                "last_deviates_at": int(d.last_deviates_at), "last_deviates_check": int(d.last_deviates_check),
                "slashed_total": str(int(d.slashed_total))}

    def _check_view(self, c: Check, full: bool) -> dict:
        out = {"check_id": int(c.check_id), "dao_id": int(c.dao_id), "chain": c.chain, "safe": c.safe, "tx": c.tx,
               "block": int(c.block), "exec_id": int(c.exec_id), "vote_id": int(c.vote_id), "cid": c.cid,
               "exec_sha": c.exec_sha, "vote_sha": c.vote_sha, "filer": c.filer, "stake": str(int(c.stake)),
               "note": c.note, "filed_at": int(c.filed_at), "status": c.status, "round": int(c.round),
               "judge_deadline": int(c.judge_deadline), "ruling": c.ruling, "ruling_summary": c.ruling_summary,
               "ruled_at": int(c.ruled_at), "contest_deadline": int(c.contest_deadline), "appellant": c.appellant,
               "appeal_bond": str(int(c.appeal_bond)), "appeal_text": c.appeal_text,
               "appeal_vote_id": int(c.appeal_vote_id), "appeal_cid": c.appeal_cid,
               "appeal_deadline": int(c.appeal_deadline), "appeal_ruling": c.appeal_ruling,
               "appeal_summary": c.appeal_summary, "final_verdict": c.final_verdict, "final_how": c.final_how,
               "final_at": int(c.final_at), "severity": c.severity, "severity_bps": int(c.severity_bps),
               "pledge_at_filing": str(int(c.pledge_at_filing)), "slash": str(int(c.slash)),
               "bounty_to": c.bounty_to,
               "settlement": json.loads(c.settlement_json) if c.settlement_json != "" else []}
        if full:
            out["ruling_detail"] = json.loads(c.ruling_json) if c.ruling_json != "" else None
            out["appeal_detail"] = json.loads(c.appeal_json) if c.appeal_json != "" else None
        return out

    @gl.public.view
    def get_config(self) -> typing.Any:
        return {"version": VERSION, "contract": "AsVotedRegistry", "mode": self.mode,
                "exec_reader": self.exec_reader.as_hex.lower(), "vote_reader": self.vote_reader.as_hex.lower(),
                "judge": self.judge.as_hex.lower(), "demo_controllers": json.loads(self.demo_controllers_json),
                "contest_s": int(self.contest_s), "judge_deadline_s": int(self.judge_s),
                "appeal_deadline_s": int(self.appeal_s), "withdraw_delay_s": int(self.withdraw_s),
                "binding_max_age_s": int(self.binding_s), "check_stake": str(CHECK_STAKE),
                "appeal_bond": str(APPEAL_BOND), "min_pledge": str(MIN_PLEDGE),
                "severity_table": [[r[0], r[1], r[2]] for r in SEVERITY],
                "novelty": {"jaccard_bps": NOVEL_JACCARD_BPS, "containment_bps": NOVEL_CONTAIN_BPS,
                            "min_chars": MIN_COUNTER}}

    @gl.public.view
    def get_stats(self) -> typing.Any:
        out = {"daos": int(self.n_daos), "checks": int(self.n_checks)}
        for k in ("status:" + s for s in (ST_PROVISIONAL, ST_CONTESTABLE, ST_APPEALED, ST_FINAL)):
            out[k] = int(self.counts.get(k) or 0)
        for v in (V_AS, V_DEV, V_UNCLEAR):
            out["final:" + v] = int(self.counts.get("final:" + v) or 0)
        for h in ("NO_APPEAL", "RULED_UNCLEAR", "APPEAL_RULED", "APPEAL_EXPIRED", "EXPIRED_UNJUDGED"):
            out["how:" + h] = int(self.counts.get("how:" + h) or 0)
        out["pledges_total"] = str(int(self.pledges_total))
        out["open_total"] = str(int(self.open_total))
        out["claimable_total"] = str(int(self.claimable_total))
        out["claimed_total"] = str(int(self.claimed_total))
        out["received_total"] = str(int(self.received_total))
        return out

    @gl.public.view
    def get_dao(self, dao_id: int) -> typing.Any:
        d = self._dao(dao_id)
        if d is None:
            return {"found": False}
        out = self._dao_view(d)
        out["found"] = True
        return out

    @gl.public.view
    def get_dao_id(self, space: str, chain: str, safe: str) -> int:
        return int(self.dao_by_key.get(str(chain).strip().lower() + "|" + _addr(safe) + "|" + str(space).strip().lower()) or 0)

    @gl.public.view
    def get_daos(self, offset: int, limit: int) -> typing.Any:
        o = max(_as_int(offset, 0), 0)
        lim = min(max(_as_int(limit, 20), 0), MAX_PAGE)
        out = []
        i = o + 1
        while i <= int(self.n_daos) and len(out) < lim:
            d = self.daos.get(u64(i))
            if d is not None:
                out.append(self._dao_view(d))
            i += 1
        return {"total": int(self.n_daos), "daos": out}

    @gl.public.view
    def get_check(self, check_id: int) -> typing.Any:
        c = self._check(check_id)
        if c is None:
            return {"found": False}
        out = self._check_view(c, True)
        out["found"] = True
        return out

    @gl.public.view
    def get_checks(self, offset: int, limit: int) -> typing.Any:
        """Newest first: offset 0 is the latest check."""
        o = max(_as_int(offset, 0), 0)
        lim = min(max(_as_int(limit, 20), 0), MAX_PAGE)
        out = []
        i = int(self.n_checks) - o
        while i >= 1 and len(out) < lim:
            c = self.checks.get(u64(i))
            if c is not None:
                out.append(self._check_view(c, False))
            i -= 1
        return {"total": int(self.n_checks), "checks": out}

    @gl.public.view
    def get_dao_checks(self, dao_id: int, offset: int, limit: int) -> typing.Any:
        did = _as_int(dao_id, 0)
        n = int(self.dao_check_n.get(u64(max(did, 0))) or 0)
        o = max(_as_int(offset, 0), 0)
        lim = min(max(_as_int(limit, 20), 0), MAX_PAGE)
        out = []
        k = n - 1 - o
        while k >= 0 and len(out) < lim:
            cid = int(self.dao_check_at.get(str(did) + "#" + str(k)) or 0)
            c = self.checks.get(u64(cid)) if cid > 0 else None
            if c is not None:
                out.append(self._check_view(c, False))
            k -= 1
        return {"total": n, "checks": out}

    @gl.public.view
    def get_check_id_by_tx(self, chain: str, safe: str, tx_hash: str) -> int:
        return int(self.check_by_tx.get(str(chain).strip().lower() + "|" + _addr(safe) + "|" + _hash32(tx_hash)) or 0)

    @gl.public.view
    def get_open_checks(self, offset: int, limit: int) -> typing.Any:
        """Open checks (oldest first) with what each needs next, for the
        patrol bot and the site. Scans at most SCAN_CAP records from offset."""
        o = max(_as_int(offset, 0), 0)
        lim = min(max(_as_int(limit, 20), 0), MAX_PAGE)
        out = []
        i = o + 1
        scanned = 0
        while i <= int(self.n_checks) and len(out) < lim and scanned < SCAN_CAP:
            c = self.checks.get(u64(i))
            scanned += 1
            if c is not None and c.status in OPEN:
                out.append({"check_id": int(c.check_id), "status": c.status, "round": int(c.round),
                            "filer": c.filer, "judge_deadline": int(c.judge_deadline),
                            "contest_deadline": int(c.contest_deadline), "appeal_deadline": int(c.appeal_deadline)})
            i += 1
        return {"next_offset": i - 1, "done": i > int(self.n_checks), "checks": out}

    @gl.public.view
    def get_standing(self, dao_id: int) -> typing.Any:
        d = self._dao(dao_id)
        if d is None:
            return {"found": False}
        return {"found": True, "dao_id": int(d.dao_id), "space": d.space, "chain": d.chain, "safe": d.safe,
                "controller": d.controller, "pledge": str(int(d.pledge)), "open_checks": int(d.open_checks),
                "as_voted": int(d.as_voted), "deviates": int(d.deviates), "unclear": int(d.unclear),
                "last_deviates_at": int(d.last_deviates_at), "last_deviates_check": int(d.last_deviates_check)}

    @gl.public.view
    def claimable_of(self, who: str) -> typing.Any:
        a = _addr(who)
        return {"address": a, "claimable": str(int(self.claimable.get(a, u256(0)))),
                "claimed": str(int(self.claimed.get(a, u256(0))))}

    def _sums(self, offset: int, count: int) -> dict:
        pledges = 0
        for i in range(offset + 1, min(offset + count, int(self.n_daos)) + 1):
            d = self.daos.get(u64(i))
            if d is not None:
                pledges += int(d.pledge)
        held = 0
        for i in range(offset + 1, min(offset + count, int(self.n_checks)) + 1):
            c = self.checks.get(u64(i))
            if c is not None and c.status in OPEN:
                held += int(c.stake) + int(c.appeal_bond)
        owed = 0
        paid = 0
        ps = [str(x) for x in self.payees]
        for who in ps[offset:offset + count]:
            owed += int(self.claimable.get(who, u256(0)))
            paid += int(self.claimed.get(who, u256(0)))
        return {"pledges": pledges, "open": held, "claimable": owed, "claimed": paid}

    @gl.public.view
    def get_ledger(self) -> typing.Any:
        """The books two ways: running counters, and the same totals
        recomputed from every record (up to SCAN_CAP of each kind; beyond
        that, get_ledger_page). Invariant: received == pledges + open +
        claimable + claimed."""
        big = max(int(self.n_daos), int(self.n_checks), len(self.payees)) > SCAN_CAP
        r = self._sums(0, SCAN_CAP) if not big else None
        received = int(self.received_total)
        books = int(self.pledges_total) + int(self.open_total) + int(self.claimable_total) + int(self.claimed_total)
        bal = int(self.balance)
        held = int(self.pledges_total) + int(self.open_total) + int(self.claimable_total)
        return {"received": str(received), "pledges": str(int(self.pledges_total)), "open": str(int(self.open_total)),
                "claimable": str(int(self.claimable_total)), "claimed": str(int(self.claimed_total)),
                "held_now": str(held), "invariant_holds": received == books,
                "recomputed": ({k: str(r[k]) for k in r} if r is not None else None),
                "views_match_storage": ((r["pledges"] == int(self.pledges_total) and r["open"] == int(self.open_total)
                                         and r["claimable"] == int(self.claimable_total)
                                         and r["claimed"] == int(self.claimed_total)) if r is not None else None),
                "on_chain_balance": str(bal), "balance_minus_held": str(bal - held),
                "note": ("claim() posts a value transfer; on Studio Dev those are queued and not delivered, so "
                         "on_chain_balance can exceed held_now by up to the claimed total.")}

    @gl.public.view
    def get_ledger_page(self, offset: int, count: int) -> typing.Any:
        o = max(_as_int(offset, 0), 0)
        n = min(max(_as_int(count, SCAN_CAP), 1), SCAN_CAP)
        r = self._sums(o, n)
        longest = max(int(self.n_daos), int(self.n_checks), len(self.payees))
        return {"offset": o, "count": n, "done": o + n >= longest, "pledges": str(r["pledges"]),
                "open": str(r["open"]), "claimable": str(r["claimable"]), "claimed": str(r["claimed"])}
