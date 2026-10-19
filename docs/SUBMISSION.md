# Submission

## One-liner (176/180)

AsVoted checks every action a DAO's Safe executed against the passed Snapshot proposal its filer names: decoded calldata, CID-proven text, code-first rulings, pledges, appeals.

## Description (837/1000)

Most DAOs vote on Snapshot and a Safe multisig executes the result; nothing checks the two match. AsVoted reads the execution from two RPCs that must agree, decodes every action (MultiSend batches included) and verifies the Safe's own success event. It reads the proposal by IPFS CID, hashing it in the contract, checks the hub and the space's treasury list, and computes whether it passed. Code rules on each action: unnamed recipient, amount over the one figure the proposal states for it (summed across transfers), unnamed DELEGATECALL; ambiguity is UNCLEAR. A model only reads calls described in words, and must quote the text. DAOs pledge a bond; anyone files with a stake; one appeal; deadlines; pull payouts; no admin. A patrol bot scans listed Safes from durable checkpoints. 15 real executions: 6 as voted, 2 deviate, 7 unclear.

## How to try it (5 steps)

1. Open https://asvoted.vercel.app and pick a check: the proposal as voted on the left, every decoded action of the Safe execution on the right, a verdict per action. (163 chars)
2. Open /verify and click Compare: each contract's code is read from Studio Dev and hashed against the deploy commit on GitHub in your browser. (140 chars)
3. Switch the header to Demo, connect a wallet funded from the Studio faucet, and file a check on /file with a listed DAO, a Safe tx hash and a proposal CID. (154 chars)
4. On the check page, judge and apply the ruling, then appeal within 90 seconds (only the DAO, answering a DEVIATES, may name another proposal) or finalize after it. (162 chars)
5. Run the offline suites (cd test && python3 -m unittest test_asvoted test_attacks test_attacks_r2 test_attacks_r3 test_attacks_r4 test_steward; cd frontend && npm test). (168 chars)

## Review verification (469/500)

All 9 contracts deployed from commit b836f41; node tools/verify_source.mjs (or the site's /verify) shows each is byte-identical on chain. Canonical registry: 15 real seeds, all ruled, final after the 6 h contest window (6 AS_VOTED, 2 DEVIATES, 7 UNCLEAR), each linked to Etherscan and IPFS. Demo registry: every path run on chain, 35/35; 4/4 payouts arrived (recipient eth_getBalance checked); registry eth_getBalance 0 after the claims. 229 contract + 54 patrol tests.

## Evidence

- Repository: https://github.com/kenil1710/asvoted
- Live site: https://asvoted.vercel.app
- ExecReader (explorer): https://explorer-studio-dev.genlayer.com/address/0x08E3E60e037af578D1c5f4189cDDd888ac497685
- VoteReader (explorer): https://explorer-studio-dev.genlayer.com/address/0xEb81fc7584fFf7f9414B52575c0151B1cE9b0bc7
- AsVotedJudge (explorer): https://explorer-studio-dev.genlayer.com/address/0x73fA37dc86005942AA1045a82CcF9e48eAA557F6
- AsVotedRegistry (explorer): https://explorer-studio-dev.genlayer.com/address/0xc73438492c3F9604D99BfF7Aa268B7F77Aa3a9b1
- AsVotedRegistryDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x5AF1254384965e7E21ab37853Ee6385448331C50
- DaoStanding (explorer): https://explorer-studio-dev.genlayer.com/address/0x7B0B239181CAF8AFaa261f95E2344594d09d53A0
- DaoStandingDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x1dA328B19AbCaA8c30BA62c56D7e8775D7e0D380
- GrantGate (explorer): https://explorer-studio-dev.genlayer.com/address/0x638Ae4Cd8F0c62e373626E88F75490817bBD6877
- GrantGateDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0xecEb8c215fe63Fe1eBeF09f4Fe236087E106C50B
- Seeds: https://github.com/kenil1710/asvoted/blob/main/docs/SEEDS.md
- Final check: https://github.com/kenil1710/asvoted/blob/main/docs/FINAL_CHECK.md
- Attack report: https://github.com/kenil1710/asvoted/blob/main/docs/ATTACK_REPORT.md
- Attack report, round 4: https://github.com/kenil1710/asvoted/blob/main/docs/ATTACK_REPORT_R4.md
- Demo video: https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted.mp4
  Recorded on the previous deployment (addresses in docs/superseded/); the flow is unchanged.
- Vertical cut: https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted-vertical.mp4
  Recorded on the previous deployment (addresses in docs/superseded/); the flow is unchanged.
- Medium article (draft): https://github.com/kenil1710/asvoted/blob/main/docs/medium.md
