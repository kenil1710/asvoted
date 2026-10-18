# Final check

Run 2026-10-17T22:10:15.429Z by `tools/final_check.mjs` against commit `75815c0eec`, the live site and Studio Dev. **25/25 PASS.**

## PASS · Source match: every address byte-identical to HEAD, all from one commit, contracts/ untouched since

```
commit ab42d5c632d3c80ac11da5762be116962434e69f; contracts/ changes since: none
ExecReader 0xA08486C9b6518B734D19Af58948db36FE3bdD961 sha256 d2b6475e2272a3a4… byte-identical to HEAD
VoteReader 0x029870D42f42f808eFE707fea6BB3D78dA48147F sha256 60079ef401ad1769… byte-identical to HEAD
AsVotedJudge 0xa7c0123bBc8c1982C2cD037e723aA0d1AbB6a2a1 sha256 17c929f28c1c3137… byte-identical to HEAD
AsVotedRegistry 0x808bbc73B8C65312d14e421C51C774EB4E90121C sha256 f7e5a79b9323cba3… byte-identical to HEAD
AsVotedRegistryDemo 0xBcD9e80084C796CB3ca07126c5180CD0bdB537D1 sha256 f7e5a79b9323cba3… byte-identical to HEAD
DaoStanding 0xF12CA2B1440AAB7915879D84Abf04123D71d905f sha256 d45495c84350bc8f… byte-identical to HEAD
DaoStandingDemo 0xfcae1de4D6B42752bFeF59bEa9140B6e4e39c128 sha256 d45495c84350bc8f… byte-identical to HEAD
GrantGate 0xf4A21d3e39e6807202Cd9f656EAAF1F7C115e187 sha256 2fc4477e774a6871… byte-identical to HEAD
GrantGateDemo 0x3C77CA433b10E71a414203a7FFeB20Bf10e20296 sha256 2fc4477e774a6871… byte-identical to HEAD
```

## PASS · Ledger invariant holds on both registries (counters and recomputation)

```
canonical received 1500000000000000000 = pledges 600000000000000000 + open 0 + claimable 900000000000000000 + claimed 0; demo received 9400000000000000001 = 0 + 0 + 0 + 9400000000000000001
```

## PASS · Each registry's eth_getBalance equals what its books hold (every claimed wei has left)

```
canonical 0x808bbc73B8C65312d14e421C51C774EB4E90121C: eth_getBalance 1500000000000000000, held_now 1500000000000000000, claimed 0
demo 0xBcD9e80084C796CB3ca07126c5180CD0bdB537D1: eth_getBalance 0, held_now 0, claimed 9400000000000000001
```

## PASS · Demo registry drained: eth_getBalance is 0 and the books hold 0

```
demo eth_getBalance 0; held_now 0, pledges 0, open 0, claimable 0
```

## PASS · Every demo payout arrived at its recipient (claim FINALIZED, external transfer executed, none skipped, recipient eth_getBalance moved by exactly amount - fee)

```
4 payouts, 9400000000000000001 wei = demo claimed 9400000000000000001
ARRIVED 0x576bd5a382d4276d4457975b3c10fd94236751f5cfa1739f99d96c497eb4aeb1 claim by 0x96bd3efa59880bd5a51e5debd817bd544f8584ae: 2400000000000000000 wei; balance 1980417702979699214109 -> 1982817576673199213286 (= +2400000000000000000 - fee 126306500000823: exact)
ARRIVED 0x2ba5c8f7ccad0c0de435aa6c4ae7fddb203a6dca759b056960ecc8117f6d9a1c claim by 0xf9469ea4a318403492e230ff60e397aa33319bf2: 400000000000000000 wei; balance 1997191255868749912292 -> 1997591129562249911469 (= +400000000000000000 - fee 126306500000823: exact)
ARRIVED 0x82772f6f7aa0278461c5a96ada7c437ad4b557d2fbf0cb4f4038b2a6423507cc claim by 0x88fe8ab95e561a57ce2dd375355858a0893d5d2d: 6300000000000000000 wei; balance 939693537963749936159 -> 945993411656749935336 (= +6300000000000000000 - fee 126307000000823: exact)
ARRIVED 0x3d73172f9d01a197183031a61cf460877d768b5972e3b9576f2bb7518ae985c4 claim by 0x55020dff7d5fa3d4422e3bbe56d99c88763687a8: 300000000000000001 wei; balance 998096561182499968014 -> 998396434875499967192 (= +300000000000000001 - fee 126307000000823: exact)
```

## PASS · Nothing stuck: no open check more than 3 h past its deadline (each has a permissionless exit)

```
none
```

## PASS · No state written before any check that can revert (AST scan, every write method of every contract)

```
AsVotedJudge.judge                       first write L1933 self.judgments[key]                  last revert before L1931   PASS
AsVotedRegistry.list_dao                 first write L749 self.daos[u64(did)]                   last revert before L746    PASS
AsVotedRegistry.claim_dao                first write L782 d.controller                          last revert before L780    PASS
AsVotedRegistry.pledge                   first write L799 self._refuse()                        last revert before -       PASS
AsVotedRegistry.request_withdrawal       first write L820 d.withdraw_amount                     last revert before L818    PASS
AsVotedRegistry.cancel_withdrawal        first write L837 d.withdraw_amount                     last revert before L836    PASS
AsVotedRegistry.execute_withdrawal       first write L863 d.pledge                              last revert before L860    PASS
AsVotedRegistry.file_check               first write L925 self._refuse()                        last revert before -       PASS
AsVotedRegistry.rule                     first write L1118 c.ruling                             last revert before L1111   PASS
AsVotedRegistry.appeal                   first write L1251 self._refuse()                       last revert before -       PASS
AsVotedRegistry.finalize                 first write L1315 self._drop()                         last revert before L1312   PASS
AsVotedRegistry.expire                   first write L1349 self._drop()                         last revert before L1346   PASS
AsVotedRegistry.claim                    first write L1482 self.claimable[who]                  last revert before L1479   PASS
ExecReader.read_execution                first write L1122 self.execs[u64(eid)]                 last revert before L1115   PASS
GrantGate.request_grant                  first write L83 self.requests[u64(rid)]                last revert before -       PASS
VoteReader.read_proposal                 first write L1344 self.props[u64(vid)]                 last revert before L1341   PASS
VoteReader.read_space                    first write L1393 self.binds[u64(bid)]                 last revert before L1390   PASS
VoteReader.read_names_at                 first write L1439 self.names_at[key]                   last revert before L1436   PASS
```

## PASS · Views read storage only (no writes, no web/model calls in any view); get_ledger recomputation matches counters

```
Ran 4 tests in 0.392s  OK
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
Ran 207 tests in 13.056s  OK
```

## PASS · Demo: every path end to end on chain (each verdict, appeal won / lost, expiries, duplicate, unauthorized claim, consumer refusal, drain)

```
30/30 expectations passed (docs/demo-run.log)
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
= final:AS_VOTED: site "6" chain "6"
= final:DEVIATES: site "2" chain "2"
= final:UNCLEAR: site "7" chain "7"
= daos: site "8" chain "8"
= pledges: site "0.6" chain "0.6"
= Canonical registry:received: site "1.5 GEN" chain "1.5 GEN"
= Canonical registry:open: site "0 GEN" chain "0 GEN"
= Canonical registry:claimable: site "0.9 GEN" chain "0.9 GEN"
= Canonical registry:held_now: site "1.5 GEN" chain "1.5 GEN"
= Demo registry:received: site "9.4 GEN" chain "9.4 GEN"
= Demo registry:held_now: site "0 GEN" chain "0 GEN"
= Demo registry:claimed: site "9.4 GEN" chain "9.4 GEN"
= dao:final as voted: site "3" chain "3"
= dao:final deviates: site "1" chain "1"
= dao:final unclear: site "4" chain "4"
= dao:open checks: site "0" chain "0"
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
GET / 200; /api/patrol dry run watched 8 Safes on 0x808bbc73B8C65312d14e421C51C774EB4E90121C
```

## PASS · Git history clean: no keys or secrets ever committed, no assistant attribution, no force pushes, tree clean

```
commits touching key files: none; attribution in messages: none; working tree: clean
```
