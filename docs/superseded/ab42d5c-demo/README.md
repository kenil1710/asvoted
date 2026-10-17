# Superseded demo sets from ab42d5c

Same contract code as the current deployment (ab42d5c, byte-identical on chain). Only the demo trio (registry, standing, gate) was redeployed, each time because a demo run could not finish every path. The payout fix worked on every one of them: every claim sent arrived at its recipient.

| Run | AsVotedRegistryDemo | Why it was replaced | eth_getBalance (wei) on 2026-10-17T21:47:54Z |
|---|---|---|---|
| part 1-2 | `0x5d054EAb7Dc657e99598C76A795aA530592B5D6D` | rate limits stalled judging past its deadlines | 7200000000000000000 |
| part 3 | `0x2aaabEC3480Be886203698300092ff82091D8eD2` | three proposal reads came back unreadable, so those paths were never filed | 0 |
| part 4 | `0xf0b5EDAad5A5263a750092880E9edE5f8645060B` | checks #1 and #2 were judged after their judge deadline | 5500000000000000000 |

None of this GEN is stuck. It is held for open checks and pledges, and in the books as `held_now` (`balance_matches_held` true). Anyone can still expire or finalize those checks, and the controller can then withdraw and claim the remainder.

Logs: `demo-run-part1.log` ... `demo-run-part4.log`, with the claims of parts 3 and 4 in `seed-demo-part3.json` and `seed-demo-part4.json`.
