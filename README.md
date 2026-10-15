# AsVoted

**Did the Safe execute what token holders voted for?**

Most DAOs vote on Snapshot, off chain, and a Safe multisig carries out the result on chain. Nothing in between checks that what the signers executed is what passed. AsVoted reads both sides itself, rules on every action the Safe performed, puts a pledge behind the answer, and keeps watching.

- Live site: https://asvoted.vercel.app
- Network: GenLayer Studio Dev (chain 61997), explorer https://explorer-studio-dev.genlayer.com/
- Contracts and addresses: [ADDRESSES.md](ADDRESSES.md) · deployed from commit `790d6952d7bf6d7e3a39e485f02ec04f2e79f3fe`, byte-identical on chain (`node tools/verify_source.mjs`)
- Real seeds: [docs/SEEDS.md](docs/SEEDS.md) · Final check: [docs/FINAL_CHECK.md](docs/FINAL_CHECK.md) · Attacks: [docs/ATTACK_REPORT.md](docs/ATTACK_REPORT.md)

## How it works

Five pieces, six contracts, each doing one job:

| Contract | Job |
|---|---|
| `ExecReader` | Reads one Safe execution (chain, Safe, tx hash) at a finalized block the leader names, from **two allowlisted RPCs run by different operators that must answer identically**. Requires a direct, successful `execTransaction` to the Safe. Recomputes the Safe transaction hash in the contract (EIP-712, keccak-256, both domain layouts Safe has shipped) from the decoded calldata and the nonce, and requires the Safe's own `ExecutionSuccess` for exactly that hash. Decodes **every** action: the outer call and every inner call of a `MultiSend` / `MultiSendCallOnly` batch (recursively, allowlisted canonical deployments only), with ERC-20 `transfer` / `transferFrom` / `approve` decoded to token, recipient and amount (symbol and decimals read at the pinned block from both RPCs). A DELEGATECALL to anything else stays in the list as a DELEGATECALL; unknown selectors stay as raw calls with their argument words; a gas refund the Safe paid is an action too. The list is the calldata, decoded; no model ever chooses which actions exist. |
| `VoteReader` | Fetches the Snapshot proposal by IPFS CID from allowlisted gateways and **hashes the bytes against the CID in the contract** (CIDv1 raw: sha2-256 of the bytes; CIDv0 / dag-pb: sha2-256 of the single-chunk UnixFS node). The signed message inside gives space, author, title, body, voting type, choices, start, end and snapshot block. The Snapshot hub must report the same proposal (same CID, space, author, title, body, type, choices, start, end), `state = closed`, `scores_state = final`. Code computes PASSED / FAILED / UNCLEAR from the final scores (`basic`, and `single-choice` with an approving winning label; anything else is UNCLEAR). Records whether the Safe is listed among **the space's own treasuries** on that chain at read time. Resolves every ASCII `.eth` name in the text on Ethereum from both RPCs at the pinned block and, when the space votes on Ethereum, also at the proposal's snapshot block; a name counts only if all resolutions agree. |
| `AsVotedJudge` | Rules on each action: code first, the model only for what code cannot settle (below). |
| `AsVotedRegistry` | DAO listings, pledge bonds, checks, the PROVISIONAL → CONTESTABLE → FINAL lifecycle, one appeal, deadlines, pull payouts, the ledger. Canonical (1 h contest window) and demo (90 s) instances, same code. |
| `DaoStanding` + `GrantGate` | `is_executing_as_voted(dao, at_time)`: no FINAL DEVIATES ruling in the last 30 days. `GrantGate` is a tiny consumer that refuses to act for a DAO without that standing, and logs every request. |

A **patrol bot** (`frontend/src/lib/patrol.ts`, a Vercel function called by cron-job.org every 15 minutes with a secret header) watches every listed Safe's `ExecutionSuccess` events, matches each new execution to the most recent passed proposal of the space that ended before it (preferring one whose text names an address the execution touches), files the check on the canonical registry, and judges, rules on and closes its own filings after their deadlines. It never re-files a (Safe, tx). Every write estimates its fee by simulating the call first.

## How each action is decided

Code extracts from the proposal text, deterministically: every address (`0x` + 40 hex digits, and any address whose 40 hex digits appear inside quoted calldata), every ENS name that VoteReader resolved identically, and every token amount (a number with thousands separators, decimals and k / m / b / thousand / million / billion, next to a symbol or `$`). Then, per action:

1. **Exact calldata.** If the proposal quotes the action's exact calldata, for a contract it names → AUTHORIZED.
2. **Value moved** (native send, ERC-20 transfer / transferFrom / approve, gas refund). Recipient not mentioned anywhere → **NOT_AUTHORIZED**. Otherwise the amounts stated next to the recipient (same line, else paragraph, else section; the whole text only when the recipient is the only address it names) set the cap. **All transfers to that recipient in that token family are summed** – within the execution, and across earlier executions of the same DAO checked against the same proposal – so splitting a payment does not get under the cap. Above the largest stated amount + 0.5 % → **OVER_AMOUNT**. Amounts stated there only in other tokens → OVER_AMOUNT. Only dollar figures while paid in a volatile token → UNCLEAR (no prices). No amount stated → UNCLEAR. Unknown decimals → UNCLEAR. Unlimited approvals need the words "unlimited / infinite / max approval" near the spender.
3. **Calls.** A DELEGATECALL to an address the proposal does not mention → NOT_AUTHORIZED. A call that passes an address-like argument the proposal does not mention, or to a contract the proposal does not identify (by address, resolved ENS name, or the token's on-chain symbol as a whole word) → NOT_AUTHORIZED.
4. **Words, only for what is left**: an identified contract called with mentioned arguments. The model answers AUTHORIZED / NOT_AUTHORIZED / UNCLEAR with a verbatim quote. Code keeps the answer only if the quote is an exact substring of the proposal text (whitespace-normalised, at least 12 characters) and the leader's two answers agree; otherwise UNCLEAR.

**Overall (code):** AS_VOTED if every action is AUTHORIZED and the vote PASSED; DEVIATES if any action is NOT_AUTHORIZED or OVER_AMOUNT; otherwise UNCLEAR. Wording is neutral and dated: *"Execution 0x2d3d227c… on 2024-05-25 includes an action the proposal of 2024-04-12 does not mention."* or *"…sends more than the proposal of … states."* Never an accusation.

## What the model is never allowed to decide

- which actions an execution contains, or their order, operation, target or calldata
- any address: who received what, which contract was called, what an ENS name resolves to
- any amount, token, decimal, sum or tolerance
- any chain fact: block, transaction, success, the Safe transaction hash, the nonce
- whether the vote passed, whether it ended before the execution, whether the Safe belongs to the space
- the overall verdict, its severity, or where any money goes

The model sees the proposal text (fenced, defanged, untrusted) and a description of the calls code could not settle; on appeal also the counter-evidence (fenced, and quotes must still come from the proposal).

## When validators disagree (exactly as it behaves on chain)

- **ExecReader / VoteReader:** the leader's record is accepted only if byte-identical to the validator's own read at the same pinned block. A validator also rejects a leader block that is not final for it, or more than 30 minutes older than its own finalized block. If they differ, the transaction is not accepted and nothing is written; anyone can read again.
- **Judge:** the leader asks the model twice and keeps a verdict per action only where both agree (else UNCLEAR). Each validator re-runs the code part and its own two model answers and accepts only an identical per-action verdict list (quotes may differ but must each be a substring). If not, the transaction ends UNDETERMINED and **nothing is written**: the check stays PROVISIONAL (or APPEALED), anyone may call `judge` again, and after the deadline anyone may call `expire`, which records UNCLEAR and refunds. A disagreement is never recorded as a verdict.

## Money, lifecycle and who may do what

- Filing stake 0.1 GEN (exact). Appeal bond 0.1 GEN (exact). Pledge ≥ 0.1 GEN.
- `PROVISIONAL` (judge deadline 24 h canonical / 10 min demo; exit `expire` → UNCLEAR, refunds) → `CONTESTABLE` (1 h canonical / 90 s demo; exit `finalize`) → optional `APPEALED` (deadline 24 h / 10 min; exit `expire` → ruling stands, bond refunded) → `FINAL`. UNCLEAR is final at once.
- **DEVIATES final:** the pledge, as it stood at filing, is slashed by the worst action's severity from a frozen table (CRITICAL 50 % for an unnamed DELEGATECALL; MAJOR 25 % for value to an unmentioned address or > 10 % over; MINOR 10 % otherwise) and the slash is paid to whoever proved the deviation; their stake is refunded. **AS_VOTED final:** the challenger's stake goes to the DAO's pledge. **UNCLEAR:** refunds. A lost appeal's bond goes to the other side.
- Pull payouts only (`claim`). Every state has a deadline and a permissionless exit. No owner, admin or setter anywhere.
- **Listing** a DAO needs a VoteReader binding read within the last hour showing the Safe in the space's own treasury settings on that chain. **Claiming** a listing (pledge, withdraw, appeal DEVIATES) needs the sender to be an admin or moderator of the space in a fresh hub read. Only the demo registry additionally accepts the test controller fixed in its constructor (visible in `get_config`; the canonical constructor refuses any).
- Ledger invariant `received == pledges + open stakes and bonds + claimable + claimed`, kept as counters and recomputed from records in `get_ledger`.

## How a reviewer can test

1. **Read a real verdict.** Open https://asvoted.vercel.app, pick any check. Left: the proposal as voted, CID-pinned, with the quoted lines highlighted. Right: every decoded action with its chip. Click the tx and block links to see the same execution on Etherscan / Basescan / Optimistic Etherscan.
2. **Verify the code.** `/verify` reads every contract's code back from Studio Dev and compares its sha256 with the file at the deploy commit on GitHub, in your browser. Or `node tools/verify_source.mjs`.
3. **Run the offline suite.** `cd test && python3 -m unittest -q test_asvoted test_attacks test_attacks_r2` (no network), and `python3 tools/scan_writes.py` (no state written before a revert, every write method of every contract).
4. **Re-run a real read locally.** `python3 tools/live.py exec ethereum 0xcA771eda0c70aA7d053aB1B25004559B918FE662 0xf4631cc0ed16c718bd508f374b0064c7db0c36f72dc44a5dd46d73fb3f423b16 27` runs the contract's own ExecReader code against the two real RPCs and checks the validator path agrees.
5. **Drive every path yourself.** Switch the header to **Demo**, connect a wallet funded from the Studio faucet, file a check on `/file`, and use the buttons on the check page (each disabled with the contract's own reason until it applies). `test/demo_paths.mjs` does the whole set end to end; its log is [docs/demo-run.log](docs/demo-run.log).

## Known limitations

These cannot be fixed inside this design, and why:

- **Scores come from the Snapshot hub.** The proposal text, type, choices and dates are proven by the CID, but the vote totals are only on the hub. Recomputing them would mean re-running each space's voting strategies over every vote, which a contract cannot do. They are read only after `scores_state = final`.
- **The treasury listing is the hub's current setting.** It is checked when the proposal is read for the filing (fresh within one hour) and when listing, not as of the vote: Snapshot keeps no history of space settings.
- **Only direct `execTransaction` calls are read.** Executions through a Safe module (Zodiac Reality / oSnap `execTransactionFromModule`) or through a relayer contract are refused, because the actions are then not in the Safe's own calldata in a form two RPCs can bind to an `ExecutionSuccess` of that Safe.
- **Calls described only in words go to the model**, and a model can be wrong; that is why its answer needs a verbatim quote and two agreeing answers, and why counter-evidence and a fresh panel exist. Anything code can settle never reaches it.
- **Amounts in dollars paid in a volatile token are UNCLEAR.** The contract never fetches prices.
- **A standing mandate with a per-payment figure** ("send profits monthly, e.g. 237 WETH") will rule later, larger payments OVER_AMOUNT, because caps are summed across executions under the same proposal. That summing is what stops a cap from being spent twice; a proposal that wants recurring payments has to state the total.
- **Choosing the proposal is the filer's (or the bot's) claim.** One check per execution; a wrong match is corrected by appeal naming the right proposal (the 67 WETH demo shows it). A DAO that does not appeal within the window keeps a DEVIATES ruling on that listing.
- **One Safe can be listed under several spaces** if each space's settings list it; each listing has its own record and standing.
- **ENS names on non-Ethereum spaces are resolved only at the current block**, because the snapshot block of an L2-voting space is not an Ethereum block.
- **Studio Dev value transfers.** `claim()` posts the transfer, but Studio Dev queues it and does not deliver it, so a registry's on-chain balance stays above what it holds by up to the claimed total. The books (`held_now`) are what drain to zero.
- **Demo control seam.** No Safe or Snapshot space is controlled by this project, so the demo registry lets one test address claim listings; the canonical registry has none.
- **Public RPCs and gateways can be down.** Then a read is refused, never guessed; anyone can retry.

## Repository

- `contracts/` the six contracts (`shared/` holds helpers inlined identically into each by `tools/inline_shared.py`)
- `test/` offline suite (`stub.py`, `world.py`, `fixtures.py`, `test_*.py`), Studio scripts (`deploy.mjs`, `pipeline.mjs`, `seed_canonical.mjs`, `demo_paths.mjs`, `tx.mjs`)
- `tools/` `live.py` (contract code against the real network), `scan_writes.py`, `verify_source.mjs`, `sync_addresses.mjs`, `final_check.mjs`
- `frontend/` Next.js site and the patrol function
- `docs/` seeds, demo log, attack reports, final check, submission, article, video
