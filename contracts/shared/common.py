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
