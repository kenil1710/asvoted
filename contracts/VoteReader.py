# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *
from dataclasses import dataclass
import hashlib
import json
import typing

# VoteReader - what token holders voted for, proven.
#
# read_proposal(cid, chain, safe). Every validator, independently:
#   1. fetches the proposal by IPFS CID from allowlisted gateways and hashes
#      the bytes IN CODE: a CIDv1 raw leaf is sha2-256 of the bytes; a CIDv0 /
#      dag-pb CID is sha2-256 of the single-chunk UnixFS node built around
#      them. Bytes that do not hash to the CID are never used. The signed
#      Snapshot message inside (space, author, title, body, type, choices,
#      start, end, snapshot block) is therefore exactly what was proposed;
#   2. looks the CID up on the Snapshot hub (GraphQL) and requires the hub's
#      record to be the SAME proposal: same CID, space, author, title, body,
#      type, choices, start and end. A proposal edited later has a new CID, so
#      the old CID is no longer the hub's proposal and is refused. From the hub
#      it takes only what IPFS cannot hold: state (must be "closed"),
#      scores_state (must be "final"), scores, scores_total, quorum;
#   3. code computes whether the proposal PASSED from the scores and the
#      voting type: "basic" (For / Against / Abstain) and "single-choice" with
#      an approving winning label. Every other type, a tie, an unknown label or
#      a "rejection" quorum is UNCLEAR, never a guess;
#   4. binding: reads the space's own settings from the hub and records
#      whether this (Safe, chain) is listed among its treasuries at read time;
#   5. extracts every ENS name in the text (ASCII labels ending in ".eth") and
#      resolves each on Ethereum from TWO RPCs at the pinned finalized block
#      and, when the space votes on Ethereum, also at the proposal's own
#      snapshot block. A name counts only if every resolution agrees.
# read_space(space, chain, safe) is the binding alone, plus the space's
# admins and moderators, for registration and control claims.
# Validators accept the leader's record only if it is byte-identical to their
# own. There is no model in this contract.

VERSION = "1.0.0"

IPFS_GATEWAYS = ("https://snapshot.4everland.link/ipfs/", "https://ipfs.snapshot.box/ipfs/")
SNAPSHOT_HUB = "https://hub.snapshot.org/graphql"
ENS_REGISTRY = "0x00000000000c2e074ec69a0dfb2997ba6c7d2e1e"

MAX_SOURCE_BYTES = 200000
MAX_UNIXFS_CHUNK = 262144
MAX_BODY_CHARS = 100000
MAX_ENS = 24
MAX_SPACE = 64
REREAD_S = 600                 # a (cid, chain, safe) may be read again after this, to refresh the binding

APPROVE_WORDS = ("for", "yes", "yae", "yay", "aye", "approve", "approved", "accept", "in favor", "in favour",
                 "support", "agree", "pass", "execute", "enable", "fund", "adopt", "ratify", "confirm")
REJECT_WORDS = ("against", "no", "nay", "reject", "abstain", "do not", "don't", "dont", "oppose", "deny",
                "decline", "not")

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

# ==== shared rpc helpers: generated from contracts/shared/rpc.py by tools/inline_shared.py; edit there ====
# --- HTTP / JSON-RPC ----------------------------------------------------------

class ReadFailed(Exception):
    """An endpoint did not answer, or answered something that is not a
    JSON-RPC result or a revert. The read is refused; nothing is guessed."""


class Disagree(Exception):
    """The two RPCs of a chain answered differently."""


def _status(res: typing.Any) -> int:
    s = getattr(res, "status_code", None)
    if s is None:
        s = getattr(res, "status", None)
    return 0 if s is None else int(s)


def _raw(res: typing.Any) -> bytes:
    b = getattr(res, "body", None)
    if b is None:
        return b""
    if isinstance(b, bytes):
        return b
    return str(b).encode("utf-8")


def rpc_url_allowed(url: str) -> bool:
    for ch in CHAINS:
        if url in CHAINS[ch][1]:
            return True
    return False


def parse_batch(doc: typing.Any, n: int) -> list:
    """A JSON-RPC batch answer -> [("ok", result) | ("revert", None)] in call
    order. An error that is not an EVM revert raises."""
    if isinstance(doc, dict):
        doc = [doc]
    if not isinstance(doc, list):
        raise ReadFailed("batch")
    by_id = {}
    for item in doc:
        if isinstance(item, dict) and isinstance(item.get("id"), int) and not isinstance(item.get("id"), bool):
            by_id[item["id"]] = item
    out = []
    for i in range(n):
        item = by_id.get(i)
        if item is None:
            raise ReadFailed("missing id")
        if "error" in item and item["error"] is not None:
            err = item["error"]
            msg = str(err.get("message", "")).lower() if isinstance(err, dict) else ""
            code = err.get("code") if isinstance(err, dict) else None
            if code == 3 or msg.find("revert") >= 0:
                out.append(["revert", None])
                continue
            raise ReadFailed("rpc error " + msg[:40])
        if "result" not in item:
            raise ReadFailed("no result")
        out.append(["ok", item["result"]])
    return out


def rpc_send(url: str, calls: list) -> list:
    """One endpoint, every call, in chunks of the endpoint's batch size."""
    if not rpc_url_allowed(url):
        raise ReadFailed("rpc not allowed")
    cap = RPC_BATCH.get(url, 10)
    out = []
    i = 0
    while i < len(calls):
        chunk = calls[i:i + cap]
        body = json.dumps([{"jsonrpc": "2.0", "id": j, "method": chunk[j][0], "params": chunk[j][1]}
                           for j in range(len(chunk))])
        res = None
        why = ""
        for _ in range(RPC_TRIES):
            try:
                res = gl.nondet.web.request(url, method="POST", body=body,
                                            headers={"Content-Type": "application/json"})
            except Exception:
                res = None
                why = "transport"
                continue
            st = _status(res)
            if st == 200:
                break
            why = "http " + str(st)
            res = None
            if st != 429 and st < 500:
                break
        if res is None:
            raise ReadFailed(why)
        try:
            doc = json.loads(_raw(res).decode("utf-8", errors="replace"))
        except Exception:
            raise ReadFailed("json")
        out = out + parse_batch(doc, len(chunk))
        i += cap
    return out


def dual_read(chain: str, calls: list, project: typing.Any) -> list:
    """The same calls against BOTH RPCs of the chain. `project(call, result)`
    keeps only the fields this contract uses; the projected answers must be
    identical, or Disagree is raised. Returns the projected answers."""
    urls = CHAINS[chain][1]
    a = rpc_send(urls[0], calls)
    b = rpc_send(urls[1], calls)
    pa = [project(calls[i], a[i]) for i in range(len(calls))]
    pb = [project(calls[i], b[i]) for i in range(len(calls))]
    if _canon(pa) != _canon(pb):
        raise Disagree("rpc answers differ")
    return pa


def _block_of(r: typing.Any) -> typing.Any:
    if not isinstance(r, list) or r[0] != "ok" or not isinstance(r[1], dict):
        return None
    blk = r[1]
    try:
        num = int(str(blk.get("number")), 16)
        ts = int(str(blk.get("timestamp")), 16)
    except Exception:
        return None
    hsh = _hash32(blk.get("hash", ""))
    if hsh == "":
        return None
    return {"number": num, "hash": hsh, "timestamp": ts}


def _proj_basic(call: list, r: typing.Any) -> typing.Any:
    if call[0] == "eth_getBlockByNumber":
        return _block_of(r)
    if call[0] == "eth_chainId":
        if isinstance(r, list) and r[0] == "ok" and isinstance(r[1], str):
            try:
                return int(r[1], 16)
            except Exception:
                return None
        return None
    return r


def finalized_each(chain: str) -> typing.Any:
    """The finalized block as each RPC reports it, and its chain id. The two
    may legitimately differ by a block or two, so they are NOT compared;
    the pinned block is then read from both and must agree."""
    out = []
    for url in CHAINS[chain][1]:
        got = rpc_send(url, [["eth_getBlockByNumber", ["finalized", False]], ["eth_chainId", []]])
        blk = _block_of(got[0])
        cid = _proj_basic(["eth_chainId", []], got[1])
        if blk is None or cid != CHAINS[chain][0]:
            return None
        out.append(blk)
    return out


def pin_block(chain: str, block: int) -> dict:
    """Leader (block < 0): the lower of the two RPCs' finalized blocks.
    Validator: the leader's block, if it is final for this node on both RPCs
    and no more than LEADER_LAG_S older than this node's own finalized block.
    Returns {"block": {...}} or {"refused": ...} / {"reject": ...}."""
    try:
        fins = finalized_each(chain)
    except ReadFailed:
        return {"refused": "RPC_UNREADABLE"}
    if fins is None:
        return {"refused": "RPC_WRONG_CHAIN_OR_UNREADABLE"}
    low = fins[0] if fins[0]["number"] <= fins[1]["number"] else fins[1]
    n = low["number"] if block < 0 else block
    if n > low["number"]:
        return {"reject": "BLOCK_NOT_FINALIZED_FOR_VALIDATOR"}
    try:
        got = dual_read(chain, [["eth_getBlockByNumber", [hex(n), False]]], _proj_basic)
    except ReadFailed:
        return {"refused": "RPC_UNREADABLE"}
    except Disagree:
        return {"refused": "RPC_DISAGREE_ON_PINNED_BLOCK"}
    blk = got[0]
    if blk is None or blk["number"] != n:
        return {"refused": "RPC_UNREADABLE"}
    if block >= 0 and blk["timestamp"] < low["timestamp"] - LEADER_LAG_S:
        return {"reject": "LEADER_BLOCK_TOO_OLD"}
    return {"block": blk}
# ==== end shared rpc ====


# =============================================================================
# CID
# =============================================================================

B32 = "abcdefghijklmnopqrstuvwxyz234567"
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b32_decode(s: str) -> typing.Any:
    bits = 0
    nbits = 0
    out = []
    for ch in s:
        k = B32.find(ch)
        if k < 0:
            return None
        bits = (bits << 5) | k
        nbits += 5
        if nbits >= 8:
            nbits -= 8
            out.append((bits >> nbits) & 0xff)
    if nbits >= 5 or (bits & ((1 << nbits) - 1)) != 0:
        return None
    return bytes(out)


def b32_encode(b: bytes) -> str:
    bits = 0
    nbits = 0
    out = ""
    for x in b:
        bits = (bits << 8) | x
        nbits += 8
        while nbits >= 5:
            nbits -= 5
            out += B32[(bits >> nbits) & 31]
    if nbits > 0:
        out += B32[(bits << (5 - nbits)) & 31]
    return out


def b58_decode(s: str) -> typing.Any:
    n = 0
    for ch in s:
        k = B58.find(ch)
        if k < 0:
            return None
        n = n * 58 + k
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n > 0 else b""
    lead = 0
    while lead < len(s) and s[lead] == "1":
        lead += 1
    return bytes(lead) + body


def parse_cid(text: typing.Any) -> dict:
    """"ipfs://<cid>" or a bare CID -> {"cid", "codec", "digest"} or {"error"}.
    sha2-256 only: CIDv0 ("Qm...") and canonical CIDv1 base32 ("b...")."""
    t = str(text)
    if t != t.strip() or t == "":
        return {"error": "CID_NOT_CANONICAL"}
    if t.startswith("ipfs://"):
        t = t[7:]
    if len(t) > 100:
        return {"error": "CID_BAD"}
    if t.startswith("Qm") and len(t) == 46:
        raw = b58_decode(t)
        if raw is None or len(raw) != 34 or raw[0] != 0x12 or raw[1] != 0x20:
            return {"error": "CID_BAD"}
        return {"cid": t, "codec": "dag-pb", "digest": raw[2:].hex()}
    if t.startswith("b"):
        raw = b32_decode(t[1:])
        if raw is None or len(raw) != 36 or raw[0] != 0x01:
            return {"error": "CID_BAD"}
        if raw[2] != 0x12 or raw[3] != 0x20:
            return {"error": "CID_NOT_SHA256"}
        if raw[1] == 0x55:
            codec = "raw"
        elif raw[1] == 0x70:
            codec = "dag-pb"
        else:
            return {"error": "CID_CODEC_NOT_SUPPORTED"}
        if "b" + b32_encode(raw) != t:
            return {"error": "CID_NOT_CANONICAL"}
        return {"cid": t, "codec": codec, "digest": raw[4:].hex()}
    return {"error": "CID_BAD"}


def _varint(n: int) -> bytes:
    out = []
    while True:
        b = n & 0x7f
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def unixfs_node(data: bytes) -> bytes:
    u = b"\x08\x02"
    if len(data) > 0:
        u += b"\x12" + _varint(len(data)) + data
    u += b"\x18" + _varint(len(data))
    return b"\x0a" + _varint(len(u)) + u


def cid_matches(pc: dict, body: bytes) -> bool:
    if pc["codec"] == "raw":
        return hashlib.sha256(body).hexdigest() == pc["digest"]
    if len(body) > MAX_UNIXFS_CHUNK:
        return False
    return hashlib.sha256(unixfs_node(body)).hexdigest() == pc["digest"]


# =============================================================================
# proposal
# =============================================================================

def _str_list(v: typing.Any) -> typing.Any:
    if not isinstance(v, list):
        return None
    out = []
    for x in v:
        if not isinstance(x, str):
            return None
        out.append(x)
    return out


def proposal_from_ipfs(body: bytes) -> dict:
    """The signed Snapshot message -> its fields, or {"error"}. Layouts: the
    EIP-712 envelope with types.Proposal, the same with types.UpdateProposal
    (an edit before voting; timing then comes from the hub, cross-checked by
    proposal id), and the legacy {"msg": "<json>"} envelope."""
    try:
        doc = json.loads(body.decode("utf-8"))
    except Exception:
        return {"error": "PROPOSAL_NOT_JSON"}
    if not isinstance(doc, dict):
        return {"error": "PROPOSAL_NOT_JSON"}
    author = _addr(doc.get("address", ""))
    data = doc.get("data")
    out = {"author": author, "update_of": ""}
    if isinstance(data, dict) and isinstance(data.get("message"), dict) and isinstance(data.get("types"), dict):
        m = data["message"]
        tps = data["types"]
        if "Proposal" in tps:
            out["space"] = m.get("space")
            out["start"] = m.get("start")
            out["end"] = m.get("end")
            out["snapshot"] = m.get("snapshot")
            out["timestamp"] = m.get("timestamp")
        elif "UpdateProposal" in tps:
            out["space"] = m.get("space")
            out["update_of"] = str(m.get("proposal", "")).lower()
            out["start"] = None
            out["end"] = None
            out["snapshot"] = None
            out["timestamp"] = m.get("timestamp")
        else:
            return {"error": "NOT_A_SNAPSHOT_PROPOSAL"}
        out["title"] = m.get("title")
        out["body"] = m.get("body")
        out["type"] = m.get("type")
        out["choices"] = _str_list(m.get("choices"))
        if _addr(m.get("from", "")) != "" and _addr(m.get("from", "")) != author:
            return {"error": "ENVELOPE_AUTHOR_MISMATCH"}
    elif isinstance(doc.get("msg"), str):
        try:
            mm = json.loads(doc["msg"])
        except Exception:
            return {"error": "PROPOSAL_NOT_JSON"}
        if not isinstance(mm, dict) or mm.get("type") != "proposal" or not isinstance(mm.get("payload"), dict):
            return {"error": "NOT_A_SNAPSHOT_PROPOSAL"}
        pl = mm["payload"]
        out["space"] = mm.get("space")
        out["title"] = pl.get("name")
        out["body"] = pl.get("body")
        out["type"] = None
        md = pl.get("metadata")
        if isinstance(md, dict) and isinstance(md.get("type"), str):
            out["type"] = md.get("type")
        out["choices"] = _str_list(pl.get("choices"))
        out["start"] = _as_int(pl.get("start"), -1)
        out["end"] = _as_int(pl.get("end"), -1)
        out["snapshot"] = _as_int(pl.get("snapshot"), -1)
        out["timestamp"] = _as_int(mm.get("timestamp"), -1)
    else:
        return {"error": "NOT_A_SNAPSHOT_PROPOSAL"}
    if not isinstance(out["title"], str) or not isinstance(out["body"], str) or not isinstance(out["space"], str) \
            or author == "" or out["choices"] is None:
        return {"error": "NOT_A_SNAPSHOT_PROPOSAL"}
    out["space"] = out["space"].lower()
    return out


def _qs(q: str) -> str:
    out = ""
    for ch in q:
        if ch.isalnum() or ch in "-_.~":
            out += ch
        else:
            out += "%" + ("0" + hex(ord(ch))[2:].upper())[-2:]
    return out


def _gql_str(s: str) -> str:
    """A GraphQL string literal for an id that was already validated to be
    plain ASCII (CID alphabet, ENS-like space id)."""
    return '"' + s + '"'


def hub_query_proposal(cid: str, space: str) -> str:
    q = ("{proposals(where:{ipfs:" + _gql_str(cid) + "}){id ipfs author space{id} type title body choices "
         "start end snapshot state scores scores_total scores_state quorum quorumType network}"
         " space(id:" + _gql_str(space) + "){id network voting{type} treasuries{address network} admins moderators}}")
    return SNAPSHOT_HUB + "?query=" + _qs(q)


def hub_query_space(space: str) -> str:
    q = "{space(id:" + _gql_str(space) + "){id network treasuries{address network} admins moderators}}"
    return SNAPSHOT_HUB + "?query=" + _qs(q)


def allowed_url(url: str) -> bool:
    for g in IPFS_GATEWAYS:
        if url.startswith(g):
            return "error" not in parse_cid(url[len(g):])
    if url.startswith(SNAPSHOT_HUB + "?query="):
        return True
    return rpc_url_allowed(url)


def http_get(url: str) -> dict:
    if not allowed_url(url):
        return {"ok": False, "http": -2, "body": b""}
    try:
        res = gl.nondet.web.get(url)
    except Exception:
        return {"ok": False, "http": -1, "body": b""}
    return {"ok": True, "http": _status(res), "body": _raw(res)}


def space_ok(s: str) -> bool:
    if len(s) == 0 or len(s) > MAX_SPACE:
        return False
    for ch in s:
        if not (ch.isalnum() and ch.isascii()) and ch not in "-._":
            return False
    return s == s.lower()


def binding_of(sp: typing.Any, chain: str, safe: str) -> dict:
    """The space settings -> whether (safe, chain) is a listed treasury."""
    if not isinstance(sp, dict):
        return {"error": "SPACE_NOT_FOUND"}
    tr = sp.get("treasuries")
    if not isinstance(tr, list):
        tr = []
    want = str(CHAINS[chain][0])
    listed = False
    rows = []
    for t in tr:
        if not isinstance(t, dict):
            continue
        a = _addr(t.get("address", ""))
        n = str(t.get("network", ""))
        if a != "":
            rows.append([a, n])
        if a == safe and n == want:
            listed = True
    adm = []
    for k in ("admins", "moderators"):
        for a in sp.get(k) or []:
            x = _addr(a)
            if x != "" and x not in adm:
                adm.append(x)
    return {"listed": listed, "treasuries": rows, "controllers": adm, "network": str(sp.get("network", ""))}


def _num(v: typing.Any) -> typing.Any:
    if isinstance(v, bool):
        return None
    if isinstance(v, int) or isinstance(v, float):
        return v
    return None


def _label(s: str) -> str:
    """A choice label, lowercased, with leading non-letters ("1. ", "✅ ")
    and surrounding spaces removed."""
    t = s.strip().lower()
    i = 0
    while i < len(t) and not t[i].isalpha():
        i += 1
    return t[i:].strip()


def _starts_word(t: str, w: str) -> bool:
    if not t.startswith(w):
        return False
    return len(t) == len(w) or not t[len(w)].isalnum()


def label_kind(s: str) -> str:
    t = _label(s)
    if t.startswith("not ") or t.find(" not ") >= 0:
        return "REJECT"
    for w in REJECT_WORDS:
        if _starts_word(t, w.strip()):
            return "REJECT"
    for w in APPROVE_WORDS:
        if _starts_word(t, w):
            return "APPROVE"
    return "UNKNOWN"


def outcome_of(vtype: str, choices: list, scores: list, total: typing.Any, quorum: typing.Any,
               quorum_type: str) -> dict:
    """PASSED / FAILED / UNCLEAR, computed by code from the final scores."""
    if len(scores) != len(choices) or len(choices) < 2:
        return {"outcome": "UNCLEAR", "why": "scores do not line up with the choices"}
    for s in scores:
        if _num(s) is None or s < 0:
            return {"outcome": "UNCLEAR", "why": "a score is not a number"}
    if _num(total) is None:
        return {"outcome": "UNCLEAR", "why": "scores_total is not a number"}
    if quorum_type not in ("", "default"):
        return {"outcome": "UNCLEAR", "why": "quorum type '" + quorum_type[:20] + "' is not supported"}
    q = _num(quorum)
    if q is None:
        q = 0
    if vtype == "basic":
        if [_label(c) for c in choices[:2]] != ["for", "against"] or (len(choices) == 3 and _label(choices[2]) != "abstain") \
                or len(choices) > 3:
            return {"outcome": "UNCLEAR", "why": "basic voting with unexpected choices"}
        if q > 0 and total < q:
            return {"outcome": "FAILED", "why": "quorum not reached"}
        if scores[0] > scores[1]:
            return {"outcome": "PASSED", "why": "For > Against" + (", quorum reached" if q > 0 else "")}
        return {"outcome": "FAILED", "why": "For <= Against"}
    if vtype == "single-choice":
        best = 0
        for i in range(1, len(scores)):
            if scores[i] > scores[best]:
                best = i
        for i in range(len(scores)):
            if i != best and scores[i] == scores[best]:
                return {"outcome": "UNCLEAR", "why": "the top choices are tied"}
        if q > 0 and total < q:
            return {"outcome": "FAILED", "why": "quorum not reached"}
        k = label_kind(choices[best])
        if k == "APPROVE":
            return {"outcome": "PASSED", "why": "winning choice '" + choices[best][:60] + "' approves"}
        if k == "REJECT":
            return {"outcome": "FAILED", "why": "winning choice '" + choices[best][:60] + "' does not approve"}
        return {"outcome": "UNCLEAR", "why": "winning choice '" + choices[best][:60] + "' is not a yes/no label"}
    return {"outcome": "UNCLEAR", "why": "voting type '" + str(vtype)[:20] + "' is not supported"}


# =============================================================================
# ENS
# =============================================================================

def _ens_char(ch: str) -> bool:
    return ("a" <= ch <= "z") or ("0" <= ch <= "9") or ch == "-"


def ens_names(text: str) -> list:
    """Every ASCII ENS name ending in ".eth" in the text, lowercased, in
    order of first appearance. A name glued to a letter, digit or '@' on
    the left, or to a name character on the right, is not a name."""
    low = text.lower()
    out = []
    k = low.find(".eth")
    while k >= 0:
        end = k + 4
        if end < len(low) and (_ens_char(low[end]) or (low[end] == "." and end + 1 < len(low) and _ens_char(low[end + 1]))):
            k = low.find(".eth", k + 1)
            continue
        i = k
        while i > 0 and (_ens_char(low[i - 1]) or (low[i - 1] == "." and i - 2 >= 0 and _ens_char(low[i - 2]))):
            i -= 1
        name = low[i:end]
        ok = i < k and (i == 0 or low[i - 1] not in "@/")
        if ok:
            for lab in name.split("."):
                if lab == "" or lab.startswith("-") or lab.endswith("-"):
                    ok = False
        if ok and name not in out:
            out.append(name)
        k = low.find(".eth", k + 1)
    return out


def namehash(name: str) -> bytes:
    node = bytes(32)
    labels = name.split(".")
    for i in range(len(labels) - 1, -1, -1):
        node = keccak256(node + keccak256(labels[i].encode("ascii")))
    return node


def _proj_word(call: list, r: typing.Any) -> typing.Any:
    if not isinstance(r, list) or r[0] != "ok" or not isinstance(r[1], str):
        return ""
    t = r[1].lower()
    if not t.startswith("0x") or len(t) != 66:
        return ""
    return "0x" + t[26:]


def resolve_names(names: list, block: int) -> dict:
    """name -> address at `block`, from both Ethereum RPCs. Unresolvable
    names are left out. Raises ReadFailed / Disagree."""
    out = {}
    if len(names) == 0:
        return out
    bh = hex(block)
    nodes = [namehash(n) for n in names]
    calls = [["eth_call", [{"to": ENS_REGISTRY, "data": "0x0178b8bf" + nd.hex()}, bh]] for nd in nodes]
    res = dual_read("ethereum", calls, _proj_word)
    calls2 = []
    idx = []
    for i in range(len(names)):
        r = res[i]
        if r != "" and r != ZERO and _addr(r) != "":
            calls2.append(["eth_call", [{"to": r, "data": "0x3b3b57de" + nodes[i].hex()}, bh]])
            idx.append(i)
    if len(calls2) == 0:
        return out
    res2 = dual_read("ethereum", calls2, _proj_word)
    for j in range(len(idx)):
        a = _addr(res2[j])
        if a != "" and a != ZERO:
            out[names[idx[j]]] = a
    return out


# =============================================================================
# the read
# =============================================================================

def fetch_ipfs(pc: dict) -> dict:
    tried = []
    for g in IPFS_GATEWAYS:
        got = http_get(g + pc["cid"])
        tried.append(got["http"])
        if got["ok"] and got["http"] == 200 and len(got["body"]) <= MAX_SOURCE_BYTES:
            if cid_matches(pc, got["body"]):
                return {"body": got["body"]}
    if 200 in tried:
        return {"refused": "IPFS_CONTENT_DOES_NOT_MATCH_CID"}
    return {"refused": "IPFS_FETCH_FAILED"}


def _hub_json(url: str) -> typing.Any:
    got = http_get(url)
    if not got["ok"] or got["http"] != 200:
        return None
    try:
        doc = json.loads(got["body"].decode("utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("data"), dict):
        return None
    return doc["data"]


def read_proposal(p: dict, now: int, block: int) -> dict:
    pc = p["cid"]
    f = fetch_ipfs(pc)
    if "refused" in f:
        return f
    ip = proposal_from_ipfs(f["body"])
    if "error" in ip:
        return {"refused": ip["error"]}
    if not space_ok(ip["space"]):
        return {"refused": "SPACE_ID_NOT_SUPPORTED"}
    if len(ip["title"]) + len(ip["body"]) > MAX_BODY_CHARS:
        return {"refused": "PROPOSAL_TOO_LARGE"}
    hd = _hub_json(hub_query_proposal(pc["cid"], ip["space"]))
    if hd is None:
        return {"refused": "SNAPSHOT_HUB_UNREADABLE"}
    rows = hd.get("proposals")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return {"refused": "CID_IS_NOT_THE_HUBS_CURRENT_PROPOSAL"}
    h = rows[0]
    hs = h.get("space")
    hub_space = str(hs.get("id", "")).lower() if isinstance(hs, dict) else ""
    if str(h.get("ipfs", "")) != pc["cid"] or hub_space != ip["space"] or _addr(h.get("author", "")) != ip["author"] \
            or h.get("title") != ip["title"] or h.get("body") != ip["body"] or _str_list(h.get("choices")) != ip["choices"]:
        return {"refused": "HUB_RECORD_DIFFERS_FROM_IPFS"}
    pid = str(h.get("id", "")).lower()
    if not pid.startswith("0x") or not _is_hex(pid[2:], 64):
        return {"refused": "SNAPSHOT_HUB_UNREADABLE"}
    if ip["update_of"] != "" and ip["update_of"] != pid:
        return {"refused": "HUB_RECORD_DIFFERS_FROM_IPFS"}
    vtype = ip["type"] if isinstance(ip["type"], str) else str(h.get("type", ""))
    if isinstance(ip["type"], str) and h.get("type") != ip["type"]:
        # A space that enforces one voting type overrides the type in the
        # signed message; the hub then reports the enforced one. Accepted only
        # when the space's own settings say so.
        sv = hd.get("space")
        enforced = sv.get("voting") if isinstance(sv, dict) else None
        if not isinstance(enforced, dict) or enforced.get("type") != h.get("type") or not isinstance(h.get("type"), str):
            return {"refused": "HUB_RECORD_DIFFERS_FROM_IPFS"}
        vtype = h["type"]
    start = _as_int(h.get("start"), -1)
    end = _as_int(h.get("end"), -1)
    snap = _as_int(h.get("snapshot"), -1)
    if ip["start"] is not None and (ip["start"] != start or ip["end"] != end or ip["snapshot"] != snap):
        return {"refused": "HUB_RECORD_DIFFERS_FROM_IPFS"}
    if start <= 0 or end <= start:
        return {"refused": "SNAPSHOT_HUB_UNREADABLE"}
    if h.get("state") != "closed" or end > now:
        return {"refused": "PROPOSAL_NOT_CLOSED"}
    if h.get("scores_state") != "final":
        return {"refused": "SCORES_NOT_FINAL"}
    scores = h.get("scores")
    if not isinstance(scores, list):
        return {"refused": "SNAPSHOT_HUB_UNREADABLE"}
    oc = outcome_of(vtype, ip["choices"], scores, h.get("scores_total"), h.get("quorum"), str(h.get("quorumType") or ""))
    b = binding_of(hd.get("space"), p["chain"], p["safe"])
    if "error" in b:
        return {"refused": b["error"]}
    text = "# " + ip["title"] + "\n\n" + ip["body"]
    names = ens_names(text)
    if len(names) > MAX_ENS:
        return {"refused": "TOO_MANY_ENS_NAMES"}
    pin = pin_block("ethereum", block)
    if "block" not in pin:
        return pin
    eb = pin["block"]
    ens = {}
    at = [eb["number"]]
    if b["network"] == "1" and snap > 0 and snap < eb["number"]:
        at.append(snap)
    try:
        maps = [resolve_names(names, n) for n in at]
    except ReadFailed:
        return {"refused": "ENS_UNREADABLE", "pinned": eb}
    except Disagree:
        return {"refused": "ENS_RPC_DISAGREE", "pinned": eb}
    for nm in names:
        a = maps[0].get(nm, "")
        same = a != ""
        for m in maps[1:]:
            if m.get(nm, "") != a:
                same = False
        if same:
            ens[nm] = a
    return {
        "cid": pc["cid"], "proposal_id": pid, "space": ip["space"], "author": ip["author"],
        "title": ip["title"], "body_sha256": _sha(ip["body"]), "text": text,
        "type": vtype, "choices": ip["choices"], "start": start, "end": end, "snapshot": snap,
        "scores": [repr(float(s)) for s in scores], "scores_total": repr(float(h.get("scores_total"))),
        "quorum": repr(float(_num(h.get("quorum")) or 0)), "outcome": oc["outcome"], "outcome_why": oc["why"],
        "chain": p["chain"], "safe": p["safe"], "listed": b["listed"], "treasuries": b["treasuries"],
        "controllers": b["controllers"], "space_network": b["network"],
        "ens_names": names, "ens": ens, "ens_blocks": at, "pinned": eb,
    }


def read_space(p: dict) -> dict:
    hd = _hub_json(hub_query_space(p["space"]))
    if hd is None:
        return {"refused": "SNAPSHOT_HUB_UNREADABLE"}
    b = binding_of(hd.get("space"), p["chain"], p["safe"])
    if "error" in b:
        return {"refused": b["error"]}
    if str(hd["space"].get("id", "")).lower() != p["space"]:
        return {"refused": "SPACE_NOT_FOUND"}
    return {"space": p["space"], "chain": p["chain"], "safe": p["safe"], "listed": b["listed"],
            "treasuries": b["treasuries"], "controllers": b["controllers"], "space_network": b["network"]}


def validate_proposal(theirs: typing.Any, p: dict, now: int) -> bool:
    if not isinstance(theirs, dict):
        return False
    pinned = theirs.get("pinned")
    if isinstance(pinned, dict) and isinstance(pinned.get("number"), int):
        mine = read_proposal(p, now, int(pinned["number"]))
    else:
        mine = read_proposal(p, now, -1)
        if "pinned" in mine:
            return False
    if "reject" in mine:
        return False
    return _canon(mine) == _canon(theirs)


# =============================================================================
# storage
# =============================================================================

@gl.storage.allow
@dataclass
class Proposal:
    vote_id: u64
    cid: str
    proposal_id: str
    space: str
    author: str
    title: str
    text: str
    body_sha256: str
    vtype: str
    choices_json: str
    scores_json: str
    scores_total: str
    quorum: str
    start: u64
    end: u64
    snapshot: u64
    outcome: str
    outcome_why: str
    chain: str
    safe: str
    listed: bool
    treasuries_json: str
    controllers_json: str
    space_network: str
    ens_json: str
    ens_names_json: str
    ens_blocks_json: str
    pinned_block: u64
    pinned_hash: str
    read_at: u64
    reader: Address
    evidence_sha256: str


@gl.storage.allow
@dataclass
class SpaceBinding:
    bind_id: u64
    space: str
    chain: str
    safe: str
    listed: bool
    treasuries_json: str
    controllers_json: str
    space_network: str
    read_at: u64
    reader: Address


class VoteReader(gl.contract.Contract):
    n: u64
    props: gl.storage.TreeMap[u64, Proposal]
    latest: gl.storage.TreeMap[str, u64]         # cid|chain|safe -> latest vote_id
    nb: u64
    binds: gl.storage.TreeMap[u64, SpaceBinding]
    latest_bind: gl.storage.TreeMap[str, u64]    # space|chain|safe -> latest bind_id

    def __init__(self) -> None:
        self.n = u64(0)
        self.nb = u64(0)

    def _now(self) -> int:
        return _epoch_from_iso(gl.message.raw.get("datetime", ""))

    def _target(self, chain: str, safe: str) -> tuple:
        ch = str(chain).strip().lower()
        if ch not in CHAINS:
            raise gl.vm.UserError("REFUSED: UNSUPPORTED_CHAIN")
        sf = _addr(safe)
        if sf == "" or sf == ZERO:
            raise gl.vm.UserError("REFUSED: BAD_SAFE_ADDRESS")
        return (ch, sf)

    @gl.public.write
    def read_proposal(self, cid: str, chain: str, safe: str) -> typing.Any:
        """Read a Snapshot proposal by IPFS CID, and whether (safe, chain) is
        listed in its space's treasuries right now. Refusals raise before any
        write."""
        now = self._now()
        if now <= 0:
            raise gl.vm.UserError("REFUSED: NO_CLOCK")
        pc = parse_cid(cid)
        if "error" in pc:
            raise gl.vm.UserError("REFUSED: " + pc["error"])
        ch, sf = self._target(chain, safe)
        key = pc["cid"] + "|" + ch + "|" + sf
        prev = int(self.latest.get(key) or 0)
        if prev != 0:
            old = self.props[u64(prev)]
            if now - int(old.read_at) < REREAD_S:
                raise gl.vm.UserError("REFUSED: READ_RECENTLY_AS_" + str(prev))
        p = {"cid": pc, "chain": ch, "safe": sf}

        def leader() -> dict:
            return read_proposal(p, now, -1)

        def validator(res: gl.vm.Result) -> bool:
            if not isinstance(res, gl.vm.Return):
                return False
            return validate_proposal(res.calldata, p, now)

        ev = gl.vm.run_nondet(leader, validator)
        if not isinstance(ev, dict):
            raise gl.vm.UserError("REFUSED: EVIDENCE_UNREADABLE")
        if "refused" in ev:
            raise gl.vm.UserError("REFUSED: " + str(ev["refused"])[:80])
        if "reject" in ev:
            raise gl.vm.UserError("REFUSED: " + str(ev["reject"])[:80])
        # --- writes (nothing below can refuse)
        vid = int(self.n) + 1
        self.props[u64(vid)] = Proposal(
            vote_id=u64(vid), cid=ev["cid"], proposal_id=ev["proposal_id"], space=ev["space"], author=ev["author"],
            title=ev["title"], text=ev["text"], body_sha256=ev["body_sha256"], vtype=ev["type"],
            choices_json=_canon(ev["choices"]), scores_json=_canon(ev["scores"]), scores_total=ev["scores_total"],
            quorum=ev["quorum"], start=u64(ev["start"]), end=u64(ev["end"]), snapshot=u64(max(ev["snapshot"], 0)),
            outcome=ev["outcome"], outcome_why=ev["outcome_why"], chain=ch, safe=sf, listed=bool(ev["listed"]),
            treasuries_json=_canon(ev["treasuries"]), controllers_json=_canon(ev["controllers"]),
            space_network=ev["space_network"], ens_json=_canon(ev["ens"]), ens_names_json=_canon(ev["ens_names"]),
            ens_blocks_json=_canon(ev["ens_blocks"]), pinned_block=u64(int(ev["pinned"]["number"])),
            pinned_hash=ev["pinned"]["hash"], read_at=u64(now), reader=gl.message.sender_address,
            evidence_sha256=_sha(_canon(ev)))
        self.latest[key] = u64(vid)
        self.n = u64(vid)
        return {"vote_id": vid, "outcome": ev["outcome"], "listed": bool(ev["listed"]), "space": ev["space"]}

    @gl.public.write
    def read_space(self, space: str, chain: str, safe: str) -> typing.Any:
        """Whether (safe, chain) is listed in the space's treasuries right
        now, and who the space's admins and moderators are."""
        now = self._now()
        if now <= 0:
            raise gl.vm.UserError("REFUSED: NO_CLOCK")
        sp = str(space).strip().lower()
        if not space_ok(sp):
            raise gl.vm.UserError("REFUSED: BAD_SPACE_ID")
        ch, sf = self._target(chain, safe)
        key = sp + "|" + ch + "|" + sf
        prev = int(self.latest_bind.get(key) or 0)
        if prev != 0:
            old = self.binds[u64(prev)]
            if now - int(old.read_at) < REREAD_S:
                raise gl.vm.UserError("REFUSED: READ_RECENTLY_AS_" + str(prev))
        p = {"space": sp, "chain": ch, "safe": sf}

        def leader() -> dict:
            return read_space(p)

        def validator(res: gl.vm.Result) -> bool:
            if not isinstance(res, gl.vm.Return):
                return False
            return _canon(read_space(p)) == _canon(res.calldata)

        ev = gl.vm.run_nondet(leader, validator)
        if not isinstance(ev, dict):
            raise gl.vm.UserError("REFUSED: EVIDENCE_UNREADABLE")
        if "refused" in ev:
            raise gl.vm.UserError("REFUSED: " + str(ev["refused"])[:80])
        # --- writes
        bid = int(self.nb) + 1
        self.binds[u64(bid)] = SpaceBinding(
            bind_id=u64(bid), space=sp, chain=ch, safe=sf, listed=bool(ev["listed"]),
            treasuries_json=_canon(ev["treasuries"]), controllers_json=_canon(ev["controllers"]),
            space_network=ev["space_network"], read_at=u64(now), reader=gl.message.sender_address)
        self.latest_bind[key] = u64(bid)
        self.nb = u64(bid)
        return {"bind_id": bid, "listed": bool(ev["listed"])}

    # --- views (storage only) -------------------------------------------------

    def _pview(self, x: Proposal, with_text: bool) -> dict:
        out = {"vote_id": int(x.vote_id), "cid": x.cid, "proposal_id": x.proposal_id, "space": x.space,
               "author": x.author, "title": x.title, "body_sha256": x.body_sha256, "type": x.vtype,
               "choices": json.loads(x.choices_json), "scores": json.loads(x.scores_json),
               "scores_total": x.scores_total, "quorum": x.quorum, "start": int(x.start), "end": int(x.end),
               "snapshot": int(x.snapshot), "outcome": x.outcome, "outcome_why": x.outcome_why, "chain": x.chain,
               "safe": x.safe, "listed": bool(x.listed), "treasuries": json.loads(x.treasuries_json),
               "controllers": json.loads(x.controllers_json), "space_network": x.space_network,
               "ens": json.loads(x.ens_json), "ens_names": json.loads(x.ens_names_json),
               "ens_blocks": json.loads(x.ens_blocks_json), "pinned_block": int(x.pinned_block),
               "pinned_hash": x.pinned_hash, "read_at": int(x.read_at), "reader": x.reader.as_hex.lower(),
               "evidence_sha256": x.evidence_sha256}
        if with_text:
            out["text"] = x.text
        return out

    def _bview(self, x: SpaceBinding) -> dict:
        return {"bind_id": int(x.bind_id), "space": x.space, "chain": x.chain, "safe": x.safe,
                "listed": bool(x.listed), "treasuries": json.loads(x.treasuries_json),
                "controllers": json.loads(x.controllers_json), "space_network": x.space_network,
                "read_at": int(x.read_at), "reader": x.reader.as_hex.lower()}

    @gl.public.view
    def get_proposal(self, vote_id: int) -> typing.Any:
        x = self.props.get(u64(max(_as_int(vote_id, 0), 0)))
        if x is None:
            return {"found": False}
        out = self._pview(x, True)
        out["found"] = True
        return out

    @gl.public.view
    def get_proposal_id(self, cid: str, chain: str, safe: str) -> int:
        return int(self.latest.get(str(cid).strip() + "|" + str(chain).strip().lower() + "|" + _addr(safe)) or 0)

    @gl.public.view
    def get_proposals(self, offset: int, limit: int) -> typing.Any:
        o = max(_as_int(offset, 0), 0)
        lim = min(max(_as_int(limit, 20), 0), 25)
        out = []
        i = o + 1
        while i <= int(self.n) and len(out) < lim:
            x = self.props.get(u64(i))
            if x is not None:
                out.append(self._pview(x, False))
            i += 1
        return {"total": int(self.n), "proposals": out}

    @gl.public.view
    def get_binding(self, bind_id: int) -> typing.Any:
        x = self.binds.get(u64(max(_as_int(bind_id, 0), 0)))
        if x is None:
            return {"found": False}
        out = self._bview(x)
        out["found"] = True
        return out

    @gl.public.view
    def get_binding_id(self, space: str, chain: str, safe: str) -> int:
        return int(self.latest_bind.get(str(space).strip().lower() + "|" + str(chain).strip().lower() + "|" + _addr(safe)) or 0)

    @gl.public.view
    def get_config(self) -> typing.Any:
        return {"version": VERSION, "contract": "VoteReader", "ipfs_gateways": list(IPFS_GATEWAYS),
                "snapshot_hub": SNAPSHOT_HUB, "ens_registry": ENS_REGISTRY,
                "ethereum_rpcs": list(CHAINS["ethereum"][1]), "supported_types": ["basic", "single-choice"],
                "reread_s": REREAD_S, "max_body_chars": MAX_BODY_CHARS, "proposals": int(self.n),
                "bindings": int(self.nb)}
