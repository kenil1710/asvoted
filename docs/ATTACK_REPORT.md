# Attack report

Four rounds, written as an outsider trying to get a wrong verdict, move money that should not move, or make the registry say something false. Every attack is a test that runs offline against the same contract files that are deployed (`test/test_attacks.py`, `test/test_attacks_r2.py`, `test/test_attacks_r3.py`).

```
cd test && python3 -m unittest -q test_attacks test_attacks_r2 test_attacks_r3 test_attacks_r4
```

Round 1 was run against the first full deployment (commit `790d695`, all nine contracts, seeding started). Four of its tests failed on that code ([first run](research/attacks_r1_first_run.txt)). Round 2 attacked only the round-1 fixes; one of its tests failed ([first run](research/attacks_r2_first_run.txt)). All findings were fixed in commit `93d5be9`, which is what is deployed now; the `790d695` deployment and its partial seed run are recorded as superseded in `deployments.json` and `docs/superseded/`.

Round 4 attacked the round-3 fixes; its report, with the commit that fixed each finding, is [ATTACK_REPORT_R4.md](ATTACK_REPORT_R4.md).

## Findings and fixes

| # | Severity | Attack | What happened on `790d695` | Fix (`93d5be9`) | Test |
|---|---|---|---|---|---|
| H1 | High | **Borrow another recipient's amount.** Proposal: "Send 100,000 USDC to Bob… Alice helps with coordination." Execution: 90,000 USDC to Alice. | AS_VOTED. Alice's line and paragraph state no amount, so the cap ladder climbed to the section and took Bob's 100,000. | Every amount now belongs to the addresses its own line names (or, if none, its paragraph). An amount owned by other addresses is never used as this recipient's cap, at any level. | `a13`, `r2_01`–`r2_04` |
| M1 | Medium | **Lock a pledge forever.** Keep one check of the DAO open at all times (each costs a stake that UNCLEAR refunds). | `request_withdrawal` and `execute_withdrawal` refused whenever any check of the DAO was open, so a pledge could be held hostage indefinitely. | A request is always accepted. Execution is blocked only by open checks of executions made **before the unlock time**; a check of a later execution does not hold the pledge. | `a57`, `a58` |
| M1b | Medium (round 2, in the M1 fix) | **Request, misbehave, leave.** Request a withdrawal, execute something off-proposal during the delay, then withdraw before anyone can finish the check. | The first M1 fix used the *request* time as the cut-off, so the misbehaving execution (after the request) did not block. | The cut-off is the unlock time (`withdraw_at`), so the whole delay is covered. Every blocking check still has its own deadline exit. | `r2_10`, `r2_11`, `r2_13` |
| L1 | Low | **Put accusing words in the verdict sentence** through a choice label ("The signers committed fraud"). | The UNCLEAR summary for an uncomputable vote quoted the winning label. | That sentence is now fixed text; no proposal or label text ever enters a verdict sentence. | `a63`, `r2_20` |

Fixes found while preparing seeds (before the first deployment, recorded for completeness): USD-only figures paid in a volatile token were OVER_AMOUNT and are now UNCLEAR (no prices); addresses embedded in quoted calldata were not counted as mentioned and now are, and an action whose exact calldata the proposal quotes is authorized by code; a call into another Safe's `execTransaction` treated the owner addresses inside its signatures as arguments and no longer does; transfers to one recipient are now summed across executions checked under the same proposal.

## Round 3: the code-first matching

Round 3 attacked only how code reads amounts and addresses out of the proposal: amounts and addresses on different lines, tables, bullet lists, "up to" / "max" / "per month", one address named for two purposes, ENS and hex for one recipient, number formats, tokens of different decimals, payments split across many transactions, approve against transfer, and an address that appears only inside a link. 30 tests at first (33 with three added while fixing); 17 failed on the deployed code ([first run](research/attacks_r3_first_run.txt)). The fixes are in `0b1281a`; the second pass below is deployed from `7a74665`. Running the new code offline on the 15 real seeds and the 7 demo checks changes none of their rulings.

| # | Severity | Attack | What happened on `93d5be9` | Fix | Test |
|---|---|---|---|---|---|
| H2 | High | **Bullet list, amount on its own line.** `- Alice: 0xA… / Amount: 1,000 USDC / - Bob: 0xB… / Amount: 9,000 USDC`; Alice gets 9,000. | AS_VOTED. The amount lines name no address, so both amounts belonged to the whole paragraph, Alice included. | An amount belongs to the address of its list item (marker line to the next marker at that indent). | `r3_01`, `r3_02` |
| H3 | High | **Table with addresses in the header** and amounts in the row below; Alice takes Bob's column. | AS_VOTED, same cause. | An amount in a table row belongs to the address in the same column above it. | `r3_03` |
| H4 | High | **Key/value block naming two recipients** (`Amount… To: A… Amount… To: B…`). | AS_VOTED with the larger amount. | When a paragraph names several addresses and nothing ties the amount to one, a within-cap result is UNCLEAR. | `r3_04` |
| H5 | High | **One amount, two recipients.** "Send 10,000 USDC to A and B"; each gets 10,000. | AS_VOTED for 20,000. | One amount on a line with several addresses covers them together unless the amount says "each" (the word right after it, or "each receive"). "each of whom signs" does not count. | `r3_05`, `r3_06`, `r3_06b` |
| H6 | High | **Push real payments out of view.** File nine dust executions under the proposal, then two full payments. | Both full payments AS_VOTED: a judgment read only the 8 oldest earlier executions. | A judgment reads up to 24 and is told when there are more. A within-cap result is then UNCLEAR. | `r3_31` |
| H7 | High | **Approve and transfer to one address.** Proposal: 5,000 USDC; execution approves 5,000 and transfers 5,000. | AS_VOTED: approvals and transfers were capped separately. | Finite approvals and transfers to one address add up against its cap. | `r3_32`, `r3_33` |
| H8 | High | **Hidden HTML comment** `<!-- 0xMallory 9,000 USDC -->`, invisible on Snapshot. | AS_VOTED for a payment to Mallory. | HTML comments are blanked before anything is read, for code and for the model's quotes. | `r3_40`, `r3_41` |
| H9 | High | **A number inside a link target** (`…?q=9000 USDC`) used as the cap. | AS_VOTED for 9,000. | Link targets can still name an address but never carry an amount; numbers after `=`, `?`, `&` are not amounts. | `r3_42`, `r3_43` |
| M2 | Medium | **"Per month" summed forever.** "1,000 USDC per month", paid in August and September. | September ruled DEVIATES (wrong slash). | Calendar periods (day, week, month, quarter, year, UTC) reset the running total; "for N months" caps the overall total; a period code can't date ("per epoch") makes later over-total payments UNCLEAR. A period word more than a few words from the amount is ignored. | `r3_12`–`r3_14`, `r3_12b`, `r3_12c` |
| M3 | Medium | **A minimum read as a cap.** "at least 1,000 USDC"; 1,000,000 paid. | DEVIATES. | Minimums are not caps; with nothing else stated the action is UNCLEAR. | `r3_10` |
| M4 | Medium | **One address, two purposes** (5,000 audit + 3,000 travel; 8,000 paid). | DEVIATES. | Above the largest stated amount but within the sum of the amounts stated for that address alone: UNCLEAR. Above the sum is still over. | `r3_07` |
| M5 | Medium | **"50,000 USDC worth of COW"**, paid in COW. | DEVIATES (read as the wrong token). | A stablecoin figure followed by "worth", "equivalent", "valued" or "denominated" is a valuation: UNCLEAR, as for "$". A plainly stated other token is still OVER. | `r3_15` |
| M6 | Medium | **Space-grouped thousands** "1 000 000 USDC". | DEVIATES: read as "000 USDC", a cap of 0. | Groups after spaces (two or more), no-break or thin spaces are thousands. A single plain-space group ("5 000") is no amount. | `r3_22`, `r3_23` |
| L2 | Low | **Dot-grouped thousands** "1.000.000 USDC", "1.250.000,50 USDC". | UNCLEAR: no amount read. | Two dot groups, or dot groups with a decimal comma, are thousands. One group ("50.000") is still the smaller reading. | `r3_20`, `r3_21`, `r3_24` |

A second attacker attacked the same deployed code in parallel: decoding, binding, pairing, money and docs. Their full report with each attack is [ATTACK_REPORT_R3.md](ATTACK_REPORT_R3.md); 20 tests, `r3_50`–`r3_69`, all failing on `93d5be9`. Fixed in `b733e9e`:

| # | Severity | Finding | Fix | Test |
|---|---|---|---|---|
| 1 | High | ETH attached to a token call was not counted | Native value on any action is a value leg to its target | `r3_50` |
| 2 | High | A stranger appeals a correct AS_VOTED, names an unrelated proposal, gets a final DEVIATES and the bounty | Only an appeal of a DEVIATES ruling may name another proposal | `r3_64` |
| 3 | High | An expired check hid its payment from the cap | Every other filing under the proposal counts, whatever its outcome | `r3_60` |
| 4 | High | Address inside nested calldata (`multicall(bytes[])`) never checked | Full-width addresses 4 bytes off the grid are checked like arguments | `r3_52` |
| 5 | High | Largest number near the recipient was the cap ("from the 2,000,000 USDC treasury"; "request … rejected") | Several amounts on the cap's line: only the smallest authorizes, above it UNCLEAR; refused amounts are not caps | `r3_57`, `r3_58` |
| 6 | High | The losing option set the cap | A vote with several approving options: within-cap is UNCLEAR | `r3_59` |
| 7 | High | Two recipients, two amounts on one line | Fixed in `0b1281a` (UNCLEAR) | `r3_56` |
| 8 | Medium | Recipient repoints an ENS name and turns a correct payment into DEVIATES | Names on Ethereum spaces resolve at the vote's snapshot block only | `r3_61` |
| 9 | Medium | `transferFrom`'s source never checked | Source must be the Safe or mentioned | `r3_51` |
| 10 | Medium | Vanity addresses below 2^120 not treated as addresses | Bound lowered to 2^96 | `r3_53` |
| 11 | Medium | Any contract whose `symbol()` is a word of the proposal counts as named | Symbol matches need a token-like symbol (2+ capitals) in its exact case | `r3_54` |
| 12 | Medium | Any space can list any Safe | **By design**, kept: a rogue listing is its own record and can't touch the real one (README, Known limitations) | `r3_62` (rewritten to pin that) |
| 13 | Medium | The DAO switches checks off by dropping the Safe from its settings | Filings are bound to the listing | `r3_63`, `a32` |
| 14 | Medium | Pledge leaves before a late execution can be filed | Withdrawals wait a late window after the unlock (6 h canonical) | `r3_65` |
| 15 | Medium | 1 h canonical contest window | 72 h | `r3_68` |
| 16 | Low | Quoted calldata accepted on any mentioned contract | The quote's own paragraph must name the target | `r3_55` |
| 17 | Low | Newer checks push a blocking check out of the 500-check scan | A counter set at the request and moved by every filing and closing | `r3_66` |
| 18 | Low | Standing dated by the ruling, not the execution | `last_deviates_at` is the execution time | `r3_67` |
| 19 | Low | README named the superseded commit | Fixed | `r3_69` |

Two test changes follow from the fixes, not from relaxing them. `r3_65` now expects the early withdrawal to be refused, then the slash to land. `r3_62` pins the by-design behavior. Tests that waited only the old withdrawal delay now also wait the late window. All 171 tests pass. Running the new code offline on the 15 real seeds and 7 demo checks changes no ruling.

### Second pass: the required design

The fixes above were then replaced or tightened to a fixed design, and redeployed from `7a74665` (the `829e156` deployment and its stopped run are in `docs/superseded/829e156/`):

| Finding | Design | Change | Tests |
|---|---|---|---|
| ETH with a token call (H, #1) | Every call's native value is its own transfer to the call's target, whatever the calldata, in caps and recipient checks | unchanged from `b733e9e` | `r3_50` |
| Weaponised appeals (H, #2) | Only the DAO may switch the proposal; any DEVIATES produced on appeal opens a DAO response window before FINAL | Only the listing's controller, answering a DEVIATES, may name another proposal (unclaimed listings: nobody). An appeal that turns AS_VOTED into DEVIATES puts the check back to CONTESTABLE for the DAO side only (round 2). Bonds settle three ways | `r3_64`, `r3_70`–`r3_74` |
| Caps from records (H, #3) | Earlier payments counted whatever the outcome; an expired check can be refiled | Every other filing counts; a check that expired unjudged no longer blocks refiling the same pair | `r3_60`, `r3_75` |
| Nested calldata (H, #4) | Any unnamed address in sub-calls (recursive, depth limit) blocks AS_VOTED: UNCLEAR unless code proves a NOT_AUTHORIZED payment | Full-width addresses at 4, 8 and 12 bytes off the grid (three levels) → UNCLEAR. Top-level address arguments keep the stricter, code-settled NOT_AUTHORIZED | `r3_52` (assertion now UNCLEAR), `r3_83` |
| Ambiguous caps (H, #5, #7) | A cap only in the recipient's own line / bullet / table row with no other amount for that token; negation or more than one candidate → UNCLEAR | The paragraph, section and document levels are gone. Negation is per sentence ("rejected", "not", "instead of", "rather than", "will not") | `r3_01`–`r3_09`, `r3_56`–`r3_58`; `r2_01`, `r2_03`, `r3_03`, `r3_07` changed to UNCLEAR (below) |
| Losing option (H, #6) | Only the winning choice's text and choice-independent text count; ambiguous → UNCLEAR | Paragraphs or sections that begin with a losing choice's name are dropped; if the winner's text is not found, nothing caps | `r3_59`, `r3_76`, `r3_77` |
| ENS repointing (M, #8) | Resolved at the execution block, never later | `VoteReader.read_names_at(vote, l1_block)`, snapshotted at filing. ExecReader records each execution's Ethereum block (the block; OP-stack L1 attributes deposit; Arbitrum `l1BlockNumber`). A name counts only if it also matches the vote's snapshot (keeps `a21`) | `r3_61`, `a20`–`a22`, `r3_80` |
| `transferFrom` source (M, #9) | Must be the Safe or named | unchanged from `b733e9e` | `r3_51` |
| Vanity addresses (M, #10) | Leading zeros recognised | 2^96 bound | `r3_53` |
| Symbol spoofing (M, #11) | Tokens by address (named, or a fixed token list), never by `symbol()` alone | Judge constructor takes a token list (`test/token_list.json`, symbols read on chain); other tokens need their address in the proposal, else UNCLEAR | `r3_54`, `r3_78`, `r3_79` |
| Rogue listings (M, #12) | DAO = (space, Safe); standing keyed by the pair; the UI shows the space; a verified badge | `is_executing_as_voted_for(space, chain, safe)`; VoteReader reads the space's ENS owner (NameWrapper aware) and the Safe's owners; `verified` on the listing | `r3_62`, `r3_81`, `r3_82` |
| Treasury removed later (M, #13) | Listing snapshotted at registration | unchanged from `b733e9e` | `r3_63`, `a32` |
| Pledge leaves early (M, #14) | Delay covers filing + contest for earlier executions | Canonical: 6 h delay + 6 h filing window; demo 90 s + 120 s; blocking counter | `r3_65`, `r3_66` |
| Contest window (M, #15) | 6 h canonical, demo 90 s | 6 h | `r3_68` (assertion now ≥ 6 h) |
| Standing (L, #18) | From the execution time | unchanged from `b733e9e` | `r3_67` |
| Relayed executions (Known limitation) | cheap | SafeL2 `SafeMultiSigTransaction` log decoded, nonce checked, bound to `ExecutionSuccess` | `r3_84`, `r3_85` |

Assertions changed, and why:
- **`r2_01`, `r2_03`** (amount on the next line; a section budget): AS_VOTED → UNCLEAR. Under the required design a cap must sit on the recipient's own line, bullet or row.
- **`r3_03`** (table, header addresses, amounts below): DEVIATES / AS_VOTED → UNCLEAR for both. A column below a header is not the recipient's own row, so the attack is still never AS_VOTED.
- **`r3_07`** (one address, two amounts): UNCLEAR / DEVIATES / AS_VOTED → UNCLEAR for all three. Two candidates means no cap.
- **`r3_52`**: NOT_AUTHORIZED → UNCLEAR. That is the design for nested calldata.
- **`r3_68`**: ≥ 24 h → ≥ 6 h. That is the design.
- **`test_ens_resolved_as_at_the_vote`** now resolves as of the execution.
- **`test_windows_and_no_seam`** expects 6 h.

187 tests pass.

Controls that already held: "up to" and "max" are caps (`r3_11`), suffixes k / M / million and decimals (`r3_25`), USDC and DAI at different decimals add up (`r3_26`), twenty legs in one batch are summed (`r3_30`), ENS and hex for one recipient are one recipient (`r3_08`, `r3_09`).

## Attacks the contracts already resisted

| Area | Attack | Result | Test |
|---|---|---|---|
| Batches | MultiSend nested inside MultiSend hides a payment | every inner call decoded, unnamed one is NOT_AUTHORIZED | `a01` |
| | Nest deeper than the decoder goes, so the tail is skipped | refused (`TOO_DEEP`), never truncated | `a02` |
| | A look-alike MultiSend address one hex digit off | not decoded as a batch; DELEGATECALL, CRITICAL | `a03` |
| | DELEGATECALL tucked inside an otherwise named batch | that action NOT_AUTHORIZED, severity CRITICAL | `a04` |
| | Pay a relayer through the gas refund | refund is an action; unnamed recipient → DEVIATES | `a05` |
| Amounts | Recipient paid in a different token than stated | OVER_AMOUNT | `a10` |
| | Six transfers of 10,000 against a 50,000 cap | summed → OVER_AMOUNT | `a11` |
| | Two executions of 30,000 against one 50,000 proposal | second check DEVIATES (prior execution summed) | `a12` |
| | Truncated address `0xabcd…1234` in the text | not a mention | `a14` |
| ENS | Cyrillic homoglyph of a resolvable name | not resolved, not a mention | `a20` |
| | Name repointed to the attacker after the vote | resolutions differ → name ignored → DEVIATES | `a21` |
| | `pay.alice.eth` vs `alice.eth` | the subdomain does not count as its parent | `a22` |
| Votes | Gateway serves other bytes for the CID | refused, bytes hashed in the contract | `a30` |
| | Proposal from a look-alike space that lists the Safe | refused for this DAO's listing | `a31` |
| | Safe removed from the space's treasuries | filing refused | `a32` |
| | Listed only on another chain | listing refused | `a33` |
| | Executed before the vote ended | filing refused | `a34` |
| | Hub returns two rows / a swapped voting type | refused | `a35`, `a36` |
| | Leader names an old block | validators reject; nothing written | `test_asvoted` `test_leader_naming_an_old_block_is_rejected` |
| | The two RPCs answer differently | refused (`RPC_DISAGREE`) | `test_asvoted` `test_rpc_disagreement_refused` |
| Filing | Second proposal claims the same execution | `DUPLICATE_OF_CHECK` | `a40` |
| | Execution of another Safe filed for this DAO | refused | `a41` |
| | Refused filing keeps the stake | credited back to the sender | `a42` |
| | A fake registry feeds the judge evidence | judgment keyed to the fake registry; the real one never sees it | `a43` |
| Appeals / money | Second appeal, stranger appealing for a claimed DAO, controller appealing its own AS_VOTED | refused | `a50`–`a52` |
| | Top up after a DEVIATES ruling to shrink the slash, or withdraw to dodge it | slash uses the pledge at filing; withdrawal blocked | `a53`–`a55`, `r2_13` |
| | Claim twice | second claim refused | `a56` |
| Model | Prompt injection in the proposal text | code-settled actions never reach the model; wording is fixed text | `a60`, `a61` |
| | Quote that is not in the proposal | UNCLEAR | `a62` |
| | Model answers disagree / validator disagrees | UNCLEAR / transaction undetermined, nothing written | `test_asvoted` `test_model_samples_disagreeing_is_unclear`, `test_validator_disagreement_writes_nothing` |
| Writes | Counter or state changed before a check that can revert | none in any write method of any contract | `tools/scan_writes.py` |

## What remains

These are in the README's Known limitations, each marked as either impossible on Studio Dev or a deliberate choice, with the reason.
