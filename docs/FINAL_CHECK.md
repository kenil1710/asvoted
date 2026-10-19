# Final check

Run 2026-10-19T01:06:16.281Z by `tools/final_check.mjs` against commit `ad2d8a84b5`, the live site and Studio Dev. **28/28 PASS.**

## PASS · Source match: every address byte-identical to HEAD, all from one commit, contracts/ untouched since

```
commit b836f418da32f8bd1b2bb0e218a6512d35275cbb; contracts/ changes since: none
ExecReader 0x08E3E60e037af578D1c5f4189cDDd888ac497685 sha256 d2b6475e2272a3a4… byte-identical to HEAD
VoteReader 0xEb81fc7584fFf7f9414B52575c0151B1cE9b0bc7 sha256 60079ef401ad1769… byte-identical to HEAD
AsVotedJudge 0x73fA37dc86005942AA1045a82CcF9e48eAA557F6 sha256 17c929f28c1c3137… byte-identical to HEAD
AsVotedRegistry 0xc73438492c3F9604D99BfF7Aa268B7F77Aa3a9b1 sha256 8af77a788882dcd9… byte-identical to HEAD
AsVotedRegistryDemo 0x5AF1254384965e7E21ab37853Ee6385448331C50 sha256 8af77a788882dcd9… byte-identical to HEAD
DaoStanding 0x7B0B239181CAF8AFaa261f95E2344594d09d53A0 sha256 8f100112913a2820… byte-identical to HEAD
DaoStandingDemo 0x1dA328B19AbCaA8c30BA62c56D7e8775D7e0D380 sha256 8f100112913a2820… byte-identical to HEAD
GrantGate 0x638Ae4Cd8F0c62e373626E88F75490817bBD6877 sha256 6ef6823340a08717… byte-identical to HEAD
GrantGateDemo 0xecEb8c215fe63Fe1eBeF09f4Fe236087E106C50B sha256 6ef6823340a08717… byte-identical to HEAD
```

## PASS · Ledger invariant holds on both registries (counters and recomputation)

```
canonical received 1500000000000000000 = pledges 0 + open 800000000000000000 + claimable 700000000000000000 + claimed 0; demo received 9500000000000000001 = 0 + 0 + 0 + 9500000000000000001
```

## PASS · Each registry's eth_getBalance equals what its books hold (every claimed wei has left)

```
canonical 0xc73438492c3F9604D99BfF7Aa268B7F77Aa3a9b1: eth_getBalance 1500000000000000000, held_now 1500000000000000000, claimed 0
demo 0x5AF1254384965e7E21ab37853Ee6385448331C50: eth_getBalance 0, held_now 0, claimed 9500000000000000001
```

## PASS · Demo registry drained: eth_getBalance is 0 and the books hold 0

```
demo eth_getBalance 0; held_now 0, pledges 0, open 0, claimable 0
```

## PASS · Every demo payout arrived at its recipient (claim FINALIZED, external transfer executed, none skipped, recipient eth_getBalance moved by exactly amount - fee)

```
4 payouts, 9500000000000000001 wei = demo claimed 9500000000000000001
ARRIVED 0xcebb46a25aa067a9124341fc6aa9d69055b48dc23cce223a264939d24bc94e52 claim by 0x96bd3efa59880bd5a51e5debd817bd544f8584ae: 2350000000000000000 wei; balance 1979200582560199049509 -> 1981550456253699048686 (= +2350000000000000000 - fee 126306500000823: exact)
ARRIVED 0x04362c04cc44214bf1acf13fd260da9e288b7c1d424e7e6787f55d20619b4a74 claim by 0xf9469ea4a318403492e230ff60e397aa33319bf2: 400000000000000000 wei; balance 1996789871315999898301 -> 1997189745009499897478 (= +400000000000000000 - fee 126306500000823: exact)
ARRIVED 0x8ca561a4e1e1dec2e87baf5b7a78c18654a8f3052caba3915f16971fa0c20efa claim by 0x88fe8ab95e561a57ce2dd375355858a0893d5d2d: 6450000000000000000 wei; balance 931792074953249921345 -> 938241948646249920522 (= +6450000000000000000 - fee 126307000000823: exact)
ARRIVED 0x07b2d33e31dd6b763fe1c083d2cccaca8a58919bd78a03d4cac9590ba9ce4db8 claim by 0x55020dff7d5fa3d4422e3bbe56d99c88763687a8: 300000000000000001 wei; balance 998095915412999962253 -> 998395789105999961431 (= +300000000000000001 - fee 126307000000823: exact)
```

## PASS · Nothing stuck: no open check more than 3 h past its deadline (each has a permissionless exit)

```
none
```

## PASS · No state written before any check that can revert (AST scan, every write method of every contract)

```
AsVotedJudge.judge                       first write L1933 self.judgments[key]                  last revert before L1931   PASS
AsVotedRegistry.list_dao                 first write L758 self.daos[u64(did)]                   last revert before L755    PASS
AsVotedRegistry.claim_dao                first write L791 d.controller                          last revert before L789    PASS
AsVotedRegistry.pledge                   first write L808 self._refuse()                        last revert before -       PASS
AsVotedRegistry.request_withdrawal       first write L829 d.withdraw_amount                     last revert before L827    PASS
AsVotedRegistry.cancel_withdrawal        first write L846 d.withdraw_amount                     last revert before L845    PASS
AsVotedRegistry.execute_withdrawal       first write L872 d.pledge                              last revert before L869    PASS
AsVotedRegistry.file_check               first write L934 self._refuse()                        last revert before -       PASS
AsVotedRegistry.rule                     first write L1127 c.ruling                             last revert before L1120   PASS
AsVotedRegistry.appeal                   first write L1260 self._refuse()                       last revert before -       PASS
AsVotedRegistry.finalize                 first write L1324 self._drop()                         last revert before L1321   PASS
AsVotedRegistry.expire                   first write L1358 self._drop()                         last revert before L1355   PASS
AsVotedRegistry.record_coverage          first write L1523 self.coverage[p[0]]                  last revert before L1514   PASS
AsVotedRegistry.claim                    first write L1537 self.claimable[who]                  last revert before L1534   PASS
ExecReader.read_execution                first write L1122 self.execs[u64(eid)]                 last revert before L1115   PASS
GrantGate.request_grant                  first write L86 self.requests[u64(rid)]                last revert before -       PASS
VoteReader.read_proposal                 first write L1344 self.props[u64(vid)]                 last revert before L1341   PASS
VoteReader.read_space                    first write L1393 self.binds[u64(bid)]                 last revert before L1390   PASS
VoteReader.read_names_at                 first write L1439 self.names_at[key]                   last revert before L1436   PASS
```

## PASS · Views read storage only (no writes, no web/model calls in any view); get_ledger recomputation matches counters

```
Ran 4 tests in 0.402s  OK
```

## PASS · Evidence bound at filing to (chain, Safe, tx, proposal CID, block) and snapshotted (reader evidence hashes match every check)

```
15 canonical checks compared; mismatches: none
```

## PASS · Every pinned source authenticated: IPFS bytes hashed against the CID in the contract, hub record cross-checked; no GitHub source is used

```
VoteReader.fetch_ipfs uses only bytes for which cid_matches() holds; read_proposal refuses HUB_RECORD_DIFFERS_FROM_IPFS
```

## PASS · Allowlisted hosts only, matched exactly

```
Every URL literal in the contracts: https://eth-pokt.nodies.app, https://rpc.mevblocker.io, https://arb1.arbitrum.io/rpc, https://arb-pokt.nodies.app, https://mainnet.optimism.io, https://optimism.drpc.org, https://mainnet.base.org, https://base-pokt.nodies.app, https://polygon-bor-rpc.publicnode.com, https://polygon.drpc.org, https://snapshot.4everland.link/ipfs/, https://ipfs.snapshot.box/ipfs/, https://hub.snapshot.org/graphql. rpc_send refuses any URL not in CHAINS; VoteReader.http_get refuses any URL not a gateway+valid CID, the hub query endpoint, or a CHAINS RPC.
```

## PASS · Nobody acts for a DAO they don't control: a listing needs the space's own treasury setting (unverified by Snapshot, so each listing is its own record); claims, pledges and DEVIATES appeals need a space admin/moderator; canonical has no demo seam

```
8 canonical listings, each with a listed=true binding (bad: none); canonical demo_controllers = []; demo log: "claim by a non-admin is refused"
```

## PASS · All offline tests pass (contracts: python unittest; patrol: node --test against mocked chains and registries)

```
Ran 229 tests in 13.528s  OK | frontend: # tests 54, # pass 54, # fail 0
```

## PASS · Demo: every path end to end on chain (each verdict, appeal won / lost, expiries, duplicate, unauthorized claim, consumer refusal, drain)

```
35/35 expectations passed (docs/demo-run.log)
```

## PASS · Partial or unreadable data refuses or is UNCLEAR, never a guess

```
tests: RPC disagreement, IPFS mismatch, hub mismatch, scores not final, unknown decimals, no amount stated, unsupported voting type, too deep, too many actions
```

## PASS · Replay / duplicate filings refused

```
test_duplicate_and_replay_refused, a40; demo: duplicate filing refused on chain
```

## PASS · What the model is never allowed to decide holds

```
a60 (injection: nothing reaches the model when code settles), a61 (model sees only unsettled actions), overall/severity/money computed in code (finish, severity_of, _settle)
```

## PASS · Disagreement behaviour documented exactly as on chain

```
test_validator_disagreement_writes_nothing; test_leader_naming_an_old_block_is_rejected; README 'When validators disagree'
```

## PASS · Fees on every write (estimated per call by simulation, generic estimate as fallback)

```
test/harness.mjs send(), frontend lib/contract.ts send(), lib/patrol.ts write()
```

## PASS · README and /docs: Scope states what is proven and what is covered; required sections; neutral wording (no guaranteed/100%/limitation/TODO)

```
missing sections: none; flagged words: none; Scope statements missing: none
```

## PASS · Live site: 10+ numbers equal the chain

```
17 numbers compared, mismatches: []
= checks: site "15" chain "15"
= final:AS_VOTED: site "0" chain "0"
= final:DEVIATES: site "0" chain "0"
= final:UNCLEAR: site "7" chain "7"
= daos: site "8" chain "8"
= pledges: site "0" chain "0"
= Canonical registry:received: site "1.5 GEN" chain "1.5 GEN"
= Canonical registry:open: site "0.8 GEN" chain "0.8 GEN"
= Canonical registry:claimable: site "0.7 GEN" chain "0.7 GEN"
= Canonical registry:held_now: site "1.5 GEN" chain "1.5 GEN"
= Demo registry:received: site "9.5 GEN" chain "9.5 GEN"
= Demo registry:held_now: site "0 GEN" chain "0 GEN"
= Demo registry:claimed: site "9.5 GEN" chain "9.5 GEN"
= dao:final as voted: site "0" chain "0"
= dao:final deviates: site "0" chain "0"
= dao:final unclear: site "4" chain "4"
= dao:open checks: site "4" chain "4"
```

## PASS · 375 px: no horizontal scroll on any page

```
/ 375, /daos 375, /dao/1 375, /check/1 375, /check/7 375, /check/9 375, /check/11 375, /file 375, /patrol 375, /docs 375, /verify 375
```

## PASS · Patrol state is durable: patrol-state branch holds per-Safe checkpoints for the canonical registry, a retry queue and unmatched executions

```
registry 0xc73438492c3f9604d99bff7aa268b7f77aa3a9b1; updated 2026-10-18T23:02:53.000Z; 8 checkpoints:
  base|0x65136b3e4f012e4c13aff0926091e2eadcfedb42 through block 52579720 (from 52484321)
  ethereum|0x619bbf92fd6ba59893327676b2685a3762a49a33 through block 26207523 (from 26171524)
  ethereum|0x8cf60b289f8d31f737049b590b5e4285ff0bd1d1 through block 26207523 (from 26171524)
  ethereum|0xca771eda0c70aa7d053ab1b25004559b918fe662 through block 26207523 (from 26171524)
  ethereum|0xcba28b38103307ec8da98377fff9816c164f9afa through block 26207523 (from 26171524)
  ethereum|0xe4762eacebdb7585d32079fdcba5bb94eb5d76f2 through block 26207523 (from 26171524)
  ethereum|0xf26d1bb347a59f6c283c53156519cc1b1abaca51 through block 26207523 (from 26171524)
  optimism|0xf93a7f819f83dbfdbc307d4d4f0fe5a208c50318 through block 158292139 (from 158076140)
retry queue 0; unmatched 1; pending txs 0
```

## PASS · Coverage heartbeat on chain for every canonical DAO (record_coverage by the patrol), and DaoStanding answers with a structured state

```
dao #1 cow.eth ethereum 0xca771eda0c70aa7d053ab1b25004559b918fe662: coverage block 26207523 (block time 2026-10-16T20:34:35.000Z, recorded 2026-10-18T23:02:09.000Z); standing PENDING - 4 check(s) of this DAO still open
dao #2 paraswap-dao.eth ethereum 0x619bbf92fd6ba59893327676b2685a3762a49a33: coverage block 26207523 (block time 2026-10-16T20:34:35.000Z, recorded 2026-10-18T23:02:09.000Z); standing PENDING - 1 check(s) of this DAO still open
dao #3 paraswap-dao.eth optimism 0xf93a7f819f83dbfdbc307d4d4f0fe5a208c50318: coverage block 158292139 (block time 2026-10-16T20:37:35.000Z, recorded 2026-10-18T23:02:09.000Z); standing STALE_MONITORING - the monitor's coverage ends at block 158292139 (time 1792183055), more than 21600 s before
dao #4 paraswap-dao.eth base 0x65136b3e4f012e4c13aff0926091e2eadcfedb42: coverage block 52579720 (block time 2026-10-14T03:33:07.000Z, recorded 2026-10-18T23:02:09.000Z); standing PENDING - 1 check(s) of this DAO still open
dao #5 banklessvault.eth ethereum 0xf26d1bb347a59f6c283c53156519cc1b1abaca51: coverage block 26207523 (block time 2026-10-16T20:34:35.000Z, recorded 2026-10-18T23:02:09.000Z); standing PENDING - 1 check(s) of this DAO still open
dao #6 morpho.eth ethereum 0xcba28b38103307ec8da98377fff9816c164f9afa: coverage block 26207523 (block time 2026-10-16T20:34:35.000Z, recorded 2026-10-18T23:02:09.000Z); standing STALE_MONITORING - the monitor's coverage ends at block 26207523 (time 1792182875), more than 21600 s before
dao #7 safe.eth ethereum 0x8cf60b289f8d31f737049b590b5e4285ff0bd1d1: coverage block 26207523 (block time 2026-10-16T20:34:35.000Z, recorded 2026-10-18T23:02:09.000Z); standing PENDING - 1 check(s) of this DAO still open
dao #8 krausehouse.eth ethereum 0xe4762eacebdb7585d32079fdcba5bb94eb5d76f2: coverage block 26207523 (block time 2026-10-16T20:34:35.000Z, recorded 2026-10-18T23:02:09.000Z); standing STALE_MONITORING - the monitor's coverage ends at block 26207523 (time 1792182875), more than 21600 s before
```

## PASS · GrantGate acts only on COMPLIANT: every DaoStanding state shown on chain in the demo

```
NO_COVERAGE: shown; PENDING: shown; COMPLIANT: shown; DEVIATES: shown; STALE_MONITORING: shown
```

## PASS · One set of addresses everywhere (deployments.json, site, ADDRESSES.md, SUBMISSION)

```
missing: none; other addresses: none
```

## PASS · Vercel deployment live and green (site 200, patrol endpoint answers)

```
GET / 200; /api/patrol dry run watched 8 Safes on 0xc73438492c3F9604D99BfF7Aa268B7F77Aa3a9b1
```

## PASS · Git history clean: no keys or secrets ever committed, no assistant attribution, no force pushes, tree clean

```
commits touching key files: none; attribution in messages: none; working tree: clean
```
