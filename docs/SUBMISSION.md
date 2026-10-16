# Submission

## One-liner (176/180)

AsVoted checks every action a DAO's Safe executed against the passed Snapshot proposal its filer names: decoded calldata, CID-proven text, code-first rulings, pledges, appeals.

## Description (814/1000)

Most DAOs vote on Snapshot and a Safe multisig executes the result; nothing checks the two match. AsVoted reads the execution from two RPCs that must agree, decodes every action (MultiSend batches included) and verifies the Safe's own success event. It reads the proposal by IPFS CID, hashing it in the contract, checks the hub and the space's treasury list, and computes whether it passed. Code rules on each action: unnamed recipient, amount over the one figure the proposal states for it (summed across transfers), unnamed DELEGATECALL; ambiguity is UNCLEAR. A model only reads calls described in words, and must quote the text. DAOs pledge a bond; anyone files with a stake; one appeal; deadlines; pull payouts; no admin. A patrol bot watches listed Safes. 15 real executions: 8 as voted, 2 deviate, 5 unclear.

## How to try it (5 steps)

1. Open https://asvoted.vercel.app and pick a check: the proposal as voted on the left, every decoded action of the Safe execution on the right, a verdict per action. (163 chars)
2. Open /verify and click Compare: each contract's code is read from Studio Dev and hashed against the deploy commit on GitHub in your browser. (140 chars)
3. Switch the header to Demo, connect a wallet funded from the Studio faucet, and file a check on /file with a listed DAO, a Safe tx hash and a proposal CID. (154 chars)
4. On the check page, judge and apply the ruling, then appeal within 90 seconds (only the DAO, answering a DEVIATES, may name another proposal) or finalize after it. (162 chars)
5. Run the offline suite (cd test && python3 -m unittest test_asvoted test_attacks test_attacks_r2 test_attacks_r3) and read docs/SEEDS.md and docs/FINAL_CHECK.md. (160 chars)

## Review verification (356/500)

All 9 contracts deployed from commit 7a74665; node tools/verify_source.mjs (or the site's /verify) shows each is byte-identical on chain. Canonical registry: 15 real seeds, all ruled, final after the 6 h contest window, each linked to Etherscan and IPFS. Demo registry: every path run on chain, 25/25, drained to 0. 187 offline tests incl. 3 attack rounds.

## Evidence

- Repository: https://github.com/kenil1710/asvoted
- Live site: https://asvoted.vercel.app
- ExecReader (explorer): https://explorer-studio-dev.genlayer.com/address/0x6AFBFDE6D81b2DC3EbaE2Af822dF31f9D97dDC5a
- VoteReader (explorer): https://explorer-studio-dev.genlayer.com/address/0x7e4a6F43Df5Bb28ECd6D4E3b8a9DB5186200Bb88
- AsVotedJudge (explorer): https://explorer-studio-dev.genlayer.com/address/0xa75aF3785c25056589B0348a19b8fB10f5F66304
- AsVotedRegistry (explorer): https://explorer-studio-dev.genlayer.com/address/0x1C2891FE54a5CfE98436F439e40A3043050eFF44
- AsVotedRegistryDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x8B904F094F5b2A25C5004Ab09301dc9041c17B7a
- DaoStanding (explorer): https://explorer-studio-dev.genlayer.com/address/0x785b9091dBFc1a45F76ccE89Eaa22Dd8fb9A6D1E
- DaoStandingDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x659c4FE83ccFdfD0a6cC55A0004d70E574DfBDfa
- GrantGate (explorer): https://explorer-studio-dev.genlayer.com/address/0x8691BaB8DB890C5B20F563dE9e6f0c33645ad4c4
- GrantGateDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0xCC8De1d9b971B7fF484bbFb1C0CB1F9B2045BA7F
- Seeds: https://github.com/kenil1710/asvoted/blob/main/docs/SEEDS.md
- Final check: https://github.com/kenil1710/asvoted/blob/main/docs/FINAL_CHECK.md
- Attack report: https://github.com/kenil1710/asvoted/blob/main/docs/ATTACK_REPORT.md
- Demo video: https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted.mp4
  Recorded on the previous deployment (addresses in docs/superseded/); the flow is unchanged.
- Vertical cut: https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted-vertical.mp4
  Recorded on the previous deployment (addresses in docs/superseded/); the flow is unchanged.
- Medium article (draft): https://github.com/kenil1710/asvoted/blob/main/docs/medium.md
