"""Run a contract's own pure + fetch code locally against the REAL network
(the allowlisted RPCs, IPFS gateways, the Snapshot hub), with a tiny stand-in
for gl.nondet.web. Used for research and to verify seeds by hand.

  python3 tools/live.py exec <chain> <safe> <tx> <nonce>
  python3 tools/live.py vote <cid> <chain> <safe>
"""
import json
import sys
import time
import types
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = []


class _Res:
    def __init__(self, status, body):
        self.status_code = status
        self.body = body
        self.headers = {}


def _request(url, method="GET", body=None, headers=None, **_k):
    LOG.append((method, url))
    req = urllib.request.Request(url, data=body.encode() if isinstance(body, str) else body,
                                 method=method, headers={"User-Agent": "Mozilla/5.0 asvoted-live", **(headers or {})})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return _Res(r.status, r.read())
        except urllib.error.HTTPError as e:
            return _Res(e.code, e.read())
        except Exception:
            if i == 2:
                raise
            time.sleep(3)


def load(name):
    mod = types.ModuleType("genlayer")
    web = types.SimpleNamespace(get=lambda url, **k: _request(url), request=_request)
    nondet = types.SimpleNamespace(web=web, exec_prompt=None)
    storage = types.SimpleNamespace(TreeMap=dict, DynArray=list, allow=lambda c: c)
    mod.gl = types.SimpleNamespace(nondet=nondet, storage=storage,
                                   contract=types.SimpleNamespace(Contract=object),
                                   public=types.SimpleNamespace(view=lambda f: f, write=lambda f: f),
                                   vm=types.SimpleNamespace(UserError=Exception, Result=object, Return=object),
                                   message=None)
    mod.gl.public.write.payable = lambda f: f
    mod.Address = str
    for n in ("u8", "u16", "u32", "u64", "u128", "u256", "i64", "bigint"):
        setattr(mod, n, int)
    sys.modules["genlayer"] = mod
    ns = {}
    src = (ROOT / "contracts" / (name + ".py")).read_text()
    exec(compile(src, name + ".py", "exec"), ns)
    return ns


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "exec":
        C = load("ExecReader")
        chain, safe, tx, nonce = sys.argv[2], sys.argv[3].lower(), sys.argv[4].lower(), int(sys.argv[5])
        t = time.time()
        ev = C["read_execution"]({"chain": chain, "safe": safe, "tx": tx, "nonce": nonce}, -1)
        print(json.dumps(ev, indent=1)[:int(sys.argv[6]) if len(sys.argv) > 6 else 20000])
        print("requests", len(LOG), "seconds", round(time.time() - t, 1), file=sys.stderr)
        if "pinned" in ev and "refused" not in ev:
            ok = C["validate"](ev, {"chain": chain, "safe": safe, "tx": tx, "nonce": nonce})
            print("validator agrees:", ok, file=sys.stderr)
    elif cmd == "vote":
        C = load("VoteReader")
        cid, chain, safe = sys.argv[2], sys.argv[3], sys.argv[4].lower()
        t = time.time()
        p = {"cid": C["parse_cid"](cid), "chain": chain, "safe": safe}
        ev = C["read_proposal"](p, int(time.time()), -1)
        out = dict(ev)
        if "body" in out:
            out["body"] = out["body"][:300] + "..."
        print(json.dumps(out, indent=1)[:20000])
        print("requests", len(LOG), "seconds", round(time.time() - t, 1), file=sys.stderr)
