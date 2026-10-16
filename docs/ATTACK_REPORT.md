# Attack report

Three rounds, written as an outsider trying to get a wrong verdict, move money that should not move, or make the registry say something false. Every attack is a test that runs offline against the same contract files that are deployed (`test/test_attacks.py`, `test/test_attacks_r2.py`, `test/test_attacks_r3.py`).

```
cd test && python3 -m unittest -q test_attacks test_attacks_r2 test_attacks_r3
```

Round 1 was run against the first full deployment (commit `790d695`, all nine contracts, seeding started). Four of its tests failed on that code ([first run](research/attacks_r1_first_run.txt)). Round 2 attacked only the round-1 fixes; one of its tests failed ([first run](research/attacks_r2_first_run.txt)). All findings were fixed in commit `93d5be9`, which is what is deployed now; the `790d695` deployment and its partial seed run are recorded as superseded in `deployments.json` and `docs/superseded/`.

## Findings and fixes

| # | Severity | Attack | What happened on `790d695` | Fix (`93d5be9`) | Test |
|---|---|---|---|---|---|
| H1 | High | **Borrow another recipient's amount.** Proposal: "Send 100,000 USDC to Bob… Alice helps with coordination." Execution: 90,000 USDC to Alice. | AS_VOTED. Alice's line and paragraph state no amount, so the cap ladder climbed to the section and took Bob's 100,000. | Every amount now belongs to the addresses its own line names (or, if none, its paragraph). An amount owned by other addresses is never used as this recipient's cap, at any level. | `a13`, `r2_01`–`r2_04` |
| M1 | Medium | **Lock a pledge forever.** Keep one check of the DAO open at all times (each costs a stake that UNCLEAR refunds). | `request_withdrawal` and `execute_withdrawal` refused whenever any check of the DAO was open, so a pledge could be held hostage indefinitely. | A request is always accepted. Execution is blocked only by open checks of executions made **before the unlock time**; a check of a later execution does not hold the pledge. | `a57`, `a58` |
| M1b | Medium (round 2, in the M1 fix) | **Request, misbehave, leave.** Request a withdrawal, execute something off-proposal during the delay, then withdraw before anyone can finish the check. | The first M1 fix used the *request* time as the cut-off, so the misbehaving execution (after the request) did not block. | The cut-off is the unlock time (`withdraw_at`), so the whole delay is covered. Every blocking check still has its own deadline exit. | `r2_10`, `r2_11`, `r2_13` |
| L1 | Low | **Put accusing words in the verdict sentence** through a choice label ("The signers committed fraud"). | The UNCLEAR summary for an uncomputable vote quoted the winning label. | That sentence is now fixed text; no proposal or label text ever enters a verdict sentence. | `a63`, `r2_20` |

Fixes found while preparing seeds (before the first deployment, recorded for completeness): USD-only figures paid in a volatile token were OVER_AMOUNT and are now UNCLEAR (no prices); addresses embedded in quoted calldata were not counted as mentioned and now are, and an action whose exact calldata the proposal quotes is authorized by code; a call into another Safe's `execTransaction` treated the owner addresses inside its signatures as arguments and no longer does; transfers to one recipient are now summed across executions checked under the same proposal.

## Round 3: the code-first matching

Round 3 attacked only how code reads amounts and addresses out of the proposal: amounts and addresses on different lines, tables, bullet lists, "up to" / "max" / "per month", one address named for two purposes, ENS and hex for one recipient, number formats, tokens of different decimals, payments split across many transactions, approve against transfer, and an address that appears only inside a link. 33 tests; 17 failed on the deployed code ([first run](research/attacks_r3_first_run.txt)). The fixes are in `0b1281a`. Running the new code offline on the 15 real seeds and the 7 demo checks changes none of their rulings.

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
