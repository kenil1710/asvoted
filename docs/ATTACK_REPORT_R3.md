# Attack report, round 3 (second attacker)

Attacked: the deployed code (contracts identical to `93d5be9`). Every finding is a failing test in `test/test_attacks_r3.py` (`test_r3_50`–`test_r3_69`). Amount-matching attacks already in that file from a parallel round (`test_r3_01`–`test_r3_43`: list items, table columns, approve + transfer, "at least", per month, number formats, the prior-execution limit) are not repeated here.

```
cd test && python3 -m unittest test_attacks_r3          # 20 of mine fail on 93d5be9
python3 -m unittest -q test_asvoted test_attacks test_attacks_r2   # 118 still pass
```

On `0b1281a` (the parallel round's contract fixes, not deployed), 19 of the 20 still fail. Only `r3_56` is fixed there: it now rules UNCLEAR.

## Findings

| # | Sev | Finding | Test | Fix |
|---|---|---|---|---|
| 1 | High | ETH sent along with a token call is never counted. The Safe calls `transfer(ALICE, 5)` on a payable contract whose `symbol()` is "USDC" and attaches 1,000 ETH. Only the 5 "USDC" are checked. Ruling: AS_VOTED. | `r3_50` | For every action with `value > 0`, also add a native leg to `target`, whatever its kind. |
| 2 | High | A stranger can appeal a correct AS_VOTED and name an unrelated passed proposal. Judged against that proposal, the execution DEVIATES. The ruling is final, the DAO has no appeal, and the stranger gets 25 % of the pledge. | `r3_64` | Accept `alt_vote_id` only on a DEVIATES appeal by the DAO side. |
| 3 | High | A payment hidden by an expired check. Exec 1 (50k, the full cap) is filed and nobody judges it, so it expires UNCLEAR. `_prior` drops UNCLEAR checks, and `pair_seen` stops anyone filing (exec 1, P) again. Exec 2 pays another 50k and is ruled AS_VOTED. | `r3_60` | Count every earlier execution filed under the proposal, whatever its verdict (the transfers happened). |
| 4 | High | An address inside nested calldata is never checked. Example: `multicall(bytes[])` to a router the proposal names, with an inner call paying MALLORY. The inner words sit 4 bytes off the 32-byte grid, so code finds no address argument and the model decides. | `r3_52` | Also scan the 20-byte windows at offset 4 (mod 32) inside dynamic `bytes` args. If unsure, flag `NESTED_CALLDATA` and rule UNCLEAR. |
| 5 | High | The cap is the largest number near the recipient, whatever it describes. "Send 5,000 USDC to X from the 2,000,000 USDC treasury" lets 2M go to X. "The request from X for 100,000 USDC is rejected" authorizes 100k to X. | `r3_57`, `r3_58` | When a line holds several amounts, or negation words (not / reject / instead), make it UNCLEAR. |
| 6 | High | The losing option sets the cap. In a single-choice vote, "Yes, option A" (50k) wins, yet a 100k payment from option B's text is AS_VOTED. | `r3_59` | When there are more than two choices, or several approving labels, make value legs UNCLEAR (or limit them to the winning option's section). |
| 7 | High (deployed) | Two recipients and two amounts on one line: "Pay A 1,000 USDC and B 90,000 USDC" lets A take 90k. Fixed (UNCLEAR) on `0b1281a`. | `r3_56` | Already fixed in `0b1281a`; deploy it. |
| 8 | Medium | The recipient can turn a correct payment into DEVIATES. The proposal names `alice.eth`, which resolved to Alice at the vote and at the execution. Alice repoints it before anyone reads the proposal, so the name is dropped and the payment counts as going to an unmentioned address (MAJOR slash). An appeal re-reads the same record, so the DAO cannot fix it. | `r3_61` | Resolve names at the execution's block (from the exec record) as well as at the snapshot block. Ignore the current block. |
| 9 | Medium | `transferFrom`'s `from` is never checked. The Safe pulls 1M USDC from BOB, who never appears in the proposal, into itself. That is ruled "into the Safe itself" and AUTHORIZED. | `r3_51` | Require `from` to be the Safe or a mentioned address. |
| 10 | Medium | Address arguments with 10 leading zero hex digits fall under `ADDR_LIKE_MIN = 2**120`, so code does not treat them as addresses. Such an address can be mined in hours, so `transferOwnership(vanity)` goes to the model. | `r3_53` | Lower the bound to about 2**64, or treat any word that has code at the pinned block as an address. |
| 11 | Medium | Symbol spoofing. Any contract whose `symbol()` is a word in the proposal ("router", "grant") counts as named, both as call target and as argument. | `r3_54` | Accept a symbol match only for tokens the execution actually moves. |
| 12 | Medium | Any Snapshot space can list any Safe, because Snapshot does not verify treasury entries. `evil.eth` lists a real DAO's Safe, claims the listing and files that Safe's executions against its own proposals. | `r3_62` | When listing, require one of the Safe's owners (`getOwners()` at the pinned block) to be a space admin. |
| 13 | Medium | The DAO can switch checks off. If its space drops the Safe from its treasuries (one settings edit), every new filing is refused, even for executions made while it was listed. The pledge can then leave freely. | `r3_63` | Bind filings to the listing (Safe and space at listing time), not to the current setting. `a32` changes with this fix. |
| 14 | Medium | The pledge can leave before a late execution can be checked. Canonical withdrawal delay is 1 h. An execution made a minute before the unlock is not final on Ethereum yet (about 13 min), so nothing can be filed. The withdrawal goes through and the later DEVIATES slashes 0. | `r3_65` | Allow `execute_withdrawal` only after `withdraw_at + judge_s`, still counting executions up to `withdraw_at`. |
| 15 | Medium | The canonical contest window is 1 h. Every canonical listing is an unclaimed real DAO, which cannot notice a filing, find the right proposal and appeal in an hour. | `r3_68` | 72 h canonical. |
| 16 | Low | Quoted calldata is accepted on any mentioned contract. A quoted 100 COW transfer, sent byte-for-byte to USDC (6 decimals), is "exact calldata" for 10^14 USDC. | `r3_55` | The quoted blob must sit next to the target's address. Otherwise treat it as a normal value leg. |
| 17 | Low | `_blocking` scans only the newest 500 checks. After the unlock, the DAO files 500 checks of fresh executions (non-blocking, stakes refundable) and the old blocking check drops out of view. | `r3_66` | Keep a per-DAO counter of open checks with `exec_time <= withdraw_at` instead of scanning. |
| 18 | Low | Standing goes by when a ruling became final, not when the execution ran. A 2-year-old execution ruled today makes a DAO "not executing as voted" for 30 days. By this rule the canonical cow.eth and safe.eth listings fail `is_executing_as_voted` for the 30 days after their 2023/2024 seeds became final. | `r3_67` | Set `last_deviates_at = exec_time`. |
| 19 | Low | README says the contracts were deployed from `790d695`. ADDRESSES.md and ATTACK_REPORT say `93d5be9`, and `790d695` is superseded. | `r3_69` | Fix README line 9. |

## Docs that don't match the code

- README "Recipient not mentioned anywhere → NOT_AUTHORIZED" and "Decodes every action": wrong for ETH sent with a token call (#1) and for `transferFrom`'s `from` (#9).
- README "A call that passes an address-like argument the proposal does not mention → NOT_AUTHORIZED": wrong for nested, vanity and symbol-named addresses (#4, #10, #11).
- README "the DAO's pledge is never touched by a pairing that an appeal corrects": a stranger's appeal can create the wrong pairing, and nobody can appeal it (#2). SUBMISSION step 4 says only a DEVIATES ruling can name another proposal; the code lets either side do it.
- FINAL_CHECK "Nobody acts for a DAO they don't control: listings proven by the space's own treasury setting": a treasury setting proves nothing about who controls the Safe (#12).
- README "Known limitations: These cannot be fixed inside this design": several are cheap to fix (below).
- README test command and ATTACK_REPORT ("Two rounds") leave out round 3. On `0b1281a`, the "standing mandate" limitation is out of date, because "per month" is now handled.
- medium.md: "the SafeDAO Safe passed an address that no SafeDAO proposal mentions". The evidence is an address-only search of Snapshot (SEEDS says so). Say "no SafeDAO Snapshot proposal writes out".
- Verdict sentences: no accusing words found (README, SEEDS, SUBMISSION, medium, video captions, site).

## What held up

CID hashing and the hub cross-check. Recursive MultiSend decoding with an allowlist; look-alike MultiSends become DELEGATECALL. DELEGATECALL inside a batch. Binding to the Safe tx hash and `ExecutionSuccess`; `ExecutionFailure` and failed outer txs are refused. Module and relayer executions are refused, not misread. Execution before the vote ended: refused. A proposal from another space: refused. Unsupported voting types: UNCLEAR. Duplicate filing of the same execution. No state written before a revert (scan). The ledger invariant held after every one of my money scenarios (`r3_60`, `r3_64`, `r3_65`). Gas refunds to tx.origin are counted.

## Known limitations that are cheap to fix

- **Treasury listing as current setting**: bind filings to the listing (#13). Prove control with `getOwners()` ∩ space admins (#12). Both are one eth_call or one field.
- **One Safe under several spaces**: the same owner-admin proof stops rogue listings.
- **ENS on non-Ethereum spaces**: on OP-stack chains, the L1Block predeploy (`0x4200…0015`, `number()`) at the snapshot block gives the Ethereum block. Arbitrum blocks carry `l1BlockNumber`. One extra call. Resolving at the execution block also fixes #8.
- **Relayed executions**: on L2 chains Safes are SafeL2, which emits `SafeMultiSigTransaction` with every parameter. A relayed execution can be decoded from that log and bound to `ExecutionSuccess`. Module executions are still not cheap: they need a decoder per module.
- **Dollars paid in ETH/WETH**: read the Chainlink ETH/USD aggregator at the pinned block from both RPCs. Long-tail tokens stay UNCLEAR.
- **Choosing the proposal is the filer's claim**: the appeal path is the defence. Restrict `alt_vote_id` (#2) and lengthen the window (#15).
- Not cheap, as stated: hub scores, model judgment of words, RPC availability, Studio Dev transfers, the demo seam.
