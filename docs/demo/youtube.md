# AsVoted: did the Safe execute what token holders voted for?

Most DAOs vote on Snapshot and let a Safe multisig carry out the result. AsVoted, built on GenLayer, reads both sides itself. It decodes every action the Safe executed, from two RPCs that must agree. It reads the proposal by IPFS CID and verifies it in the contract. Then it rules on each action: code first for every address and amount, and a model only for calls the proposal describes in words, with a verbatim quote.

Shown in the video, all live on GenLayer Studio Dev:
- 0:00 The problem, and live figures read from the contracts
- Velora's 40.203 WETH return to Bybit: as voted, settled by code
- A CoW DAO batch with two calls the proposal never names: deviates
- A grant priced in dollars and paid in PSP: unclear (no prices)
- What the model is never allowed to decide
- Demo registry: a transfer filed against the wrong proposal, then appealed by naming the right one (as voted, bond refunded); a final deviates slashing a pledge; a consumer contract refusing to act
- The patrol bot, byte-identical source verification, the GenLayer explorer

Site: https://asvoted.vercel.app
Code: https://github.com/kenil1710/asvoted
Seeds: https://github.com/kenil1710/asvoted/blob/main/docs/SEEDS.md
