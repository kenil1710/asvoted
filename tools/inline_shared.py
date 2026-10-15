"""Inlines contracts/shared/common.py into every contract that asks for it.

A contract marks the spot with a line "# INLINE:common" the first time; after
that the block between the shared markers is replaced in place, so the
contracts stay single files (GenVM deploys one file) while the helpers stay
identical. `--check` exits 1 if any contract's block differs.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "contracts" / "shared" / "common.py").read_text()
BEGIN = SRC.splitlines()[0]
END = "# ==== end shared ===="
bad = 0
for f in sorted((ROOT / "contracts").glob("*.py")):
    t = f.read_text()
    if "# INLINE:common" in t:
        new = t.replace("# INLINE:common\n", SRC)
    elif BEGIN in t:
        a = t.index(BEGIN)
        b = t.index(END) + len(END) + 1
        new = t[:a] + SRC + t[b:]
    else:
        continue
    if new != t:
        if "--check" in sys.argv:
            print("STALE", f.name)
            bad += 1
        else:
            f.write_text(new)
            print("inlined", f.name)
    else:
        print("ok", f.name)
sys.exit(1 if bad else 0)
