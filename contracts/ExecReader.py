# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *
from dataclasses import dataclass
import hashlib
import json
import typing

# ExecReader - what a DAO's Safe actually executed, decoded completely.
#
# Given (chain, Safe, transaction hash, Safe nonce), every validator
# independently:
#   1. pins ONE finalized block: the leader names the lower of the two RPCs'
#      finalized blocks; a validator accepts it only if it is final on both
#      of its own RPCs and not more than LEADER_LAG_S older than its own;
#   2. reads the transaction, its receipt and its block from TWO allowlisted
#      RPCs run by different operators. The fields used must be identical on
#      both, or the read is refused;
#   3. requires a DIRECT call to the Safe's execTransaction, mined at or
#      below the pinned block, that succeeded;
#   4. recomputes the Safe transaction hash in code (EIP-712, keccak-256,
#      both domain layouts Safe has shipped) from the decoded calldata and the
#      nonce, and requires an ExecutionSuccess log FROM THE SAFE for exactly
#      that hash. A wrong nonce, a non-Safe, or a failed Safe transaction is
#      refused - the nonce is a hint the caller supplies, verified, never
#      trusted;
#   5. decodes EVERY action: the outer call, and every inner call of a batch
#      sent by DELEGATECALL to an allowlisted MultiSend / MultiSendCallOnly
#      deployment (recursively, bounded). Each action: operation, target,
#      value, selector, and for ERC-20 transfer / transferFrom / approve the
#      token, recipient and amount (token symbol and decimals read at the
#      pinned block from both RPCs). A DELEGATECALL to anything else stays in
#      the list as a DELEGATECALL action. Unknown selectors stay in the list as
#      raw calls with their argument words. A gas refund the Safe paid is an
#      action too. Nothing chooses which actions exist: the list is the
#      calldata, decoded.
# Validators accept the leader's record only if it is byte-identical to their
# own. There is no model in this contract.
#
# RULES
#   1. Allowlisted RPC hosts only, matched exactly (shared CHAINS table).
#   2. Partial or unreadable data refuses; it never yields a record.
#   3. Nothing is written before the last check that can revert.
#   4. Records are immutable; one per (chain, Safe, transaction).
#   5. No owner, no setter, no payable method, no value held.

VERSION = "1.0.0"

SEL_EXEC = "6a761202"     # execTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes)
SEL_MULTISEND = "8d80ff0a"  # multiSend(bytes)
TOPIC_SUCCESS = "0x442e715f626346e8c54381002da614f62bee8d27386535b2521ec8540898556e"  # ExecutionSuccess(bytes32,uint256)
TOPIC_FAILURE = "0x23428b18acfb3ea64b08dc0c1d296ea9c09702c09083ca5272e64d115b687d23"  # ExecutionFailure(bytes32,uint256)
# SafeL2: SafeMultiSigTransaction(address,uint256,bytes,uint8,uint256,uint256,uint256,address,address,bytes,bytes)
TOPIC_MULTISIG_TX = "0x66753cd2356569ee081232e3be8909b950e0a76c1f8460c3a5e3c2be32b11bed"
SAFE_TX_TYPEHASH = "bb8310d486368db6bd6f849402fdd73ad53d316b5a4b2644ad6efe0f941286d8"
DOMAIN_TYPEHASH_V13 = "47e79534a245952e8b16893a336b85a3d9ea9fa8c573f3d803afb92a79469218"  # (uint256 chainId,address verifyingContract), Safe >= 1.3.0
DOMAIN_TYPEHASH_OLD = "035aff83d86937d35b32e04f0ddc6ff469290eef2f1b692d8a815c89404d4749"  # (address verifyingContract), Safe < 1.3.0

# safe-global/safe-deployments: canonical and eip155 addresses on the five chains.
MULTISEND = {
    "0x8d29be29923b68abfdd21e541b9374737b49cdad": ("MultiSend 1.1.1", False),
    "0xa238cbeb142c10ef7ad8442c6d1f9e89e07e7761": ("MultiSend 1.3.0", False),
    "0x998739bfdaadde7c933b942a68053933098f9eda": ("MultiSend 1.3.0 (eip155)", False),
    "0x40a2accbd92bca938b02010e17a5b8929b49130d": ("MultiSendCallOnly 1.3.0", True),
    "0xa1dabef33b3b82c7814b6d82a79e50f4ac44102b": ("MultiSendCallOnly 1.3.0 (eip155)", True),
    "0x38869bf66a61cf6bdb996a6ae40d5853fd43b526": ("MultiSend 1.4.1", False),
    "0x9641d764fc13c8b624c04430c7356c1c7c8102e2": ("MultiSendCallOnly 1.4.1", True),
    "0x218543288004cd07832472d464648173c77d7eb7": ("MultiSend 1.5.0", False),
    "0xa83c336b20401af773b6219ba5027174338d1836": ("MultiSendCallOnly 1.5.0", True),
}

# Display names only. The judge reads selectors and decoded words, never these.
FN_NAMES = {
    "a9059cbb": "transfer(address,uint256)", "23b872dd": "transferFrom(address,address,uint256)",
    "095ea7b3": "approve(address,uint256)", "39509351": "increaseAllowance(address,uint256)",
    "a457c2d7": "decreaseAllowance(address,uint256)", "5c19a95c": "delegate(address)",
    "0d582f13": "addOwnerWithThreshold(address,uint256)", "f8dc5dd9": "removeOwner(address,address,uint256)",
    "e318b52b": "swapOwner(address,address,address)", "694e80c3": "changeThreshold(uint256)",
    "610b5925": "enableModule(address)", "e009cfde": "disableModule(address,address)",
    "e19a9dd9": "setGuard(address)", "f08a0323": "setFallbackHandler(address)",
    "d4d9bdcd": "approveHash(bytes32)", "6a761202": "execTransaction(...)", "8d80ff0a": "multiSend(bytes)",
    "d0e30db0": "deposit()", "2e1a7d4d": "withdraw(uint256)", "b6b55f25": "deposit(uint256)",
    "6e553f65": "deposit(uint256,address)", "b460af94": "withdraw(uint256,address,address)",
    "ba087652": "redeem(uint256,address,address)", "ac9650d8": "multicall(bytes[])",
    "252dba42": "aggregate((address,bytes)[])", "f2fde38b": "transferOwnership(address)",
    "3659cfe6": "upgradeTo(address)", "4f1ef286": "upgradeToAndCall(address,bytes)",
    "40c10f19": "mint(address,uint256)", "42966c68": "burn(uint256)", "9dc29fac": "burn(address,uint256)",
    "3ccfd60b": "withdraw()", "e2bbb158": "deposit(uint256,uint256)", "441a3e70": "withdraw(uint256,uint256)",
    "8456cb59": "pause()", "3f4ba83a": "unpause()", "a0712d68": "mint(uint256)",
    "f3fef3a3": "withdraw(address,uint256)", "47e7ef24": "deposit(address,uint256)",
    "e8eda9df": "deposit(address,uint256,address,uint16)", "69328dec": "withdraw(address,uint256,address)",
    "b88d4fde": "safeTransferFrom(address,address,uint256,bytes)", "42842e0e": "safeTransferFrom(address,address,uint256)",
    "f242432a": "safeTransferFrom(address,address,uint256,uint256,bytes)", "a22cb465": "setApprovalForAll(address,bool)",
    "c4d66de8": "initialize(address)", "8da5cb5b": "owner()", "e2ab691d": "lock(address,uint256,uint256)",
    "4e71d92d": "claim()", "379607f5": "claim(uint256)", "1e83409a": "claim(address)",
}

MAX_DEPTH = 4
MAX_ACTIONS = 64
MAX_ARG_WORDS = 48
MAX_TOKENS = 16
MAX_CALLDATA = 131072
ADDR_LIKE_MIN = 1 << 96       # an argument word whose top 12 bytes are zero, that is at least this and is not 2**k - 1, is reported as address-like (2**96: a vanity prefix of 16+ zero hex digits is out of reach; an amount that large is 79 billion tokens at 18 decimals)
MAX_ARG_ADDRS = 24

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
# decoding
# =============================================================================

def decode_exec(inp: bytes) -> dict:
    """execTransaction calldata -> its ten parameters, or ValueError."""
    if len(inp) < 4 or inp[:4].hex() != SEL_EXEC:
        raise ValueError("not execTransaction")
    a = inp[4:]
    out = {
        "to": _w_addr(a, 0), "value": _word(a, 1), "data": _w_bytes(a, 2), "operation": _word(a, 3),
        "safeTxGas": _word(a, 4), "baseGas": _word(a, 5), "gasPrice": _word(a, 6),
        "gasToken": _w_addr(a, 7), "refundReceiver": _w_addr(a, 8), "signatures": _w_bytes(a, 9),
    }
    if out["operation"] > 1:
        raise ValueError("bad operation")
    return out


def decode_multisig_log(data: bytes) -> dict:
    """A SafeL2 SafeMultiSigTransaction log's data -> the same ten
    parameters as execTransaction calldata, plus the nonce it records
    (additionalInfo = abi.encode(nonce, sender, threshold)), or ValueError."""
    out = {
        "to": _w_addr(data, 0), "value": _word(data, 1), "data": _w_bytes(data, 2), "operation": _word(data, 3),
        "safeTxGas": _word(data, 4), "baseGas": _word(data, 5), "gasPrice": _word(data, 6),
        "gasToken": _w_addr(data, 7), "refundReceiver": _w_addr(data, 8), "signatures": _w_bytes(data, 9),
    }
    info = _w_bytes(data, 10)
    if out["operation"] > 1 or len(info) < 32:
        raise ValueError("bad multisig log")
    out["nonce"] = _word(info, 0)
    return out


def safe_tx_hashes(chain_id: int, safe: str, e: dict, nonce: int) -> list:
    """The Safe transaction hash under both domain layouts Safe has shipped."""
    struct = keccak256(bytes.fromhex(SAFE_TX_TYPEHASH) + enc_addr(e["to"]) + enc_word(e["value"]) +
                       keccak256(e["data"]) + enc_word(e["operation"]) + enc_word(e["safeTxGas"]) +
                       enc_word(e["baseGas"]) + enc_word(e["gasPrice"]) + enc_addr(e["gasToken"]) +
                       enc_addr(e["refundReceiver"]) + enc_word(nonce))
    out = []
    for dom in (keccak256(bytes.fromhex(DOMAIN_TYPEHASH_V13) + enc_word(chain_id) + enc_addr(safe)),
                keccak256(bytes.fromhex(DOMAIN_TYPEHASH_OLD) + enc_addr(safe))):
        out.append("0x" + keccak256(b"\x19\x01" + dom + struct).hex())
    return out


def unpack_multisend(packed: bytes) -> list:
    """MultiSend's packed encoding: op(1) to(20) value(32) len(32) data(len),
    back to back. Any trailing or short bytes -> ValueError."""
    out = []
    i = 0
    while i < len(packed):
        if i + 85 > len(packed):
            raise ValueError("short inner header")
        op = packed[i]
        to = "0x" + packed[i + 1:i + 21].hex()
        value = int.from_bytes(packed[i + 21:i + 53], "big")
        n = int.from_bytes(packed[i + 53:i + 85], "big")
        if op > 1 or i + 85 + n > len(packed):
            raise ValueError("bad inner tx")
        out.append({"op": op, "to": to, "value": value, "data": packed[i + 85:i + 85 + n]})
        i += 85 + n
    return out


def addr_like_words(args: bytes) -> list:
    out = []
    for k in range(len(args) // 32):
        v = int.from_bytes(args[32 * k:32 * k + 32], "big")
        if v >> 160 == 0 and v >= ADDR_LIKE_MIN and (v + 1) & v != 0:
            a = "0x" + ("0" * 40 + hex(v)[2:])[-40:]
            if a not in out:
                out.append(a)
    return out


def classify(op: int, to: str, value: int, data: bytes, path: str, batch: str) -> dict:
    """One action, decoded. Never raises for odd calldata: what cannot be
    decoded as a known shape stays a raw call, flagged."""
    sel = data[:4].hex() if len(data) >= 4 else ""
    args = data[4:] if len(data) >= 4 else b""
    act = {"path": path, "op": "DELEGATECALL" if op == 1 else "CALL", "target": to, "value": str(value),
           "selector": ("0x" + sel) if sel != "" else "", "fn": FN_NAMES.get(sel, ""), "kind": "call",
           "token": "", "from": "", "recipient": "", "amount": "", "data_len": len(data),
           "data_sha256": hashlib.sha256(data).hexdigest(), "batch": batch, "flags": [],
           "args": [], "addr_args": []}
    if len(data) > 0 and len(data) < 4:
        act["flags"].append("SHORT_CALLDATA")
    words = []
    for k in range(min(len(args) // 32, MAX_ARG_WORDS)):
        words.append("0x" + args[32 * k:32 * k + 32].hex())
    act["args"] = words
    if len(args) // 32 > MAX_ARG_WORDS:
        act["flags"].append("ARGS_TRUNCATED_IN_VIEW")
    if len(args) % 32 != 0:
        act["flags"].append("UNALIGNED_ARGS")
    act["addr_args"] = addr_like_words(args)
    if sel == SEL_EXEC:
        # A call into ANOTHER Safe's execTransaction: its signatures carry
        # owner addresses (approved-hash and contract signatures put the
        # owner in r), which are not arguments of the action. The addresses
        # that matter are the inner target and those in the inner calldata.
        try:
            inner = decode_exec(data)
            found = addr_like_words(enc_addr(inner["to"]) + (inner["data"][4:] if len(inner["data"]) >= 4 else b""))
            for x in (inner["gasToken"], inner["refundReceiver"]):
                if x != ZERO and x not in found:
                    found.append(x)
            act["addr_args"] = found
            act["flags"].append("NESTED_SAFE_EXECUTION")
        except ValueError:
            act["flags"].append("MALFORMED_NESTED_SAFE_EXECUTION")
    if op == 1:
        act["kind"] = "delegatecall"
        return act
    if len(data) == 0:
        act["kind"] = "native" if value > 0 else "empty"
        if value > 0:
            act["recipient"] = to
            act["amount"] = str(value)
        return act
    try:
        if sel == "a9059cbb" and len(args) >= 64:
            act["kind"] = "erc20_transfer"
            act["token"] = to
            act["recipient"] = _w_addr(args, 0)
            act["amount"] = str(_word(args, 1))
        elif sel == "23b872dd" and len(args) >= 96:
            act["kind"] = "erc20_transfer_from"
            act["token"] = to
            act["from"] = _w_addr(args, 0)
            act["recipient"] = _w_addr(args, 1)
            act["amount"] = str(_word(args, 2))
        elif sel == "095ea7b3" and len(args) >= 64:
            act["kind"] = "erc20_approve"
            act["token"] = to
            act["recipient"] = _w_addr(args, 0)
            act["amount"] = str(_word(args, 1))
    except ValueError:
        act["kind"] = "call"
        act["token"] = ""
        act["from"] = ""
        act["recipient"] = ""
        act["amount"] = ""
        act["flags"].append("MALFORMED_TOKEN_CALL")
    if act["kind"] != "call":
        expect = 64 if sel != "23b872dd" else 96
        if len(args) != expect:
            act["flags"].append("EXTRA_CALLDATA")
    return act


def expand(op: int, to: str, value: int, data: bytes, path: str, depth: int, batch: str, out: list) -> None:
    """Appends the actions of one call to `out`. A DELEGATECALL to an
    allowlisted MultiSend with multiSend(bytes) is a container: its inner
    calls are the actions. Raises ValueError for a malformed batch, and
    OverflowError past MAX_DEPTH / MAX_ACTIONS."""
    ms = MULTISEND.get(to)
    if op == 1 and ms is not None and len(data) >= 4 and data[:4].hex() == SEL_MULTISEND:
        if depth >= MAX_DEPTH:
            raise OverflowError("TOO_DEEP")
        if value != 0:
            raise ValueError("value on a batch")
        inner = unpack_multisend(_w_bytes(data[4:], 0))
        if len(inner) == 0:
            raise ValueError("empty batch")
        for k in range(len(inner)):
            t = inner[k]
            if ms[1] and t["op"] != 0:
                raise ValueError("delegatecall inside MultiSendCallOnly")
            expand(t["op"], t["to"], t["value"], t["data"], path + "." + str(k), depth + 1, ms[0], out)
        return
    if len(out) >= MAX_ACTIONS:
        raise OverflowError("TOO_MANY_ACTIONS")
    act = classify(op, to, value, data, path, batch)
    act["i"] = len(out)
    out.append(act)


def dec_symbol(res: typing.Any) -> str:
    """ERC-20 symbol(): an ABI string, or a bytes32 (MKR-style). "" if neither."""
    if not isinstance(res, list) or res[0] != "ok" or not isinstance(res[1], str):
        return ""
    try:
        b = hexb(res[1])
    except Exception:
        return ""
    s = b""
    if len(b) >= 96:
        try:
            s = _w_bytes(b, 0)
        except ValueError:
            s = b""
    elif len(b) == 32:
        s = b
        k = s.find(b"\x00")
        if k >= 0:
            s = s[:k]
    try:
        t = s.decode("utf-8")
    except Exception:
        return ""
    clean = ""
    for ch in t:
        if ch.isalnum() or ch in ".-_+":
            clean += ch
    return clean[:16] if len(clean) == len(t) else ""


def dec_uint_small(res: typing.Any, hi: int) -> int:
    if not isinstance(res, list) or res[0] != "ok" or not isinstance(res[1], str):
        return -1
    try:
        b = hexb(res[1])
    except Exception:
        return -1
    if len(b) != 32:
        return -1
    v = int.from_bytes(b, "big")
    return v if v <= hi else -1


# =============================================================================
# the read
# =============================================================================

def _proj_tx(call: list, r: typing.Any) -> typing.Any:
    if not isinstance(r, list) or r[0] != "ok":
        return ["revert"]
    v = r[1]
    m = call[0]
    if m == "eth_getTransactionByHash":
        if not isinstance(v, dict):
            return None
        return {"hash": str(v.get("hash", "")).lower(), "from": str(v.get("from", "")).lower(),
                "to": str(v.get("to") or "").lower(), "input": str(v.get("input", "")).lower(),
                "value": str(v.get("value", "")).lower(), "blockNumber": str(v.get("blockNumber") or "").lower(),
                "blockHash": str(v.get("blockHash") or "").lower()}
    if m == "eth_getTransactionReceipt":
        if not isinstance(v, dict):
            return None
        logs = []
        for lg in v.get("logs") or []:
            if not isinstance(lg, dict):
                return None
            logs.append({"address": str(lg.get("address", "")).lower(),
                         "topics": [str(t).lower() for t in (lg.get("topics") or [])],
                         "data": str(lg.get("data", "")).lower(), "logIndex": str(lg.get("logIndex", "")).lower()})
        return {"status": str(v.get("status", "")).lower(), "blockNumber": str(v.get("blockNumber", "")).lower(),
                "blockHash": str(v.get("blockHash", "")).lower(), "to": str(v.get("to") or "").lower(), "logs": logs}
    return _proj_basic(call, r)


def _proj_call(call: list, r: typing.Any) -> typing.Any:
    if not isinstance(r, list):
        return None
    if r[0] == "revert":
        return ["revert", None]
    return ["ok", str(r[1]).lower()]


L1_INFO_SELECTORS = ("0x440a5e20", "0x098999be")   # OP-stack setL1BlockValuesEcotone / Isthmus (packed)
L1_INFO_BEDROCK = "0x015d8eb9"                      # setL1BlockValues(uint64 _number, ...)


def _proj_l1(call: list, r: typing.Any) -> typing.Any:
    if not isinstance(r, list) or r[0] != "ok" or not isinstance(r[1], dict):
        return None
    v = r[1]
    if call[0] == "eth_getBlockByNumber":
        return str(v.get("l1BlockNumber") or "").lower()
    return str(v.get("input") or "").lower()


def _proj_first(call: list, r: typing.Any) -> typing.Any:
    """The hash of a block's first transaction."""
    if not isinstance(r, list) or r[0] != "ok" or not isinstance(r[1], dict):
        return None
    txs = r[1].get("transactions") or []
    return str(txs[0]).lower() if len(txs) > 0 and isinstance(txs[0], str) else ""


def l1_block_of(ch: str, tb: int) -> int:
    """The Ethereum block an execution's block belongs to, so ENS names can be
    resolved as of the execution and never later: the block itself on
    Ethereum; the L1 attributes deposit (first transaction of every block)
    on OP-stack chains; the block's l1BlockNumber on Arbitrum; 0 (unknown)
    elsewhere. Raises ReadFailed / Disagree like any read."""
    if ch == "ethereum":
        return tb
    if ch in ("optimism", "base"):
        first = dual_read(ch, [["eth_getBlockByNumber", [hex(tb), False]]], _proj_first)[0]
        if not isinstance(first, str) or not first.startswith("0x") or not _is_hex(first[2:], 64):
            return 0
        got = dual_read(ch, [["eth_getTransactionByHash", [first]]], _proj_l1)[0]
        if not isinstance(got, str) or len(got) < 10:
            return 0
        sel = got[:10]
        body = got[10:]
        try:
            if sel in L1_INFO_SELECTORS and len(body) >= 64:
                return int(body[48:64], 16)
            if sel == L1_INFO_BEDROCK and len(body) >= 64:
                return int(body[0:64], 16)
        except Exception:
            return 0
        return 0
    if ch == "arbitrum":
        got = dual_read(ch, [["eth_getBlockByNumber", [hex(tb), False]]], _proj_l1)[0]
        try:
            return int(got, 16) if isinstance(got, str) and got.startswith("0x") else 0
        except Exception:
            return 0
    return 0


def read_execution(p: dict, block: int) -> dict:
    """Everything one node reads. `block` < 0: this node is the leader."""
    ch = p["chain"]
    pin = pin_block(ch, block)
    if "block" not in pin:
        return pin
    blk = pin["block"]
    out_block = {"number": blk["number"], "hash": blk["hash"], "timestamp": blk["timestamp"]}
    try:
        got = dual_read(ch, [["eth_getTransactionByHash", [p["tx"]]], ["eth_getTransactionReceipt", [p["tx"]]]], _proj_tx)
    except ReadFailed:
        return {"refused": "RPC_UNREADABLE", "pinned": out_block}
    except Disagree:
        return {"refused": "RPC_DISAGREE", "pinned": out_block}
    tx = got[0]
    rc = got[1]
    if tx is None or rc is None or tx == ["revert"] or rc == ["revert"]:
        return {"refused": "TX_NOT_FOUND", "pinned": out_block}
    if tx["blockNumber"] == "" or rc["blockNumber"] == "":
        return {"refused": "TX_NOT_MINED", "pinned": out_block}
    try:
        tb = int(tx["blockNumber"], 16)
    except Exception:
        return {"refused": "RPC_UNREADABLE", "pinned": out_block}
    if tb > blk["number"]:
        return {"refused": "TX_NOT_FINALIZED_YET", "pinned": out_block}
    try:
        tbk = dual_read(ch, [["eth_getBlockByNumber", [hex(tb), False]]], _proj_basic)[0]
        l1 = l1_block_of(ch, tb)
    except ReadFailed:
        return {"refused": "RPC_UNREADABLE", "pinned": out_block}
    except Disagree:
        return {"refused": "RPC_DISAGREE", "pinned": out_block}
    if tbk is None or tbk["hash"] != tx["blockHash"] or tbk["hash"] != rc["blockHash"] or \
            tx["hash"] != p["tx"]:
        return {"refused": "TX_BLOCK_MISMATCH", "pinned": out_block}
    if rc["status"] != "0x1":
        return {"refused": "TX_REVERTED", "pinned": out_block}
    if tx["to"] != p["safe"]:
        # relayed (the Safe was called by another contract): only a SafeL2
        # Safe records every parameter, in its SafeMultiSigTransaction log.
        # Exactly one such log of this Safe, for this nonce; it is then bound
        # to ExecutionSuccess like a direct call.
        mlogs = [lg for lg in rc["logs"] if lg["address"] == p["safe"] and len(lg["topics"]) > 0 and
                 lg["topics"][0] == TOPIC_MULTISIG_TX]
        if len(mlogs) != 1:
            return {"refused": "NOT_A_DIRECT_CALL_TO_THE_SAFE_AND_NO_SAFEL2_LOG", "pinned": out_block}
        try:
            raw = hexb(mlogs[0]["data"])
            if len(raw) > MAX_CALLDATA:
                return {"refused": "CALLDATA_TOO_LARGE", "pinned": out_block}
            e = decode_multisig_log(raw)
        except ValueError:
            return {"refused": "SAFEL2_LOG_MALFORMED", "pinned": out_block}
        except Exception:
            return {"refused": "SAFEL2_LOG_MALFORMED", "pinned": out_block}
        if e["nonce"] != p["nonce"]:
            return {"refused": "SAFEL2_LOG_NONCE_MISMATCH", "pinned": out_block}
    else:
        try:
            inp = hexb(tx["input"])
        except Exception:
            return {"refused": "EXEC_CALLDATA_MALFORMED", "pinned": out_block}
        if len(inp) > MAX_CALLDATA:
            return {"refused": "CALLDATA_TOO_LARGE", "pinned": out_block}
        try:
            e = decode_exec(inp)
        except ValueError:
            return {"refused": "NOT_EXEC_TRANSACTION", "pinned": out_block}
    hashes = safe_tx_hashes(CHAINS[ch][0], p["safe"], e, p["nonce"])
    succ = []
    fail = []
    for lg in rc["logs"]:
        if lg["address"] != p["safe"] or len(lg["topics"]) == 0:
            continue
        cand = ""
        if len(lg["topics"]) >= 2:
            cand = lg["topics"][1]
        elif len(lg["data"]) >= 66:
            cand = "0x" + lg["data"][2:66]
        payment = 0
        d = lg["data"][2:] if lg["data"].startswith("0x") else lg["data"]
        if len(lg["topics"]) >= 2 and len(d) >= 64:
            payment = int(d[0:64], 16)
        elif len(d) >= 128:
            payment = int(d[64:128], 16)
        if lg["topics"][0] == TOPIC_SUCCESS:
            succ.append([cand, payment])
        elif lg["topics"][0] == TOPIC_FAILURE:
            fail.append(cand)
    match = [s for s in succ if s[0] in hashes]
    if len(match) != 1:
        if len([f for f in fail if f in hashes]) > 0:
            return {"refused": "SAFE_EXECUTION_FAILED", "pinned": out_block}
        return {"refused": "SAFE_TX_HASH_MISMATCH", "pinned": out_block}
    safe_tx_hash = match[0][0]
    payment = match[0][1]
    actions = []
    try:
        expand(e["operation"], e["to"], e["value"], e["data"], "0", 0, "", actions)
    except OverflowError as ex:
        return {"refused": str(ex), "pinned": out_block}
    except ValueError:
        return {"refused": "BATCH_MALFORMED", "pinned": out_block}
    if payment > 0:
        if len(actions) >= MAX_ACTIONS:
            return {"refused": "TOO_MANY_ACTIONS", "pinned": out_block}
        rr = e["refundReceiver"] if e["refundReceiver"] != ZERO else tx["from"]
        actions.append({"i": len(actions), "path": "refund", "op": "CALL", "target": rr, "value": "0",
                        "selector": "", "fn": "", "kind": "gas_refund",
                        "token": e["gasToken"] if e["gasToken"] != ZERO else "", "from": "", "recipient": rr,
                        "amount": str(payment), "data_len": 0, "data_sha256": "", "batch": "", "flags": [],
                        "args": [], "addr_args": []})
    toks = []
    for a in actions:
        t = a["token"]
        if t != "" and t not in toks:
            toks.append(t)
    if len(toks) > MAX_TOKENS:
        return {"refused": "TOO_MANY_TOKENS", "pinned": out_block}
    others = []
    for a in actions:
        for x in [a["target"]] + a["addr_args"]:
            if x not in toks and x not in others and x != p["safe"] and x not in MULTISEND:
                others.append(x)
    others = others[:MAX_ARG_ADDRS]
    calls = []
    bh = hex(blk["number"])
    for t in toks:
        calls.append(["eth_call", [{"to": t, "data": "0x95d89b41"}, bh]])
        calls.append(["eth_call", [{"to": t, "data": "0x313ce567"}, bh]])
    for t in others:
        calls.append(["eth_call", [{"to": t, "data": "0x95d89b41"}, bh]])
    tokens = {}
    symbols = {}
    if len(calls) > 0:
        try:
            res = dual_read(ch, calls, _proj_call)
        except ReadFailed:
            return {"refused": "RPC_UNREADABLE", "pinned": out_block}
        except Disagree:
            return {"refused": "RPC_DISAGREE", "pinned": out_block}
        for k in range(len(toks)):
            tokens[toks[k]] = {"symbol": dec_symbol(res[2 * k]), "decimals": dec_uint_small(res[2 * k + 1], 77)}
        for k in range(len(others)):
            s = dec_symbol(res[2 * len(toks) + k])
            if s != "":
                symbols[others[k]] = s
    native = CHAINS[ch][2]
    tokens[""] = {"symbol": native, "decimals": 18}
    return {
        "chain": ch, "safe": p["safe"], "tx": p["tx"], "nonce": p["nonce"], "safe_tx_hash": safe_tx_hash,
        "executor": tx["from"], "block": {"number": tb, "hash": tbk["hash"], "timestamp": tbk["timestamp"]},
        "l1_block": l1,
        "pinned": out_block,
        "outer": {"to": e["to"], "value": str(e["value"]), "operation": e["operation"],
                  "safeTxGas": str(e["safeTxGas"]), "baseGas": str(e["baseGas"]), "gasPrice": str(e["gasPrice"]),
                  "gasToken": e["gasToken"], "refundReceiver": e["refundReceiver"], "payment": str(payment),
                  "data_len": len(e["data"]), "signatures_len": len(e["signatures"])},
        "actions": actions, "tokens": tokens, "symbols": symbols, "rpcs": list(CHAINS[ch][1]),
    }


def validate(theirs: typing.Any, p: dict) -> bool:
    if not isinstance(theirs, dict):
        return False
    pinned = theirs.get("pinned")
    if not isinstance(pinned, dict) or not isinstance(pinned.get("number"), int):
        # a refusal before any block was pinned: agree only on the same reason
        if "refused" in theirs or "reject" in theirs:
            mine = read_execution(p, -1)
            return mine.get("refused") == theirs.get("refused") and "pinned" not in mine
        return False
    mine = read_execution(p, int(pinned["number"]))
    if "reject" in mine:
        return False
    return _canon(mine) == _canon(theirs)


# =============================================================================
# storage
# =============================================================================

@gl.storage.allow
@dataclass
class Execution:
    exec_id: u64
    key: str
    chain: str
    safe: str
    tx: str
    nonce: u64
    safe_tx_hash: str
    executor: str
    block: u64
    block_hash: str
    block_time: u64
    pinned_block: u64
    pinned_hash: str
    pinned_time: u64
    l1_block: u64
    read_at: u64
    reader: Address
    n_actions: u64
    has_delegatecall: bool
    actions_json: str
    tokens_json: str
    symbols_json: str
    outer_json: str
    rpcs_json: str
    evidence_sha256: str


class ExecReader(gl.contract.Contract):
    n: u64
    execs: gl.storage.TreeMap[u64, Execution]
    by_key: gl.storage.TreeMap[str, u64]

    def __init__(self) -> None:
        self.n = u64(0)

    def _now(self) -> int:
        return _epoch_from_iso(gl.message.raw.get("datetime", ""))

    @gl.public.write
    def read_execution(self, chain: str, safe: str, tx_hash: str, nonce: int) -> typing.Any:
        """Read and decode one Safe execution. `nonce` is the Safe nonce the
        transaction used; it is verified by recomputing the Safe transaction
        hash, never trusted. Refusals raise before any write."""
        now = self._now()
        if now <= 0:
            raise gl.vm.UserError("REFUSED: NO_CLOCK")
        ch = str(chain).strip().lower()
        if ch not in CHAINS:
            raise gl.vm.UserError("REFUSED: UNSUPPORTED_CHAIN")
        sf = _addr(safe)
        if sf == "" or sf == ZERO:
            raise gl.vm.UserError("REFUSED: BAD_SAFE_ADDRESS")
        th = _hash32(tx_hash)
        if th == "":
            raise gl.vm.UserError("REFUSED: BAD_TX_HASH")
        nn = _as_int(nonce, -1)
        if nn < 0 or nn > 10 ** 12:
            raise gl.vm.UserError("REFUSED: BAD_NONCE")
        key = ch + "|" + sf + "|" + th
        prev = int(self.by_key.get(key) or 0)
        if prev != 0:
            raise gl.vm.UserError("REFUSED: ALREADY_READ_AS_" + str(prev))
        p = {"chain": ch, "safe": sf, "tx": th, "nonce": nn}

        def leader() -> dict:
            return read_execution(p, -1)

        def validator(res: gl.vm.Result) -> bool:
            if not isinstance(res, gl.vm.Return):
                return False
            return validate(res.calldata, p)

        ev = gl.vm.run_nondet(leader, validator)
        if not isinstance(ev, dict):
            raise gl.vm.UserError("REFUSED: EVIDENCE_UNREADABLE")
        if "refused" in ev:
            raise gl.vm.UserError("REFUSED: " + str(ev["refused"])[:80])
        if "reject" in ev:
            raise gl.vm.UserError("REFUSED: " + str(ev["reject"])[:80])
        # --- writes (nothing below can refuse)
        eid = int(self.n) + 1
        has_dc = False
        for a in ev["actions"]:
            if a["op"] == "DELEGATECALL":
                has_dc = True
        self.execs[u64(eid)] = Execution(
            exec_id=u64(eid), key=key, chain=ch, safe=sf, tx=th, nonce=u64(nn),
            safe_tx_hash=ev["safe_tx_hash"], executor=ev["executor"],
            block=u64(int(ev["block"]["number"])), block_hash=ev["block"]["hash"],
            block_time=u64(int(ev["block"]["timestamp"])), l1_block=u64(int(ev["l1_block"])), pinned_block=u64(int(ev["pinned"]["number"])),
            pinned_hash=ev["pinned"]["hash"], pinned_time=u64(int(ev["pinned"]["timestamp"])),
            read_at=u64(now), reader=gl.message.sender_address, n_actions=u64(len(ev["actions"])),
            has_delegatecall=has_dc, actions_json=_canon(ev["actions"]), tokens_json=_canon(ev["tokens"]),
            symbols_json=_canon(ev["symbols"]),
            outer_json=_canon(ev["outer"]), rpcs_json=_canon(ev["rpcs"]), evidence_sha256=_sha(_canon(ev)))
        self.by_key[key] = u64(eid)
        self.n = u64(eid)
        return {"exec_id": eid, "actions": len(ev["actions"]), "block": int(ev["block"]["number"]),
                "safe_tx_hash": ev["safe_tx_hash"]}

    # --- views (storage only) -------------------------------------------------

    def _view(self, x: Execution) -> dict:
        return {"exec_id": int(x.exec_id), "key": x.key, "chain": x.chain, "safe": x.safe, "tx": x.tx,
                "nonce": int(x.nonce), "safe_tx_hash": x.safe_tx_hash, "executor": x.executor,
                "block": int(x.block), "block_hash": x.block_hash, "block_time": int(x.block_time),
                "l1_block": int(x.l1_block),
                "pinned_block": int(x.pinned_block), "pinned_hash": x.pinned_hash,
                "pinned_time": int(x.pinned_time), "read_at": int(x.read_at),
                "reader": x.reader.as_hex.lower(), "n_actions": int(x.n_actions),
                "has_delegatecall": bool(x.has_delegatecall), "actions": json.loads(x.actions_json),
                "tokens": json.loads(x.tokens_json), "symbols": json.loads(x.symbols_json), "outer": json.loads(x.outer_json),
                "rpcs": json.loads(x.rpcs_json), "evidence_sha256": x.evidence_sha256}

    @gl.public.view
    def get_execution(self, exec_id: int) -> typing.Any:
        x = self.execs.get(u64(max(_as_int(exec_id, 0), 0)))
        if x is None:
            return {"found": False}
        out = self._view(x)
        out["found"] = True
        return out

    @gl.public.view
    def get_execution_id(self, chain: str, safe: str, tx_hash: str) -> int:
        key = str(chain).strip().lower() + "|" + _addr(safe) + "|" + _hash32(tx_hash)
        return int(self.by_key.get(key) or 0)

    @gl.public.view
    def get_executions(self, offset: int, limit: int) -> typing.Any:
        o = max(_as_int(offset, 0), 0)
        lim = min(max(_as_int(limit, 20), 0), 25)
        out = []
        i = o + 1
        while i <= int(self.n) and len(out) < lim:
            x = self.execs.get(u64(i))
            if x is not None:
                v = self._view(x)
                v["actions"] = len(v["actions"])
                out.append(v)
            i += 1
        return {"total": int(self.n), "executions": out}

    @gl.public.view
    def get_config(self) -> typing.Any:
        return {"version": VERSION, "contract": "ExecReader",
                "chains": {k: {"chain_id": CHAINS[k][0], "rpcs": list(CHAINS[k][1]), "native": CHAINS[k][2]} for k in CHAINS},
                "multisend": {k: MULTISEND[k][0] for k in MULTISEND}, "max_depth": MAX_DEPTH,
                "max_actions": MAX_ACTIONS, "leader_lag_s": LEADER_LAG_S, "executions": int(self.n)}
