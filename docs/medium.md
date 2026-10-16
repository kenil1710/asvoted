# The vote is off chain. The money isn't. Who checks the gap?

Most DAOs make decisions in two places. Token holders vote on Snapshot, which is free, fast and off chain. Then a handful of signers on a Safe multisig carry out the result on chain. The vote says "send 60 ETH to the ops Safe". The Safe sends something. Whether that something is what passed is left to whoever has time to read both.

I built AsVoted to read both, every time, and to say plainly when they line up and when they don't.

## Reading the receipt

Start with the execution, because it can't lie about itself. A Safe transaction is one `execTransaction` call, and everything it does is in its calldata: a transfer, an approval, or a batch of twenty calls packed into a MultiSend. AsVoted's first contract, ExecReader, decodes all of it. Every inner call of a batch becomes one row: target, value, function, and for token transfers the token, the recipient and the amount.

It reads the transaction from two public RPCs run by different companies, at a block both agree is final, and refuses if they disagree on a single field. It then recomputes the Safe's own transaction hash from the decoded calldata and checks that the Safe emitted `ExecutionSuccess` for exactly that hash. Nothing gets to decide which actions exist. The list is the calldata.

## Reading the ballot

The second contract, VoteReader, fetches the Snapshot proposal by its IPFS CID and hashes the bytes in the contract, so the text it judges against is provably the text that was proposed. It asks the Snapshot hub for the same proposal and refuses if the hub's copy differs. That catches edits: an edited proposal gets a new CID. It computes whether the vote passed from the final scores. It also checks the space's own settings: is this Safe listed as one of the space's treasuries? If not, there's no check.

## Code first, words last

Then the judge rules on each action. Code does almost all of it:

- Was the recipient's address, or an ENS name that resolved to it at the vote and still does, written anywhere in the proposal? If not, the action is not in the proposal.
- What amounts does the proposal state next to that recipient? All transfers to them in that token are added up, across the batch and across earlier executions under the same proposal. Splitting a payment in two doesn't get under the cap. More than the largest stated amount plus half a percent is over.
- A DELEGATECALL to an address the proposal never names is the most serious finding there is.

Only what code cannot settle goes to an AI model. That means a call to a contract the proposal names, with arguments it names, where only the words can say whether this function call is what was meant. The model has to quote the proposal word for word, and two of its answers have to agree. Otherwise the action is unclear. The model never decides an address, an amount, a chain fact, whether the vote passed, or the verdict.

## Fifteen real executions

I ran it on fifteen real Safe executions from six DAOs: CoW DAO, Velora (ParaSwap), Bankless, Morpho, SafeDAO and Krause House, on Ethereum, Optimism and Base. Ten came back AS VOTED, two DEVIATES and three UNCLEAR.

The AS VOTED cases are the boring, reassuring majority. Velora's Safe returned 40.203 WETH to Bybit after the February 2025 hack. The proposal names the address and the amount, and the execution matches to the wei. No model was involved.

The two DEVIATES are the kind you'd expect, and neither is an accusation. In one, a CoW DAO batch did exactly what CIP-16 described (claim SAFE tokens and delegate them), with the calldata quoted in the proposal itself. It also made two calls to a contract the proposal never names. In the other, the SafeDAO Safe passed an address that no SafeDAO Snapshot proposal writes out. The finding is narrow and dated: "Execution 0x408905df… on 2023-08-23 includes an action the proposal of 2022-11-09 does not mention." Often that means the proposal should have named something, not that anyone did anything wrong.

The three UNCLEAR are honest gaps. One proposal names the treasury but no amount. One prices a grant at "$500 per epoch" and pays in PSP; the contract never fetches prices, so it won't compare them. One DAO votes with weighted voting, whose result the contract doesn't compute.

## The 67 WETH story

The example I keep coming back to happened while I was choosing seeds.

On 25 May 2024, CoW DAO's main Safe sent 67.0123 WETH to its treasury Safe. My matching script found CIP-43 that same week: "Transfer 60 ETH (ca. 180k USD equivalent)… to the CoW DAO Ops Safe." It names the treasury Safe, so the match looked right. Judged against CIP-43, the transfer is over the stated 60 ETH by about 12%. On a first read, that's a deviation.

Read CIP-43 again, though. The treasury is where the 60 ETH comes *from*. The transfer went *to* it. It was a different operation: CIP-28, the standing mandate for CoW DAO to send its profits to the treasury. Judged against CIP-28, the same transfer is AS VOTED.

This is why AsVoted has appeals. On the demo registry I filed the transfer against CIP-43 on purpose, and it came back DEVIATES. The DAO's controller then appealed with a 0.1 GEN bond, naming CIP-28 as the proposal this execution actually implements. A fresh panel of validators read CIP-28, ruled AS VOTED, and the bond went back. The wrong match was corrected without anyone having to trust anyone's word.

## Money behind it

A DAO can post a pledge: "we execute only what passed". Anyone can file a check with a small stake. A final DEVIATES ruling slashes the pledge, by a severity table fixed in the contract, and pays it to whoever proved it. A final AS VOTED ruling adds the challenger's stake to the DAO's pledge. Every state has a deadline that anyone can close, and there is no owner or admin anywhere. Other contracts can ask a single question, `is_executing_as_voted`. A small demo contract refuses to act for a DAO with a final DEVIATES ruling on an execution from the last 30 days.

A patrol bot runs every fifteen minutes. It watches the listed Safes, matches each new execution to the latest passed proposal that names something it touches, and files the check. When no proposal names anything, it files nothing.

## What it can't do

Some limits are built in. Vote totals come from the Snapshot hub; recomputing them would mean re-running every voting strategy. Executions through Safe modules (Reality, oSnap) aren't read. A standing mandate with a per-payment figure will flag later, larger payments. The choice of proposal is the filer's claim, which is what the DAO's appeal is for. The README lists all of these, with the reason for each.

AsVoted runs on GenLayer Studio Dev. The site is https://asvoted.vercel.app, and every number on it is read from the contracts. The code is at https://github.com/kenil1710/asvoted.
