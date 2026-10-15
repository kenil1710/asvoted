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
