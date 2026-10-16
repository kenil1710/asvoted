# Final check

Run 2026-10-16T15:34:11.723Z by `tools/final_check.mjs` against commit `dc0731c9cf`, the live site and Studio Dev. **23/23 PASS.**

## PASS · Source match: every address byte-identical to HEAD, all from one commit, contracts/ untouched since

```
commit 07ff3a3d2add9702114feca11317dab78d9d8966; contracts/ changes since: none
ExecReader 0x694E28e38D66C95E3A2138e5d22F8158939e21f8 sha256 d2b6475e2272a3a4… byte-identical to HEAD
VoteReader 0x7319257a270EE4D77A302f193Eff76878ec02BCa sha256 60079ef401ad1769… byte-identical to HEAD
AsVotedJudge 0xC2aBc36E01DEab31C1F24A66A8D010Cd9F7F7dfF sha256 17c929f28c1c3137… byte-identical to HEAD
AsVotedRegistry 0x4Ec22423528e64B4f1d41B7F647c0BD42464a30C sha256 0fe7b81ca80ff1f2… byte-identical to HEAD
AsVotedRegistryDemo 0x65dB1CD4b79Bc87e5d6dbA315ea8F4239eAea028 sha256 0fe7b81ca80ff1f2… byte-identical to HEAD
DaoStanding 0xA74Bb08f0e497fc18138bF5383e5f65974eE3CCb sha256 d45495c84350bc8f… byte-identical to HEAD
DaoStandingDemo 0x6EC6F4fABd87C7A7DCA24044ED011631106c408c sha256 d45495c84350bc8f… byte-identical to HEAD
GrantGate 0x9848d38C85E1DFc8920c353124De3c82B519a62e sha256 2fc4477e774a6871… byte-identical to HEAD
GrantGateDemo 0x428727dF01a31202a66B2ED7d35F474Ba7B97C28 sha256 2fc4477e774a6871… byte-identical to HEAD
```

## PASS · Ledger invariant holds on both registries (counters and recomputation)

```
canonical received 1500000000000000000 = pledges 0 + open 800000000000000000 + claimable 700000000000000000 + claimed 0; demo received 13100000000000000002 = 0 + 0 + 0 + 13100000000000000002
```

## PASS · Demo registry drained to exactly 0 held

```
demo held_now 0, claimed 13100000000000000002, on-chain balance 13100000000000000002 (Studio Dev queues claim transfers; see README)
```

## PASS · Nothing stuck: no open check more than 3 h past its deadline (each has a permissionless exit)

```
none
```

## PASS · No state written before any check that can revert (AST scan, every write method of every contract)

```
AsVotedJudge.judge                       first write L1933 self.judgments[key]                  last revert before L1931   PASS
AsVotedRegistry.list_dao                 first write L734 self.daos[u64(did)]                   last revert before L731    PASS
AsVotedRegistry.claim_dao                first write L767 d.controller                          last revert before L765    PASS
AsVotedRegistry.pledge                   first write L784 self._refuse()                        last revert before -       PASS
AsVotedRegistry.request_withdrawal       first write L805 d.withdraw_amount                     last revert before L803    PASS
AsVotedRegistry.cancel_withdrawal        first write L822 d.withdraw_amount                     last revert before L821    PASS
AsVotedRegistry.execute_withdrawal       first write L848 d.pledge                              last revert before L845    PASS
AsVotedRegistry.file_check               first write L910 self._refuse()                        last revert before -       PASS
AsVotedRegistry.rule                     first write L1103 c.ruling                             last revert before L1096   PASS
AsVotedRegistry.appeal                   first write L1236 self._refuse()                       last revert before -       PASS
AsVotedRegistry.finalize                 first write L1300 self._drop()                         last revert before L1297   PASS
AsVotedRegistry.expire                   first write L1334 self._drop()                         last revert before L1331   PASS
AsVotedRegistry.claim                    first write L1452 self.claimable[who]                  last revert before L1450   PASS
ExecReader.read_execution                first write L1122 self.execs[u64(eid)]                 last revert before L1115   PASS
GrantGate.request_grant                  first write L83 self.requests[u64(rid)]                last revert before -       PASS
VoteReader.read_proposal                 first write L1344 self.props[u64(vid)]                 last revert before L1341   PASS
VoteReader.read_space                    first write L1393 self.binds[u64(bid)]                 last revert before L1390   PASS
VoteReader.read_names_at                 first write L1439 self.names_at[key]                   last revert before L1436   PASS
```

## PASS · Views read storage only (no writes, no web/model calls in any view); get_ledger recomputation matches counters

```
Ran 4 tests in 0.393s  OK
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
Ran 203 tests in 12.922s  OK
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
= final:UNCLEAR: site "7" chain "7"
= daos: site "8" chain "8"
= pledges: site "0" chain "0"
= Canonical registry:received: site "1.5 GEN" chain "1.5 GEN"
= Canonical registry:open: site "0.8 GEN" chain "0.8 GEN"
= Canonical registry:claimable: site "0.7 GEN" chain "0.7 GEN"
= Canonical registry:held_now: site "1.5 GEN" chain "1.5 GEN"
= Demo registry:received: site "13.1 GEN" chain "13.1 GEN"
= Demo registry:held_now: site "0 GEN" chain "0 GEN"
= Demo registry:claimed: site "13.1 GEN" chain "13.1 GEN"
= dao:final as voted: site "0" chain "0"
= dao:final deviates: site "0" chain "0"
= dao:final unclear: site "4" chain "4"
= dao:open checks: site "4" chain "4"
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
GET / 200; /api/patrol dry run watched 8 Safes on 0x4Ec22423528e64B4f1d41B7F647c0BD42464a30C
```

## PASS · Git history clean: no keys or secrets ever committed, no assistant attribution, no force pushes, tree clean

```
commits touching key files: none; attribution in messages: none; working tree: clean
```
