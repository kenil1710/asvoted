# Attack report

Two rounds, written as an outsider trying to get a wrong verdict, move money that should not move, or make the registry say something false. Every attack is a test that runs offline against the same contract files that are deployed (`test/test_attacks.py`, `test/test_attacks_r2.py`).

```
cd test && python3 -m unittest -q test_attacks test_attacks_r2
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

These are listed in the README's Known limitations with the reason: scores come from the hub; the treasury listing is the hub's current setting; module executions are not read; calls described only in words depend on the model (behind quote checks, two answers, a fresh panel); dollar figures for volatile tokens are UNCLEAR; standing mandates with a per-payment figure rule later payments over the cap; the proposal a check is filed against is the filer's claim, corrected by appeal; a determined filer can keep a pledge from leaving for as long as checks of executions made before the unlock time stay open (each has a deadline and anyone can close it).
