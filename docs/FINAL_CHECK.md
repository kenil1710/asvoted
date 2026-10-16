# Final check

Run 2026-10-16T09:46:50.431Z by `tools/final_check.mjs` against commit `3e7071fa74`, the live site and Studio Dev. **23/23 PASS.**

## PASS · Source match: every address byte-identical to HEAD, all from one commit, contracts/ untouched since

```
commit 7a746655daf01070f0cedfef806933ba243113dd; contracts/ changes since: none
ExecReader 0x6AFBFDE6D81b2DC3EbaE2Af822dF31f9D97dDC5a sha256 d2b6475e2272a3a4… byte-identical to HEAD
VoteReader 0x7e4a6F43Df5Bb28ECd6D4E3b8a9DB5186200Bb88 sha256 3f833fff652c40f8… byte-identical to HEAD
AsVotedJudge 0xa75aF3785c25056589B0348a19b8fB10f5F66304 sha256 e7d1482f09d32997… byte-identical to HEAD
AsVotedRegistry 0x1C2891FE54a5CfE98436F439e40A3043050eFF44 sha256 237bb7a1972032eb… byte-identical to HEAD
AsVotedRegistryDemo 0x8B904F094F5b2A25C5004Ab09301dc9041c17B7a sha256 237bb7a1972032eb… byte-identical to HEAD
DaoStanding 0x785b9091dBFc1a45F76ccE89Eaa22Dd8fb9A6D1E sha256 d45495c84350bc8f… byte-identical to HEAD
DaoStandingDemo 0x659c4FE83ccFdfD0a6cC55A0004d70E574DfBDfa sha256 d45495c84350bc8f… byte-identical to HEAD
GrantGate 0x8691BaB8DB890C5B20F563dE9e6f0c33645ad4c4 sha256 2fc4477e774a6871… byte-identical to HEAD
GrantGateDemo 0xCC8De1d9b971B7fF484bbFb1C0CB1F9B2045BA7F sha256 2fc4477e774a6871… byte-identical to HEAD
```

## PASS · Ledger invariant holds on both registries (counters and recomputation)

```
canonical received 1500000000000000000 = pledges 0 + open 1000000000000000000 + claimable 500000000000000000 + claimed 0; demo received 12800000000000000002 = 0 + 0 + 0 + 12800000000000000002
```

## PASS · Demo registry drained to exactly 0 held

```
demo held_now 0, claimed 12800000000000000002, on-chain balance 12800000000000000002 (Studio Dev queues claim transfers; see README)
```

## PASS · Nothing stuck: no open check more than 3 h past its deadline (each has a permissionless exit)

```
none
```

## PASS · No state written before any check that can revert (AST scan, every write method of every contract)

```
AsVotedJudge.judge                       first write L1775 self.judgments[key]                  last revert before L1773   PASS
AsVotedRegistry.list_dao                 first write L731 self.daos[u64(did)]                   last revert before L728    PASS
AsVotedRegistry.claim_dao                first write L764 d.controller                          last revert before L762    PASS
AsVotedRegistry.pledge                   first write L781 self._refuse()                        last revert before -       PASS
AsVotedRegistry.request_withdrawal       first write L802 d.withdraw_amount                     last revert before L800    PASS
AsVotedRegistry.cancel_withdrawal        first write L819 d.withdraw_amount                     last revert before L818    PASS
AsVotedRegistry.execute_withdrawal       first write L845 d.pledge                              last revert before L842    PASS
AsVotedRegistry.file_check               first write L907 self._refuse()                        last revert before -       PASS
AsVotedRegistry.rule                     first write L1053 c.ruling                             last revert before L1046   PASS
AsVotedRegistry.appeal                   first write L1173 self._refuse()                       last revert before -       PASS
AsVotedRegistry.finalize                 first write L1224 self._drop()                         last revert before L1221   PASS
AsVotedRegistry.expire                   first write L1258 self._drop()                         last revert before L1255   PASS
AsVotedRegistry.claim                    first write L1376 self.claimable[who]                  last revert before L1374   PASS
ExecReader.read_execution                first write L1122 self.execs[u64(eid)]                 last revert before L1115   PASS
GrantGate.request_grant                  first write L83 self.requests[u64(rid)]                last revert before -       PASS
VoteReader.read_proposal                 first write L1282 self.props[u64(vid)]                 last revert before L1279   PASS
VoteReader.read_space                    first write L1331 self.binds[u64(bid)]                 last revert before L1328   PASS
VoteReader.read_names_at                 first write L1373 self.names_at[key]                   last revert before L1371   PASS
```

## PASS · Views read storage only (no writes, no web/model calls in any view); get_ledger recomputation matches counters

```
Ran 4 tests in 0.385s  OK
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

## PASS · All offline tests pass

```
Ran 187 tests in 12.630s  OK
```

## PASS · Demo: every path end to end on chain (each verdict, appeal won / lost, expiries, duplicate, unauthorized claim, consumer refusal, drain)

```
25/25 expectations passed (docs/demo-run.log)
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

## PASS · README: required sections, neutral wording, no guaranteed/100%

```
missing: none; flagged words: none
```

## PASS · Live site: 10+ numbers equal the chain

```
17 numbers compared, mismatches: []
= checks: site "15" chain "15"
= final:AS_VOTED: site "0" chain "0"
= final:DEVIATES: site "0" chain "0"
= final:UNCLEAR: site "5" chain "5"
= daos: site "8" chain "8"
= pledges: site "0" chain "0"
= Canonical registry:received: site "1.5 GEN" chain "1.5 GEN"
= Canonical registry:open: site "1 GEN" chain "1 GEN"
= Canonical registry:claimable: site "0.5 GEN" chain "0.5 GEN"
= Canonical registry:held_now: site "1.5 GEN" chain "1.5 GEN"
= Demo registry:received: site "12.8 GEN" chain "12.8 GEN"
= Demo registry:held_now: site "0 GEN" chain "0 GEN"
= Demo registry:claimed: site "12.8 GEN" chain "12.8 GEN"
= dao:final as voted: site "0" chain "0"
= dao:final deviates: site "0" chain "0"
= dao:final unclear: site "2" chain "2"
= dao:open checks: site "6" chain "6"
```

## PASS · 375 px: no horizontal scroll on any page

```
/ 375, /daos 375, /dao/1 375, /check/1 375, /check/7 375, /check/9 375, /check/11 375, /file 375, /patrol 375, /docs 375, /verify 375
```

## PASS · One set of addresses everywhere (deployments.json, site, ADDRESSES.md, SUBMISSION)

```
missing: none; other addresses: none
```

## PASS · Vercel deployment live and green (site 200, patrol endpoint answers)

```
GET / 200; /api/patrol dry run watched 8 Safes on 0x1C2891FE54a5CfE98436F439e40A3043050eFF44
```

## PASS · Git history clean: no keys or secrets ever committed, no assistant attribution, no force pushes, tree clean

```
commits touching key files: none; attribution in messages: none; working tree: clean
```
