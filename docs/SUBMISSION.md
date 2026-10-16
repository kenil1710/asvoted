# Submission

## One-liner (168/180)

AsVoted checks every action a DAO's Safe executed against the Snapshot proposal that passed: decoded calldata, CID-proven text, code-first rulings, pledges and appeals.

## Description (776/1000)

Most DAOs vote on Snapshot and a Safe multisig executes the result; nothing checks the two match. AsVoted reads the execution from two RPCs that must agree, decodes every action (MultiSend batches included) and verifies the Safe's own success event. It reads the proposal by IPFS CID, hashing it in the contract, checks the hub and the space's treasury list, and computes whether it passed. Code rules on each action: unnamed recipient, amount over what the proposal states (summed across transfers), unnamed DELEGATECALL. A model only reads calls described in words, and must quote the text. DAOs pledge a bond; anyone files with a stake; one appeal; deadlines; pull payouts; no admin. A patrol bot watches listed Safes. 15 real executions: 10 as voted, 2 deviate, 3 unclear.

## How to try it (5 steps)

1. Open https://asvoted.vercel.app and pick a check: the proposal as voted on the left, every decoded action of the Safe execution on the right, a verdict per action. (163 chars)
2. Open /verify and click Compare: each contract's code is read from Studio Dev and hashed against the deploy commit on GitHub in your browser. (140 chars)
3. Switch the header to Demo, connect a wallet funded from the Studio faucet, and file a check on /file with a listed DAO, a Safe tx hash and a proposal CID. (154 chars)
4. On the check page, judge and apply the ruling, then appeal within 90 seconds (a DEVIATES ruling can name a different proposal) or finalize after it. (148 chars)
5. Run the offline suite (cd test && python3 -m unittest test_asvoted test_attacks test_attacks_r2) and read docs/SEEDS.md and docs/FINAL_CHECK.md. (144 chars)

## Review verification (325/500)

All 9 contracts deployed from commit 93d5be9; node tools/verify_source.mjs (or the site's /verify) shows each is byte-identical on chain. Canonical registry: 15 real seeds, all final, every row linked to Etherscan and IPFS. Demo registry: every path run on chain, 23/23, drained to 0. 118 offline tests incl. 2 attack rounds.

## Evidence

- Repository: https://github.com/kenil1710/asvoted
- Live site: https://asvoted.vercel.app
- ExecReader (explorer): https://explorer-studio-dev.genlayer.com/address/0x31EabbC7978d784e9EeaAf5c4FFD82eD9BC5eeB9
- VoteReader (explorer): https://explorer-studio-dev.genlayer.com/address/0xe00Cc656c9cED6F61505E9b7440Dad2B690C19FB
- AsVotedJudge (explorer): https://explorer-studio-dev.genlayer.com/address/0x4fFdAf25Fb27ba9bCeDAA0f94d93D14993a69Fb4
- AsVotedRegistry (explorer): https://explorer-studio-dev.genlayer.com/address/0x2B4ac2D50978fc4937E9a479e4706688a6c5cCdc
- AsVotedRegistryDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x01AB66898cB6f1E949449f4a9B3D384f1079ea93
- DaoStanding (explorer): https://explorer-studio-dev.genlayer.com/address/0x2dee7BBc3e09E058B3AbEdfEeD2a2334ba69b870
- DaoStandingDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x5115162037A6aB89Bc70862b9C535e13f26D3693
- GrantGate (explorer): https://explorer-studio-dev.genlayer.com/address/0x31EAFAAbd993be7F837569cf8aecBb44CaA233D4
- GrantGateDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x8e437a04970bc587adaE2764F8E18A171fe1d946
- Seeds: https://github.com/kenil1710/asvoted/blob/main/docs/SEEDS.md
- Final check: https://github.com/kenil1710/asvoted/blob/main/docs/FINAL_CHECK.md
- Attack report: https://github.com/kenil1710/asvoted/blob/main/docs/ATTACK_REPORT.md
- Demo video: https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted.mp4
- Vertical cut: https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted-vertical.mp4
- Medium article (draft): https://github.com/kenil1710/asvoted/blob/main/docs/medium.md
