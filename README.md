# AsVoted

**Did the Safe execute what token holders voted for?**

Most DAOs vote on Snapshot, off chain, and a Safe multisig carries out the result on chain. Nothing in between checks that what the signers executed is what passed. AsVoted reads both sides itself, rules on every action the Safe performed, puts a pledge behind the answer, and keeps watching.

- Live site: https://asvoted.vercel.app
- Network: GenLayer Studio Dev (chain 61997), explorer https://explorer-studio-dev.genlayer.com/
- Contracts and addresses: [ADDRESSES.md](ADDRESSES.md) · deployed from commit `07ff3a3d2add9702114feca11317dab78d9d8966`, byte-identical on chain (`node tools/verify_source.mjs`)
- Real seeds (15 executions from 6 DAOs, all 15 final on chain): [docs/SEEDS.md](docs/SEEDS.md) · Final check: [docs/FINAL_CHECK.md](docs/FINAL_CHECK.md) · Attacks: [docs/ATTACK_REPORT.md](docs/ATTACK_REPORT.md)

## How it works

Five pieces, six contracts, each doing one job:

| Contract | Job |
|---|---|
| `ExecReader` | Reads one Safe execution (chain, Safe, tx hash) at a finalized block the leader names, from **two allowlisted RPCs run by different operators that must answer identically**. Requires a successful `execTransaction` of the Safe: a direct call, or, for a relayed SafeL2 Safe, its own `SafeMultiSigTransaction` log (nonce checked). Records the execution's Ethereum block (the block itself; the L1 attributes deposit on OP-stack chains; `l1BlockNumber` on Arbitrum). Recomputes the Safe transaction hash in the contract (EIP-712, keccak-256, both domain layouts Safe has shipped) from the decoded calldata and the nonce, and requires the Safe's own `ExecutionSuccess` for exactly that hash. Decodes **every** action: the outer call and every inner call of a `MultiSend` / `MultiSendCallOnly` batch (recursively, allowlisted canonical deployments only), with ERC-20 `transfer` / `transferFrom` / `approve` decoded to token, recipient and amount (symbol and decimals read at the pinned block from both RPCs). A DELEGATECALL to anything else stays in the list as a DELEGATECALL; unknown selectors stay as raw calls with their argument words; a gas refund the Safe paid is an action too. The list is the calldata, decoded; no model ever chooses which actions exist. |
| `VoteReader` | Fetches the Snapshot proposal by IPFS CID from allowlisted gateways and **hashes the bytes against the CID in the contract** (CIDv1 raw: sha2-256 of the bytes; CIDv0 / dag-pb: sha2-256 of the single-chunk UnixFS node). The signed message inside gives space, author, title, body, voting type, choices, start, end and snapshot block. The Snapshot hub must report the same proposal (same CID, space, author, title, body, type, choices, start, end), `state = closed`, `scores_state = final`. Code computes PASSED / FAILED / UNCLEAR from the final scores (`basic`, and `single-choice` with an approving winning label; anything else is UNCLEAR). Records whether the Safe is listed among **the space's own treasuries** on that chain at read time (used when listing; filings are bound to the listing). Resolves every ASCII `.eth` name in the text on Ethereum from both RPCs as voters saw it: at the Ethereum block of the vote's snapshot, mapped from the space's own network (the block itself on Ethereum; the L1 attributes deposit on OP-stack chains; `l1BlockNumber` on Arbitrum). For each filing it records where any name had moved by the execution's Ethereum block (`read_names_at`). |
| `AsVotedJudge` | Rules on each action: code first, the model only for what code cannot settle (below). |
| `AsVotedRegistry` | DAO listings, pledge bonds, checks, the PROVISIONAL → CONTESTABLE → FINAL lifecycle, one appeal, deadlines, pull payouts, the ledger. Canonical (6 h contest window) and demo (90 s) instances, same code. |
| `DaoStanding` + `GrantGate` | `is_executing_as_voted(dao, at_time)` and `is_executing_as_voted_for(space, chain, safe, at_time)`: no FINAL DEVIATES ruling on an execution from the last 30 days. `GrantGate` is a tiny consumer that refuses to act for a DAO without that standing, and logs every request. |

A **patrol bot** (`frontend/src/lib/patrol.ts`, a Vercel function called every 15 minutes with a secret header by a GitHub Actions schedule, `.github/workflows/patrol.yml`) watches every listed Safe's `ExecutionSuccess` events, matches each new execution to the most recent passed proposal of the space that ended before it and names an address the execution touches (if none does, it does not file), files the check on the canonical registry, and judges, rules on and closes its own filings after their deadlines. It never re-files a (Safe, tx). Every write estimates its fee by simulating the call first.

## How each action is decided

The rule for every step: when code cannot decide with certainty, the action is **UNCLEAR**, decided by code, never by the model.

Code reads the proposal text as voters see it rendered (HTML comments are dropped):
- **Addresses:** every `0x` + 40 hex digits, including inside a link's target, and any address whose 40 hex digits appear inside quoted calldata.
- **ENS names:** a name counts as the address it resolved to when voters voted, at the Ethereum block of the vote's snapshot, mapped from the space's own network. If the name pointed elsewhere by the time the Safe acted (`read_names_at`, snapshotted at filing), paying the address voters saw is fine; paying the new address is UNCLEAR. If the snapshot's Ethereum block cannot be found (Polygon), names count for nobody, and an unnamed payee is UNCLEAR rather than NOT_AUTHORIZED.
- **Amounts:** numbers with thousands separators `,` `'` `.` or spaces, decimals, a decimal comma after dot groups, and k / m / b / thousand / million / billion, next to a symbol or `$`, never inside a link target. An amount may be flagged as a minimum ("at least"), refused or excluded in its sentence ("rejected", "not", "instead of"), a valuation ("worth of"), or per period ("per month", "for 6 months").
- **Choices:** text under a losing choice's heading, or in a paragraph that begins with its name followed by ":" / "-" / ")" ("## Against", "Option B: …"), never sets a cap. That covers For/Against/Abstain as much as named options. If several choices approve something and the winner's own text can't be found, nothing caps.
- **Tokens:** identified by address, either on the judge's token list fixed at deployment (`test/token_list.json`, symbols read on chain) or named by address in the proposal. `symbol()` alone never identifies a token.

Then, per action:

1. **Exact calldata.** The proposal quotes the action's exact calldata, in a paragraph that names the target → AUTHORIZED.
2. **Wrapping.** `deposit()` or `withdraw(uint256)` on a listed WETH keeps the value in the Safe → **NEUTRAL**, a conversion, not a payment.
3. **Payments:** every call's ETH value is its own transfer to the call's target, whatever the calldata. ERC-20 `transfer` / `transferFrom` / `approve` and gas refunds are payments too.
   - **Payee:** not named anywhere → **NOT_AUTHORIZED**. So is a `transferFrom` whose source is neither the Safe nor named.
   - **Cap:** the one amount for that token on the payee's own line, list item or table row. An amount anywhere else is not a cap.
   - **No single cap → UNCLEAR, never AS_VOTED:**
     - no amount there, or two different amounts;
     - only a minimum;
     - a refusal in the amount's sentence;
     - a status word ("rejected", "withdrawn", "cancelled", "not", "void", …) anywhere in its line or bullet subtree;
     - a later paragraph that names the payee, or amends a figure of that token, with a different amount (the same figure again is fine);
     - a line or item that names several addresses ambiguously.
   - **Shared amounts:** one amount on a line naming several payees covers them together, unless it says "each".
   - **Totals:** payments and finite approvals to the payee in that token family are summed, within the execution and across every other filing under the same proposal, whatever its outcome. A per-period amount sums only within its calendar period.
   - **Every proposal:** the same payment is also counted with every filing of the DAO that paid this payee, under any proposal of the space. If that changes the ruling, the action is UNCLEAR, so switching proposals can't reset a running total.
   - **Over:** above the cap + 0.5 % → **OVER_AMOUNT**. Amounts stated only in other tokens → OVER_AMOUNT.
   - **Also UNCLEAR:** dollar figures paid in another token (no prices), an unidentified token, unknown decimals, more earlier filings than one judgment reads (24).
   - **Unlimited approvals:** they need the words "unlimited / infinite / max approval" near the spender.
4. **Calls.** These → NOT_AUTHORIZED:
   - a DELEGATECALL to an address the proposal does not name;
   - a call to a contract the proposal does not identify (by address, by ENS name, or by a listed token's symbol written in that exact case);
   - a call that passes an address-like argument the proposal does not name (a word below 2^160 and at least 2^96).

   Calls nested in `bytes` arguments (multicall, router sub-calls) are read through the ABI, three levels deep. Any address-shaped word there, including one starting `0x00`, that the proposal does not name → UNCLEAR. A call nested deeper than three levels → UNCLEAR. Neither goes to the model.
5. **Words, only for what is left:** an identified contract called with named arguments. The model answers AUTHORIZED / NOT_AUTHORIZED / UNCLEAR with a verbatim quote. Code keeps the answer only if the quote is an exact substring of the proposal text (whitespace-normalised, at least 12 characters) and the leader's two answers agree; otherwise UNCLEAR.

**Overall (code):** AS_VOTED if every action is AUTHORIZED or NEUTRAL and the vote PASSED; DEVIATES if any action is NOT_AUTHORIZED or OVER_AMOUNT; otherwise UNCLEAR. UNCLEAR refunds everyone, with no slash and no bounty. Wording is neutral and dated: *"Execution 0x408905df… on 2023-08-23 includes an action the proposal of 2022-11-09 does not mention."* (canonical check #7), or *"…sends more than the proposal of … states."* Never an accusation.

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
- **Observed on chain:** during the demo run, `ExecReader.read_execution` of CoW CIP-19 ended UNDETERMINED (tx `0x7b62c9110234be83d4a427b2664d7daea398668881d2a668ca7f4369e9d6c9e0`); no record was written, and the next read of the same execution succeeded.
- **Judge:** the leader asks the model twice and keeps a verdict per action only where both agree (else UNCLEAR). Each validator re-runs the code part and its own two model answers and accepts only an identical per-action verdict list (quotes may differ but must each be a substring). If not, the transaction ends UNDETERMINED and **nothing is written**: the check stays PROVISIONAL (or APPEALED), anyone may call `judge` again, and after the deadline anyone may call `expire`, which records UNCLEAR and refunds. A disagreement is never recorded as a verdict.

## Which proposal is an execution checked against?

The filer names one proposal, and the check compares the execution with that proposal and nothing else. DEVIATES means exactly "this execution includes an action the named proposal does not cover". It does not mean that no proposal covers it, or that anyone did wrong.

If another proposal does cover the action, the DAO appeals and names it. Switching the proposal is the DAO's defence only: just the listing's controller, answering a DEVIATES, may name another proposal. Nobody else can pair the execution with an unrelated proposal to turn a correct AS_VOTED into a DEVIATES. A fresh panel judges the same execution against the named proposal. The demo does this on chain: CoW's real 6,000,000 COW transfer to its Treasury (CIP-37) is filed against CIP-30 (the oSnap proposal, which never names the Treasury) and ruled DEVIATES. The DAO appeals naming CIP-37, and the ruling becomes AS_VOTED (demo registry, check #12; on the site, switch the header to **Demo** and open `/check/12`; transactions in [docs/demo-run.log](docs/demo-run.log)).

No final DEVIATES exists without the DAO having had one chance to answer:
- **A DEVIATES ruling** is the DAO's to answer during the contest window. On an unclaimed listing (every canonical one), anyone but the filer may appeal a DEVIATES, but that never uses up the DAO's turn. An admin who claims the listing within the window takes the appeal over, and the stranger's bond is returned. If the stranger's appeal loses, the window reopens, and only the controller may answer.
- **An AS_VOTED ruling** can be appealed by anyone but the controller. If the fresh panel says DEVIATES, the DAO gets its own response window (round 2) before anything is final.

Economics of a wrong pairing:
- The challenger staked 0.1 GEN to file. When the DAO's appeal turns the ruling to AS_VOTED, that stake goes to the DAO's pledge, so naming the wrong proposal costs the challenger their stake.
- The DAO's 0.1 GEN bond comes back when it wins. It goes to the other side when its answer loses, so answering costs something too.
- Nothing is slashed until a DEVIATES is final, and that needs the DAO's window to have passed, so a pairing the DAO corrects never touches its pledge.

## Money, lifecycle and who may do what

- Filing stake 0.1 GEN (exact). Appeal bond 0.1 GEN (exact). Pledge ≥ 0.1 GEN.
- `PROVISIONAL` (judge deadline 24 h canonical / 10 min demo; exit `expire` → UNCLEAR, refunds) → `CONTESTABLE` (6 h canonical / 90 s demo; exit `finalize`). If an appeal turns AS_VOTED into DEVIATES, or a stranger's appeal of a DEVIATES loses, the check is CONTESTABLE again for the DAO's controller only (round 2, same window), then APPEALED and FINAL on the response panel's ruling, or on the appeal's ruling if the DAO lets the window pass → optional `APPEALED` (deadline 24 h / 10 min; exit `expire` → ruling stands, bond refunded) → `FINAL`. UNCLEAR is final at once.
- **DEVIATES final:** the pledge, as it stood at filing, is slashed by the worst action's severity from a frozen table (CRITICAL 50 % for an unnamed DELEGATECALL; MAJOR 25 % for value to an unmentioned address or > 10 % over; MINOR 10 % otherwise) and the slash is paid to whoever proved the deviation; their stake is refunded. **AS_VOTED final:** the challenger's stake goes to the DAO's pledge. **UNCLEAR:** refunds. A lost appeal's bond goes to the other side.
- **Pledge withdrawal:** requested by the controller, paid out no sooner than a full contest window plus a filing window after the request (6 h + 6 h canonical, 90 s + 120 s demo). An execution made before the request can finalize on its chain, be filed and be contested before the pledge can leave. Open checks of executions made before the unlock block it (a counter, so no number of newer checks can hide one).
- **Standing** (`DaoStanding`) dates a final DEVIATES by when the execution ran, not when the ruling became final.
- Pull payouts only (`claim`). Every state has a deadline and a permissionless exit. No owner, admin or setter anywhere.
- **Listing** a DAO needs a VoteReader binding read within the last hour showing the Safe in the space's own treasury settings on that chain. Filings are bound to the listing: the proposal must be from the listing's space, and a space that later drops the Safe from its settings cannot switch checks off. **Claiming** a listing (pledge, withdraw, appeal DEVIATES) needs the sender to be an admin or moderator of the space in a fresh hub read. Only the demo registry additionally accepts the test controller fixed in its constructor (visible in `get_config`; the canonical constructor refuses any).
- **Identity:** a DAO is the pair (Snapshot space, Safe on a chain); `DaoStanding.is_executing_as_voted_for(space, chain, safe, at)` answers by that pair. A listing is **verified** only when the Safe itself owns the space's ENS name (through the NameWrapper when wrapped), so changing the name takes the Safe's own threshold of signers and no single signer can earn the badge. The site shows the badge.
- Ledger invariant `received == pledges + open stakes and bonds + claimable + claimed`, kept as counters and recomputed from records in `get_ledger`.

### Payouts on chain

Every payout (refunds, bounties, bonds, pledge withdrawals) is credited to a pull balance, and `claim()` is the only way GEN leaves. It pays through `_pay`, the single send site: an external transfer (`EthSend`, via a `gl.evm` interface handle) to the claimer. The call reverts, and nothing is marked paid, if the amount is 0, the address is zero or the contract's balance is short.

Earlier deployments used `gl.chain.Account(who).emit_transfer(...)`. That posts an internal message, which only an Intelligent Contract can receive, so for an EOA Studio Dev skipped it and refunded the value to the registry. None of those claims paid anyone, and the old registries still hold that GEN (docs/superseded/). The probe that found this and tested the fix is in [docs/research/PAYOUT_PROBE.md](docs/research/PAYOUT_PROBE.md). With the fix, a registry's `eth_getBalance` equals its `held_now`. `tools/final_check.mjs` checks that on both registries, re-checks every demo claim on chain (FINALIZED, external transfer executed, none skipped, recipient `eth_getBalance` up by exactly amount minus the claim's fee), and counts the demo as drained only when the registry's `eth_getBalance` is 0.

## How a reviewer can test

1. **Read a real verdict.** Open https://asvoted.vercel.app, pick any check. Left: the proposal as voted, CID-pinned, with the quoted lines highlighted. Right: every decoded action with its chip. Click the tx and block links to see the same execution on Etherscan / Basescan / Optimistic Etherscan.
2. **Verify the code.** `/verify` reads every contract's code back from Studio Dev and compares its sha256 with the file at the deploy commit on GitHub, in your browser. Or `node tools/verify_source.mjs`.
3. **Run the offline suite.** `cd test && python3 -m unittest -q test_asvoted test_attacks test_attacks_r2 test_attacks_r3 test_attacks_r4` (no network), and `python3 tools/scan_writes.py` (no state written before a revert, every write method of every contract).
4. **Re-run a real read locally.** `python3 tools/live.py exec ethereum 0xcA771eda0c70aA7d053aB1B25004559B918FE662 0xf4631cc0ed16c718bd508f374b0064c7db0c36f72dc44a5dd46d73fb3f423b16 27` runs the contract's own ExecReader code against the two real RPCs and checks the validator path agrees.
5. **Drive every path yourself.** Switch the header to **Demo**, connect a wallet funded from the Studio faucet, file a check on `/file`, and use the buttons on the check page (each disabled with the contract's own reason until it applies). `test/demo_paths.mjs` does the whole set end to end; its log is [docs/demo-run.log](docs/demo-run.log).

## Known limitations

Fixed in round 3, with tests in `test/test_attacks_r3.py` (see [docs/ATTACK_REPORT.md](docs/ATTACK_REPORT.md)):
- Filings are bound to the listing.
- ENS names mean what voters saw, at the snapshot's Ethereum block for every network; a name moved by the payment is UNCLEAR, never a slash.
- Relayed executions of SafeL2 Safes are read from their own log.
- DAO identity is (space, Safe); the verified badge needs the Safe itself to own the space's name.
- Every filing counts toward caps, and expired checks can be refiled.
- Withdrawals wait a full filing and contest window.
- The DAO always gets a response window before a final DEVIATES.
- Caps are only unambiguous own-line amounts.
- Losing choices don't count.
- Tokens are identified by address.
- Nested calldata is read through the ABI to three levels (any unnamed address-shaped word there, deeper nesting: UNCLEAR).
- Round 4: the DAO's appeal slot is reserved on unclaimed listings; a payment counts under every proposal naming its payee; later amendments, status words in a bullet subtree and losing-choice text (Against included) never leave a cap; wrapping ETH is NEUTRAL.
- The number formats from the round are read correctly.

What is left can't be fixed on Studio Dev, or is a deliberate choice:

- **Scores come from the Snapshot hub.** *Can't fix:* the text, type, choices and dates are proven by the CID, but the vote totals exist only on the hub. Recomputing them means re-running each space's voting strategies over every vote, which no contract can do. They are read only after `scores_state = final`.
- **Any Snapshot space can list any Safe.** *By design:* Snapshot never verifies a space's treasury entries. A DAO is therefore the pair (space, Safe). A rogue space's listing is a separate record that can't file the real space's proposals or touch the real listing's standing (`r3_62`). Only a listing whose space name is owned by the Safe itself gets the verified badge (`r4_11`). Refusing unverified listings would refuse real DAOs, whose Safes rarely own their Snapshot name.
- **The treasury setting is checked when listing, not as of the vote.** *Can't fix:* Snapshot keeps no history of space settings. Later changes can't block filings, because filings are bound to the listing.
- **Module executions are not read.** *By design:* Zodiac Reality and oSnap call `execTransactionFromModule`, whose actions are an internal call with no log that carries them. They are refused rather than misread. Relayed executions are read only for SafeL2 Safes (which log every parameter); a relayed mainnet Safe is refused for the same reason.
- **Only executions that are filed count toward a cap.** *By design:* a check is about one execution, and the contract can't list a Safe's history without an indexer. Every other filing under the same proposal is summed, whatever its outcome (up to 24; more makes a within-cap result UNCLEAR). The patrol bot files every execution it matches.
- **Calls described only in words go to the model.** *By design:* a model can be wrong, so its answer needs a verbatim quote and two agreeing answers, and counter-evidence and a fresh panel exist. Anything code can settle never reaches it.
- **Dollar amounts paid in another token are UNCLEAR.** *By design:* "$500 per epoch, paid in PSP" doesn't say whose price or at which moment (the vote, the payment). Most paid tokens (COW, PSP) have no on-chain feed. Any choice the contract made would be a guess presented as a ruling.
- **Caps must be written plainly.** *By design:* a cap counts only when it is the single amount for that token on the recipient's own line, list item or table row. A budget stated elsewhere ("Recipient: …" with "Amount: …" on the next line, a section budget, a sample figure in a standing mandate such as CIP-28) gives UNCLEAR, never AS_VOTED. Every looser reading was an attack in round 3. A proposal that wants a cap enforced puts the amount next to the address.
- **Ambiguous numbers are read the small way or not at all.** *By design:* `50.000 USDC` is 50, `5 000 USDC` with one plain space is no amount, and amounts in words ("fifty thousand") are not read.
- **Argument words between 2^96 and 2^160 are treated as addresses.** *By design:* this catches vanity addresses with up to 16 leading zero hex digits. A call argument that is really an amount that large (79 billion tokens at 18 decimals) must then be named in the proposal.
- **Tokens off the token list must be named by address.** *By design:* the list (USDC, USDT, DAI, WETH and the seeds' DAO tokens per chain) is fixed at deployment. A token not on it, named only by its symbol, is UNCLEAR, because `symbol()` can be anything.
- **A link's target counts as naming an address; numbers inside it don't.** *By design:* the target is part of what voters read (on hover, in the raw text, behind every explorer link). HTML comments are dropped because Markdown never shows them.
- **The filer chooses the proposal.** *By design:* one check per execution. A wrong pairing is corrected by the DAO's appeal naming the right proposal (demo check #12). On an unclaimed listing the DAO must claim it first (an admin of the space), which it can do within the window even after a stranger has appealed. Only the DAO's controller may name another proposal, and only when answering a DEVIATES.
- **ENS names for Polygon-voting spaces are not resolved.** *Can't fix cheaply:* a Polygon block carries no Ethereum block number, so the vote's snapshot can't be placed on Ethereum. Such names never count as naming anyone, and an address they might name is UNCLEAR rather than NOT_AUTHORIZED.
- **Old deployments hold stuck GEN.** *Can't fix:* the registries before this one paid with an internal message that Studio Dev skips for an EOA (see Payouts on chain). Their claims are marked paid in their books, but the GEN never left those contracts, and no method can send it now.
- **Demo control seam and short demo windows.** *By design:* this project controls no Safe or Snapshot space, so the demo registry lets one test address claim listings and uses 90 s windows. The canonical registry has neither.
- **Public RPCs and gateways can be down.** *By design:* a read is then refused, never guessed, and anyone can retry.

## Repository

- `contracts/` the six contracts (`shared/` holds helpers inlined identically into each by `tools/inline_shared.py`)
- `test/` offline suite (`stub.py`, `world.py`, `fixtures.py`, `test_*.py`), Studio scripts (`deploy.mjs`, `pipeline.mjs`, `seed_canonical.mjs`, `demo_paths.mjs`, `tx.mjs`)
- `tools/` `live.py` (contract code against the real network), `scan_writes.py`, `verify_source.mjs`, `sync_addresses.mjs`, `final_check.mjs`
- `frontend/` Next.js site and the patrol function
- `docs/` seeds, demo log, attack reports, final check, submission, article, video
