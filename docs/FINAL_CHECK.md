# Final check

Run 2026-10-16T02:19:32.501Z by `tools/final_check.mjs` against commit `c8fe01329d`, the live site and Studio Dev. **20/23 PASS.**

## PASS · Source match: every address byte-identical to HEAD, all from one commit, contracts/ untouched since

```
commit 93d5be9a66b98ba6d0b0e5f36b8f44562c30a83b; contracts/ changes since: none
ExecReader 0x31EabbC7978d784e9EeaAf5c4FFD82eD9BC5eeB9 sha256 4909d23888c4da17… byte-identical to HEAD
VoteReader 0xe00Cc656c9cED6F61505E9b7440Dad2B690C19FB sha256 4ee549d44fd54eda… byte-identical to HEAD
AsVotedJudge 0x4fFdAf25Fb27ba9bCeDAA0f94d93D14993a69Fb4 sha256 4c123527d890961d… byte-identical to HEAD
AsVotedRegistry 0x2B4ac2D50978fc4937E9a479e4706688a6c5cCdc sha256 2810e1bb0f9a2e89… byte-identical to HEAD
AsVotedRegistryDemo 0x01AB66898cB6f1E949449f4a9B3D384f1079ea93 sha256 2810e1bb0f9a2e89… byte-identical to HEAD
DaoStanding 0x2dee7BBc3e09E058B3AbEdfEeD2a2334ba69b870 sha256 952d2995d8f12e54… byte-identical to HEAD
DaoStandingDemo 0x5115162037A6aB89Bc70862b9C535e13f26D3693 sha256 952d2995d8f12e54… byte-identical to HEAD
GrantGate 0x31EAFAAbd993be7F837569cf8aecBb44CaA233D4 sha256 2fc4477e774a6871… byte-identical to HEAD
GrantGateDemo 0x8e437a04970bc587adaE2764F8E18A171fe1d946 sha256 2fc4477e774a6871… byte-identical to HEAD
```

## PASS · Ledger invariant holds on both registries (counters and recomputation)

```
canonical received 1500000000000000000 = pledges 1000000000000000000 + open 0 + claimable 500000000000000000 + claimed 0; demo received 9200000000000000001 = 0 + 0 + 0 + 9200000000000000001
```

## PASS · Demo registry drained to exactly 0 held

```
demo held_now 0, claimed 9200000000000000001, on-chain balance 9200000000000000001 (Studio Dev queues claim transfers; see README)
```

## PASS · Nothing stuck: no open check more than 3 h past its deadline (each has a permissionless exit)

```
none
```

## PASS · No state written before any check that can revert (AST scan, every write method of every contract)

```
AsVotedJudge.judge                       first write L1274 self.judgments[key]                  last revert before L1272   PASS
AsVotedRegistry.list_dao                 first write L718 self.daos[u64(did)]                   last revert before L715    PASS
AsVotedRegistry.claim_dao                first write L750 d.controller                          last revert before L748    PASS
AsVotedRegistry.pledge                   first write L767 self._refuse()                        last revert before -       PASS
AsVotedRegistry.request_withdrawal       first write L788 d.withdraw_amount                     last revert before L786    PASS
AsVotedRegistry.cancel_withdrawal        first write L802 d.withdraw_amount                     last revert before L801    PASS
AsVotedRegistry.execute_withdrawal       first write L827 d.pledge                              last revert before L824    PASS
AsVotedRegistry.file_check               first write L875 self._refuse()                        last revert before -       PASS
AsVotedRegistry.rule                     first write L981 c.ruling                              last revert before L974    PASS
AsVotedRegistry.appeal                   first write L1059 self._refuse()                       last revert before -       PASS
AsVotedRegistry.finalize                 first write L1094 self._drop()                         last revert before L1091   PASS
AsVotedRegistry.expire                   first write L1121 self._drop()                         last revert before L1118   PASS
AsVotedRegistry.claim                    first write L1212 self.claimable[who]                  last revert before L1210   PASS
ExecReader.read_execution                first write L1027 self.execs[u64(eid)]                 last revert before L1020   PASS
GrantGate.request_grant                  first write L83 self.requests[u64(rid)]                last revert before -       PASS
VoteReader.read_proposal                 first write L1195 self.props[u64(vid)]                 last revert before L1192   PASS
VoteReader.read_space                    first write L1244 self.binds[u64(bid)]                 last revert before L1241   PASS
```

## PASS · Views read storage only (no writes, no web/model calls in any view); get_ledger recomputation matches counters

```
Ran 4 tests in 0.322s  OK
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

## PASS · Nobody acts for a DAO they don't control: listings proven by the space's own treasury setting; claims need a space admin/moderator; canonical has no demo seam

```
9 canonical listings, each with a listed=true binding (bad: none); canonical demo_controllers = []; demo log: "claim by a non-admin is refused"
```

## PASS · All offline tests pass

```
Ran 118 tests in 1.375s  OK
```

## PASS · Demo: every path end to end on chain (each verdict, appeal won / lost, expiries, duplicate, unauthorized claim, consumer refusal, drain)

```
23/23 expectations passed (docs/demo-run.log)
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
= final:AS_VOTED: site "10" chain "10"
= final:DEVIATES: site "2" chain "2"
= final:UNCLEAR: site "3" chain "3"
= daos: site "9" chain "9"
= pledges: site "1" chain "1"
= Canonical registry:received: site "1.5 GEN" chain "1.5 GEN"
= Canonical registry:open: site "0 GEN" chain "0 GEN"
= Canonical registry:claimable: site "0.5 GEN" chain "0.5 GEN"
= Canonical registry:held_now: site "1.5 GEN" chain "1.5 GEN"
= Demo registry:received: site "9.2 GEN" chain "9.2 GEN"
= Demo registry:held_now: site "0 GEN" chain "0 GEN"
= Demo registry:claimed: site "9.2 GEN" chain "9.2 GEN"
= dao:final as voted: site "6" chain "6"
= dao:final deviates: site "1" chain "1"
= dao:final unclear: site "1" chain "1"
= dao:open checks: site "0" chain "0"
```

## FAIL · 375 px: no horizontal scroll on any page

```
/ 375, /daos 375, /dao/1 375, /check/1 424, /file 375, /patrol 375, /docs 375, /verify 375
```

## FAIL · One set of addresses everywhere (deployments.json, site, ADDRESSES.md, SUBMISSION)

```
missing: none; other addresses: 0x614881c554aa58727a51966dfd34cb8f42332b37,0xbadcd1aec3ae56fc351c80e34d2c12f0913f5e62,0x04c4c0daf7a61aa425fe402d1d43695b8bbf4ab9,0xb9824ec1b057ef1b713a85e3dde9640ae0d6b69b,0x55db51e8a8aec3006a824e46ec7f4f70a12a68ff,0x88fe8ab95e561a57ce2dd375355858a0893d5d2d,0x62f1b05c8d6c28cb3c81a1d509663b44847fa188,0x252977af942a64541256321aea5c60179ac7bd2c,0xdc47be3939b7c53cb092258a2cffb6b7d2ff0178,0xcd320ade189e92a45ce7818cb3370bf71f34703a
```

## PASS · Vercel deployment live and green (site 200, patrol endpoint answers)

```
GET / 200; /api/patrol dry run watched 9 Safes on 0x2B4ac2D50978fc4937E9a479e4706688a6c5cCdc
```

## FAIL · Git history clean: no keys or secrets ever committed, no assistant attribution, no force pushes, tree clean

```
commits touching key files: none; attribution in messages: none; working tree: dirty
```
