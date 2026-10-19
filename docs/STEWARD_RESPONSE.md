# Response to the steward's requested changes

All code links are pinned to commit [`b836f41`](https://github.com/kenil1710/asvoted/tree/b836f418da32f8bd1b2bb0e218a6512d35275cbb), the commit every contract was deployed from.

Test commands: `python3 -m unittest discover -s test` (contracts, offline harness) and `cd frontend && npm test` (patrol, mocked registry and chains).

## 1. Patrol recovery

**What changed.** The fixed 3 h lookback is gone. The patrol keeps a durable state document with:

- a checkpoint per Safe and chain (the last block scanned in full);
- the executions it has processed, keyed by `(chain, safe, safeTxHash)`;
- a persistent retry queue with attempt counts and backoff;
- the unmatched executions.

Each run resumes from the checkpoint and scans at most a fixed span per chain, up to the finalized head (`LIMITS.maxSpan`; the first run backfills `initialBackfill`). Before filing, the patrol checks the registry (`get_check_id_by_tx`), so an execution is never filed twice. The checkpoint advances only after every event in the span has been processed or queued. A log range that cannot be read holds the checkpoint at the last range read in full.

**Where the state lives, and why.** The state is `patrol-state.json` on a dedicated `patrol-state` branch. The GitHub Action checks the branch out, POSTs the state to the patrol endpoint, and commits what the run returns. The reasons for this choice:

- the job needs no other storage service or credentials;
- every change is a commit, so the history can be audited;
- the `concurrency: patrol` group guarantees a single writer;
- the site reads the same file for its Unmatched executions page.

The state is bound to its registry, so a redeployment starts a fresh scan.

**Commits.** [`1354e1c`](https://github.com/kenil1710/asvoted/commit/1354e1c675aa1d5674b2fbad3a6a799b4cfc13f3), plus timing and endpoints in [`e98eee6`](https://github.com/kenil1710/asvoted/commit/e98eee6192a453cff3c4f7a9c76a40b4b00a9d4d).

**Files.**

- [frontend/src/lib/patrol/state.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/patrol/state.ts)
- [frontend/src/lib/patrol/core.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/patrol/core.ts)
- [frontend/src/lib/patrol.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/patrol.ts)
- [.github/workflows/patrol.yml](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/.github/workflows/patrol.yml)
- [frontend/src/app/api/patrol/route.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/app/api/patrol/route.ts)
- [frontend/scripts/patrol-run.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/scripts/patrol-run.ts)

**Tests.** In [frontend/test/recovery.test.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/test/recovery.test.ts):

- first run starts at the initial backfill and scans at most maxSpan blocks
- backfill resumes from the checkpoint each run until the finalized head, with no gap or overlap
- nothing past the finalized block is scanned; it is picked up once finalized
- an RPC outage holds the checkpoint at the last range read in full; the next run resumes there
- a total outage (finalized head unreadable) leaves every checkpoint where it was
- idempotent: an execution already on the registry is recorded, never filed
- idempotent: re-scanning a span (checkpoint lost) never files the same execution twice
- a failure goes to the persistent retry queue with an attempt count and backoff; the checkpoint still advances
- a failed write is queued, and the retry resumes the pipeline without repeating finished steps
- out of write budget: the rest of the span is deferred (attempts 0), the checkpoint advances, later runs file each once
- an unmatched execution is recorded visibly and never retried or filed
- a malformed state document loads as empty rather than failing the run

## 2. Pagination

**What changed.**

- `get_daos` now returns `next_offset` and `done`, like `get_open_checks`.
- The patrol and the site follow every page of both. That includes the registry's per-call scan cap of 500 rows: a page can be empty and still not `done`.
- The patrol keeps continuation cursors (`cursors.daos` and `cursors.open_checks`) in its state. A run bounded by time or writes resumes where the previous one stopped and wraps around, so every DAO and every open check is reached.

**Commit.** [`9ae5a26`](https://github.com/kenil1710/asvoted/commit/9ae5a26b45442c09e54b1437c4b37f2abe545b17)

**Files.**

- [contracts/AsVotedRegistry.py](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/contracts/AsVotedRegistry.py) (`get_daos`, `get_open_checks`)
- [frontend/src/lib/patrol/core.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/patrol/core.ts)
- [frontend/src/lib/contract.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/contract.ts) (`getAllDaos`)
- [frontend/test/mock.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/test/mock.ts): a mocked registry with the same 50-row page and 500-row scan cap

**Tests.** In [frontend/test/pagination.test.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/test/pagination.test.ts):

- more than 50 DAOs: every page of get_daos is read and every Safe is scanned and filed
- more than 50 DAOs over time-bounded runs: the round-robin cursor reaches every DAO, none skipped, none twice
- more than 500 historical checks: get_open_checks is followed past the scan cap, through empty pages, to done
- more than 500 historical checks and more than 50 open: pages of 50 are followed too
- open checks over write-bounded runs: the cursor carries over and every check is closed exactly once
- a run that starts mid-list wraps around to the checks before its cursor
- other filers' open checks are read but never touched

In [test/test_steward.py](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/test/test_steward.py), class `TestPagination`:

- `test_open_checks_cursor_crosses_the_scan_cap_and_misses_nothing`
- `test_open_checks_pages_of_fifty`
- `test_get_daos_pages_past_fifty`

## 3. Round-2 deadline

**What changed.**

- Every row of `get_open_checks()` now carries `round`, `resp_deadline` and `active_deadline`, and `get_check` carries `active_deadline`.
- `active_deadline` is `appeal_deadline` in round 1 and `resp_deadline` in round 2.
- The patrol judges, rules and expires a check by the active deadline (`activeDeadline` in core.ts). A DAO's response is therefore never expired against the original appeal deadline.

**Commit.** [`56cf0a3`](https://github.com/kenil1710/asvoted/commit/56cf0a3d9d4b2b965f9a1044541ec277f1c63673)

**Files.**

- [contracts/AsVotedRegistry.py](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/contracts/AsVotedRegistry.py) (`_active_deadline`, `get_open_checks`)
- [frontend/src/lib/patrol/core.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/patrol/core.ts)

**Tests.**

End to end on the contracts, adversarial (adverse appeal, DAO response, the original appeal_deadline passes, the response is judged and settled, no premature expire). In [test/test_steward.py](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/test/test_steward.py), class `TestRoundTwoDeadline`:

- `test_open_checks_expose_the_round_and_the_active_deadline`
- `test_response_judged_and_settled_after_the_original_appeal_deadline_no_premature_expire`
- `test_response_unjudged_expires_only_after_its_own_deadline`

Patrol side, in [frontend/test/round2.test.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/test/round2.test.ts):

- activeDeadline: round 2 uses resp_deadline, round 1 appeal_deadline
- the DAO's response is judged and ruled after the original appeal_deadline; no premature expire
- the response is expired only once resp_deadline has passed
- without active_deadline in the row (older registry), the patrol still uses resp_deadline in round 2

## 4. DAO standing

**What changed.** `DaoStanding` 2.0.0 returns a structured `state` with every failing reason. The states are checked in this order:

1. NO_COVERAGE: the DAO is unknown or unreadable.
2. DEVIATES: a final DEVIATES in the window.
3. PENDING: open checks.
4. NO_COVERAGE: no heartbeat from the configured monitor.
5. STALE_MONITORING: the heartbeat is older than `stale_s`.
6. NO_COVERAGE: no final AS_VOTED in the window.
7. COMPLIANT: none of the above.

`is_executing_as_voted()` is true only for COMPLIANT, so absent data is never favourable. The registry has an on-chain coverage heartbeat, `record_coverage` and `get_coverage`, holding per DAO and reporter the last scanned block and its time. The patrol records it every run, held back to before any queued execution. `GrantGate` 2.0.0 grants only on COMPLIANT and records the state with each request.

**Commit.** [`944ccd5`](https://github.com/kenil1710/asvoted/commit/944ccd57fcb20f02124de109cff696d17a7a979e)

**Files.**

- [contracts/DaoStanding.py](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/contracts/DaoStanding.py)
- [contracts/GrantGate.py](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/contracts/GrantGate.py)
- [contracts/AsVotedRegistry.py](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/contracts/AsVotedRegistry.py) (`record_coverage`, `get_coverage`, `last_as_voted_at`)
- [frontend/src/components/DaoView.tsx](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/components/DaoView.tsx)

**Tests.**

[test/test_steward.py](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/test/test_steward.py), class `TestStandingStates`:

- `test_no_coverage_unlisted_dao`
- `test_no_coverage_listed_with_no_data_at_all`
- `test_no_coverage_heartbeat_but_nothing_verified`
- `test_no_coverage_as_voted_but_no_heartbeat`
- `test_only_the_monitors_heartbeat_counts`
- `test_pending_while_a_check_is_open`
- `test_pending_during_a_provisional_ruling`
- `test_deviates_final_in_window`
- `test_stale_monitoring`
- `test_compliant_grants`
- `test_as_voted_outside_the_window_is_no_coverage`
- `test_every_state_listed_in_config`

[test/test_steward.py](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/test/test_steward.py), class `TestCoverageHeartbeat`:

- `test_recorded_per_reporter_and_forward_only`
- `test_refusals`
- `test_one_bad_entry_writes_nothing`
- `test_dao_view_shows_last_as_voted`

[frontend/test/coverage.test.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/test/coverage.test.ts):

- after a scan the patrol records, per DAO, the checkpoint block and its timestamp
- during backfill the heartbeat covers only what has been scanned, with that block's own time
- a queued execution holds the heartbeat back to the block before it
- an unchanged heartbeat is not resent
- filings cannot use up the write held back for the heartbeat
- more than 50 DAOs: the heartbeat is split into calls of at most 50 entries

The live demo also shows every state on chain; see item 8.

## 5. Proposal discovery

**What changed.**

- **Candidates.** Every closed proposal of the space that ended before the execution, read from the hub newest first, in pages of 100, up to 10 pages. The report counts the proposals read.
- **Addresses.** Accepted all-lowercase, all-uppercase or EIP-55 checksummed, and compared lowercase. A mixed-case address with a wrong checksum is ignored and reported.
- **ENS names.** Normalized (ENSIP-15) and resolved on Ethereum.
- **Amounts.** Stated amounts such as "50,000 USDC", "1.5 ETH" or "12k DAI" are compared with the execution's transfers in the token's own decimals.
- **Matching.** A proposal that also states the moved amount is preferred, then the newest. MultiSend batches are unpacked.
- **Unmatched executions.** Recorded with their reason in the state file and shown on the site at [/unmatched](https://asvoted.vercel.app/unmatched), never retried or filed.

**Commit.** [`d5db6ed`](https://github.com/kenil1710/asvoted/commit/d5db6edfde60914dba98f7ca4f0b438113902a18)

**Files.**

- [frontend/src/lib/patrol/discover.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/patrol/discover.ts)
- [frontend/src/lib/patrol.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/patrol.ts) (`matchProposal`)
- [frontend/src/app/unmatched/page.tsx](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/app/unmatched/page.tsx)

**Tests.** In [frontend/test/discover.test.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/test/discover.test.ts):

- decodes a MultiSend batch into each call and transfer
- pagination: a match beyond the newest 25 (and beyond the first page) is found
- pagination is bounded: at most maxPages pages are read, and the report says how many
- normalization: a checksummed address in the text matches the lowercase execution; a bad checksum is ignored
- ENS names are normalized and resolved
- amounts are compared in the token's decimals; a proposal stating the moved amount is preferred over a newer one
- failed proposals are never candidates
- an unmatched execution is recorded in the state file with its reason, and the checkpoint moves on

## 6. Transaction lifecycle

**What changed.** ACCEPTED is never success. Every patrol write goes through `Lifecycle`:

1. Before sending, the expected state change is read. If it already holds, nothing is sent.
2. The hash is stored in `state.pending` as soon as it is known.
3. Success requires all of: FINALIZED, GenVM execution SUCCESS, no rollback, and the expected change read back from the contracts (check exists, judgment recorded, check moved, coverage recorded…).
4. FINALIZED with an error, UNDETERMINED and CANCELED are failures and go to the retry queue.
5. A transaction still in flight when the run ends stays pending. The next run follows the stored hash and never sends a second copy.
6. A stored hash the node does not know is reconciled against the chain. If the expected change is there, it landed. If there is no change after 30 minutes, it is lost and is sent again only after the same read-first check.

The test harness for the contracts also waits for FINALIZED.

**Commits.**

- [`e32b675`](https://github.com/kenil1710/asvoted/commit/e32b6753c3c753c75d647fbecc274f02a48d7a8f)
- [`969d3e0`](https://github.com/kenil1710/asvoted/commit/969d3e0e52ae7031096ab9f1b70de2f6f7f83989) (reconciliation)

**Files.**

- [frontend/src/lib/patrol/txlife.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/patrol/txlife.ts)
- [frontend/src/lib/patrol/core.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/patrol/core.ts)
- [frontend/src/lib/patrol.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/lib/patrol.ts) (`tx`, `submit`)
- [test/harness.mjs](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/test/harness.mjs)

**Tests.**

[frontend/test/txlife.test.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/test/txlife.test.ts):

- ACCEPTED is not success: a file_check still ACCEPTED at the end of the run is stored as pending, not counted as filed
- an uncertain transaction is resumed from its stored hash in the next run and never sent twice
- still in flight across several runs: followed each time, sent once
- FINALIZED with a GenVM error is a failure: retry queue with an attempt counted, nothing pending
- FINALIZED with a rollback is a failure
- FINALIZED and SUCCESS but the registry shows no check (a refused payable call) is a failure
- UNDETERMINED and CANCELED are failures
- a submit that fails leaves nothing pending and counts an attempt
- ACCEPTED then FINALIZED within the run: success only once FINALIZED and verified
- a hash lost with the state (run killed): the registry is read first, so the landed filing is not repeated
- an operation whose effect is already on chain is not sent
- closing writes are verified by reading the check back: a rule that moves nothing is not success

[frontend/test/reconcile.test.ts](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/test/reconcile.test.ts):

- a state built against another registry is set aside; the new registry is scanned and filed afresh
- the core refuses a state that names another registry
- a stored hash the node does not know, whose filing is on the registry, is reconciled as landed
- a stored hash the node does not know and no change on chain: lost after LOST_AFTER_S, then filed once
- processed records are bound to the registry, so a check missing from the registry is never assumed

## 7. Docs

**What changed.** README "Scope" and the site's [/docs](https://asvoted.vercel.app/docs) Scope section state:

- the IPFS CID proves the proposal text;
- final vote scores come from the Snapshot hub;
- Safe module executions are not supported;
- ambiguous instructions rule UNCLEAR;
- AsVoted verifies proposal-specific execution within declared coverage, not every DAO action.

`tools/final_check.mjs` checks each statement and the wording.

**Commit.** [`cc4cc76`](https://github.com/kenil1710/asvoted/commit/cc4cc7655081f83c243f90f80b3902f5e42efc6f)

**Files.**

- [README.md](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/README.md#scope)
- [frontend/src/app/docs/page.tsx](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/frontend/src/app/docs/page.tsx)
- [tools/final_check.mjs](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/tools/final_check.mjs)

**Test.** `final_check` section "README and docs: Scope" (see [docs/FINAL_CHECK.md](FINAL_CHECK.md)).

## 8. Tests, redeployment, seeds, demo, live patrol, final check

**Tests.** All 283 pass:

- 229 contract tests (`python3 -m unittest discover -s test`), including the new [test/test_steward.py](https://github.com/kenil1710/asvoted/blob/b836f418da32f8bd1b2bb0e218a6512d35275cbb/test/test_steward.py);
- 54 patrol tests (`cd frontend && npm test`) covering outages, backfill, pagination >50/>500, the round-2 response, finality and reconciliation.

**Redeployment.** All nine contracts were deployed from [`b836f41`](https://github.com/kenil1710/asvoted/commit/b836f418da32f8bd1b2bb0e218a6512d35275cbb):

- the canonical set in [`20cae29`](https://github.com/kenil1710/asvoted/commit/20cae29094a4073c27b9813106ccbf3768852be1);
- the demo set in [`3370ba0`](https://github.com/kenil1710/asvoted/commit/3370ba0), redeployed from the same commit after a first demo run judged past its 600 s windows (records in [docs/superseded/demo-9ce6CEAA](superseded/demo-9ce6CEAA/README.md)).

`node tools/verify_source.mjs` reports every address byte-identical to the file at `b836f41`.

| Contract | Address |
|---|---|
| ExecReader | `0x08E3E60e037af578D1c5f4189cDDd888ac497685` |
| VoteReader | `0xEb81fc7584fFf7f9414B52575c0151B1cE9b0bc7` |
| AsVotedJudge | `0x73fA37dc86005942AA1045a82CcF9e48eAA557F6` |
| AsVotedRegistry (canonical) | `0xc73438492c3F9604D99BfF7Aa268B7F77Aa3a9b1` |
| AsVotedRegistryDemo | `0x5AF1254384965e7E21ab37853Ee6385448331C50` |
| DaoStanding | `0x7B0B239181CAF8AFaa261f95E2344594d09d53A0` |
| DaoStandingDemo | `0x1dA328B19AbCaA8c30BA62c56D7e8775D7e0D380` |
| GrantGate | `0x638Ae4Cd8F0c62e373626E88F75490817bBD6877` |
| GrantGateDemo | `0xecEb8c215fe63Fe1eBeF09f4Fe236087E106C50B` |

**Seeds.** All 15 canonical seeds were re-filed (6 AS_VOTED, 2 DEVIATES, 7 UNCLEAR), commit [`5daec94`](https://github.com/kenil1710/asvoted/commit/5daec94d08a9c5aaca6692c78b66707f10e79ce8). Records: [docs/SEEDS.md](SEEDS.md) and [docs/seed-run.log](seed-run.log). The last 6 h contest window, check #14, ends at **2026-10-19T02:47:59Z**.

**Demo.** 35 of 35 expectations passed, commit [`d876262`](https://github.com/kenil1710/asvoted/commit/d876262), log in [docs/demo-run.log](demo-run.log). The run covered:

- every verdict, both appeals (won and lost), expiries, the duplicate and wrong-stake refusals;
- every DaoStanding state on chain: NO_COVERAGE, PENDING, DEVIATES, COMPLIANT (GrantGate carries out the request) and STALE_MONITORING;
- every payout, verified at its recipient by eth_getBalance;
- the demo registry's eth_getBalance ending at 0.

**Live patrol.** The patrol ran live against the new canonical registry (GitHub Actions runs [39173661292](https://github.com/kenil1710/asvoted/actions/runs/39173661292), [39174183673](https://github.com/kenil1710/asvoted/actions/runs/39174183673), [39174382564](https://github.com/kenil1710/asvoted/actions/runs/39174382564)):

- all 8 DAOs scanned from their checkpoints on Ethereum, Optimism and Base;
- `record_coverage` FINALIZED and read back;
- state committed to the [`patrol-state`](https://github.com/kenil1710/asvoted/tree/patrol-state) branch.

The first live run showed that Base's backfill range is not served by publicnode, and the checkpoint was correctly held. Log ranges are now split to each endpoint's limit with retries (commits [`3ce2967`](https://github.com/kenil1710/asvoted/commit/3ce2967), [`6876e85`](https://github.com/kenil1710/asvoted/commit/6876e85)), and the last run read every span.

**Old records.** The ab42d5c records are in [docs/superseded/ab42d5c](superseded/ab42d5c/), commit [`b836f41`](https://github.com/kenil1710/asvoted/commit/b836f418da32f8bd1b2bb0e218a6512d35275cbb). Addresses were updated in deployments.json, ADDRESSES.md, the site and SUBMISSION.md.

**Final check.** [docs/FINAL_CHECK.md](FINAL_CHECK.md), 28/28.
