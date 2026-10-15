"""Inlines contracts/shared/{common,rpc}.py into every contract that asks.

A contract marks the spot with "# INLINE:common" / "# INLINE:rpc" the first
time; after that the block between that file's markers is replaced in place,
so contracts stay single files (GenVM deploys one file) while the helpers
stay identical. Only the two readers include the RPC block. `--check` exits 1
if any contract's block differs from its source.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = 0
for part in ("common", "rpc"):
    src = (ROOT / "contracts" / "shared" / (part + ".py")).read_text()
    begin = src.splitlines()[0]
    end = src.rstrip().splitlines()[-1]
    for f in sorted((ROOT / "contracts").glob("*.py")):
        t = f.read_text()
        mark = "# INLINE:" + part + "\n"
        if mark in t:
            new = t.replace(mark, src)
        elif begin in t:
            a = t.index(begin)
            b = t.index(end, a) + len(end) + 1
            new = t[:a] + src + t[b:]
        else:
            continue
        if new != t:
            if "--check" in sys.argv:
                print("STALE", f.name, part)
                bad += 1
            else:
                f.write_text(new)
                print("inlined", part, "->", f.name)
sys.exit(1 if bad else 0)
