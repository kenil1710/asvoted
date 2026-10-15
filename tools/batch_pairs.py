"""Runs tools/live.py judge_pair over research_cache/short.txt rows; prints a compact table."""
import json, sys
sys.path.insert(0, "tools")
import live
rows = [l.split() for l in open(sys.argv[1]) if l.strip()]
out = []
for r in rows:
    space, chain, safe, tx, nonce, cid = r[:6]
    try:
        res = live.judge_pair(chain, safe, tx, nonce, cid)
    except Exception as e:
        res = {"error": repr(e)[:120]}
    res["row"] = r[:6]
    out.append(res)
    if "code" in res:
        oc = [c["outcome"][:4] for c in res["code"]]
        print(space, tx[:10], res["vote"]["outcome"], "after" if res["after_end"] else "BEFORE", res["overall_if_model_unclear"], oc, "|", " ".join(r[6:])[:40])
        for c in res["code"]:
            if c["outcome"] in ("NOT_AUTHORIZED", "OVER_AMOUNT", "UNCLEAR"):
                print("     ", c["i"], c["outcome"], c["reason"][:150])
    else:
        print(space, tx[:10], "REFUSED", res, )
    sys.stdout.flush()
json.dump(out, open(sys.argv[2], "w"), indent=1)
