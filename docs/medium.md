# The vote is off chain. The money isn't. Who checks the gap?

Most DAOs make decisions in two places. Token holders vote on Snapshot, which is free, fast and off chain. Then a handful of signers on a Safe multisig carry out the result on chain. The vote says "send 60 ETH to the ops Safe". The Safe sends something. Whether that something is what passed is left to whoever has time to read both.

I built AsVoted to read both, every time, and to say plainly when they line up and when they don't.

## Reading the receipt

Start with the execution, because it can't lie about itself. A Safe transaction is one `execTransaction` call, and everything it does is in its calldata: a transfer, an approval, or a batch of twenty calls packed into a MultiSend. AsVoted's first contract, ExecReader, decodes all of it. Every inner call of a batch becomes one row: target, value, function, and for token transfers the token, the recipient and the amount.

It reads the transaction from two public RPCs run by different companies, at a block both agree is final, and refuses if they disagree on a single field. It then recomputes the Safe's own transaction hash from the decoded calldata and checks that the Safe emitted `ExecutionSuccess` for exactly that hash. Nothing gets to decide which actions exist. The list is the calldata.

## Reading the ballot

The second contract, VoteReader, fetches the Snapshot proposal by its IPFS CID and hashes the bytes in the contract, so the text it judges against is provably the text that was proposed. It asks the Snapshot hub for the same proposal and refuses if the hub's copy differs. That catches edits: an edited proposal gets a new CID. It computes whether the vote passed from the final scores. It also checks the space's own settings: is this Safe listed as one of the space's treasuries? If not, there's no check.

## Code first, words last

Then the judge rules on each action. Code does almost all of it, and when it cannot tell, it says UNCLEAR rather than guess:

- Was the recipient's address, or an ENS name that resolved to it both at the vote and when the Safe acted, written anywhere in the proposal? If not, the action is not in the proposal.
- What amount does the proposal state for that recipient? Only the single amount on the recipient's own line, list item or table row counts. Two different figures, a figure that is refused in its sentence, or a budget stated somewhere else is no cap at all. All transfers to them in that token are added up, across the batch and across every other execution filed under the same proposal. Splitting a payment in two doesn't get under the cap. More than the stated amount plus half a percent is over.
- A DELEGATECALL to an address the proposal never names is the most serious finding there is.

Only what code cannot settle goes to an AI model. That means a call to a contract the proposal names, with arguments it names, where only the words can say whether this function call is what was meant. The model has to quote the proposal word for word, and two of its answers have to agree. Otherwise the action is unclear. The model never decides an address, an amount, a chain fact, whether the vote passed, or the verdict.

## Fifteen real executions

I ran it on fifteen real Safe executions from six DAOs: CoW DAO, Velora (ParaSwap), Bankless, Morpho, SafeDAO and Krause House, on Ethereum, Optimism and Base. Eight came back AS VOTED, two DEVIATES and five UNCLEAR.

The AS VOTED cases are the boring, reassuring majority. Velora's Safe returned 40.203 WETH to Bybit after the February 2025 hack. The proposal names the address and the amount, and the execution matches to the wei. No model was involved.

The two DEVIATES are the kind you'd expect, and neither is an accusation. In one, a CoW DAO batch did exactly what CIP-16 described (claim SAFE tokens and delegate them), with the calldata quoted in the proposal itself. It also made two calls to a contract the proposal never names. In the other, the SafeDAO Safe passed an address that no SafeDAO Snapshot proposal writes out. The finding is narrow and dated: "Execution 0x408905df… on 2023-08-23 includes an action the proposal of 2022-11-09 does not mention." Often that means the proposal should have named something, not that anyone did anything wrong.

The five UNCLEAR are honest gaps. Two proposals name the receiving Safe without putting a figure on its line: CIP-28 is a standing mandate with a sample amount elsewhere, and MIP79 sends "half" of a total stated on another line. A cap has to be the one amount on the recipient's own line, so the contract won't guess. One proposal names the treasury but no amount at all. One prices a grant at "$500 per epoch" and pays in PSP; the contract never fetches prices, so it won't compare them. One DAO votes with weighted voting, whose result the contract doesn't compute.

## The wrong proposal, and the answer

A check compares one execution with the one proposal its filer names. That makes pairing the weak point, so it is where appeals live.

On 14 February 2024, CoW DAO's main Safe sent 6,000,000 COW to its treasury Safe. That is CIP-37, a plan to add COW liquidity through programmatic orders, and judged against CIP-37 the transfer is AS VOTED. On the demo registry I filed it against CIP-30 on purpose. CIP-30 sets up oSnap and never names the treasury, so against CIP-30 the transfer is DEVIATES: it sends to an address the proposal does not mention.

The DAO's controller then appealed with a 0.1 GEN bond, naming CIP-37. A fresh panel of validators read CIP-37, ruled AS VOTED, and the bond went back. The filer's stake went to the DAO's pledge.

Two rules keep this from being turned around. Only the DAO may name a different proposal; nobody else can pair a correct execution with an unrelated proposal to manufacture a deviation. And no DEVIATES becomes final until the DAO has had one chance to answer. If a stranger appeals an AS VOTED ruling and the new panel says DEVIATES, the DAO gets its own window before anything is final.

## Money behind it

A DAO can post a pledge: "we execute only what passed". Anyone can file a check with a small stake. A final DEVIATES ruling slashes the pledge, by a severity table fixed in the contract, and pays it to whoever proved it. A final AS VOTED ruling adds the challenger's stake to the DAO's pledge. Every state has a deadline that anyone can close, and there is no owner or admin anywhere. Other contracts can ask a single question, `is_executing_as_voted`. A small demo contract refuses to act for a DAO with a final DEVIATES ruling on an execution from the last 30 days.

A patrol bot runs every fifteen minutes. It watches the listed Safes, matches each new execution to the latest passed proposal that names something it touches, and files the check. When no proposal names anything, it files nothing.

## What it can't do

Some limits are built in. Vote totals come from the Snapshot hub; recomputing them would mean re-running every voting strategy. Executions through Safe modules (Reality, oSnap) aren't read. A standing mandate with a per-payment figure will flag later, larger payments. The choice of proposal is the filer's claim, which is what the DAO's appeal is for. The README lists all of these, with the reason for each.

AsVoted runs on GenLayer Studio Dev. The site is https://asvoted.vercel.app, and every number on it is read from the contracts. The code is at https://github.com/kenil1710/asvoted.
