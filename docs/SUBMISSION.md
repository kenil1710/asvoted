# Submission

## One-liner (176/180)

AsVoted checks every action a DAO's Safe executed against the passed Snapshot proposal its filer names: decoded calldata, CID-proven text, code-first rulings, pledges, appeals.

## Description (814/1000)

Most DAOs vote on Snapshot and a Safe multisig executes the result; nothing checks the two match. AsVoted reads the execution from two RPCs that must agree, decodes every action (MultiSend batches included) and verifies the Safe's own success event. It reads the proposal by IPFS CID, hashing it in the contract, checks the hub and the space's treasury list, and computes whether it passed. Code rules on each action: unnamed recipient, amount over the one figure the proposal states for it (summed across transfers), unnamed DELEGATECALL; ambiguity is UNCLEAR. A model only reads calls described in words, and must quote the text. DAOs pledge a bond; anyone files with a stake; one appeal; deadlines; pull payouts; no admin. A patrol bot watches listed Safes. 15 real executions: 6 as voted, 2 deviate, 7 unclear.

## How to try it (5 steps)

1. Open https://asvoted.vercel.app and pick a check: the proposal as voted on the left, every decoded action of the Safe execution on the right, a verdict per action. (163 chars)
2. Open /verify and click Compare: each contract's code is read from Studio Dev and hashed against the deploy commit on GitHub in your browser. (140 chars)
3. Switch the header to Demo, connect a wallet funded from the Studio faucet, and file a check on /file with a listed DAO, a Safe tx hash and a proposal CID. (154 chars)
4. On the check page, judge and apply the ruling, then appeal within 90 seconds (only the DAO, answering a DEVIATES, may name another proposal) or finalize after it. (162 chars)
5. Run the offline suite (cd test && python3 -m unittest test_asvoted test_attacks test_attacks_r2 test_attacks_r3 test_attacks_r4) and read docs/SEEDS.md and docs/FINAL_CHECK.md. (176 chars)

## Review verification (323/500)

All 9 contracts deployed from commit 07ff3a3; node tools/verify_source.mjs (or the site's /verify) shows each is byte-identical on chain. Canonical registry: 15 real seeds, all 15 final, each linked to Etherscan and IPFS. Demo registry: every path run on chain, 25/25, drained to 0. 203 offline tests incl. 4 attack rounds.

## Evidence

- Repository: https://github.com/kenil1710/asvoted
- Live site: https://asvoted.vercel.app
- ExecReader (explorer): https://explorer-studio-dev.genlayer.com/address/0x694E28e38D66C95E3A2138e5d22F8158939e21f8
- VoteReader (explorer): https://explorer-studio-dev.genlayer.com/address/0x7319257a270EE4D77A302f193Eff76878ec02BCa
- AsVotedJudge (explorer): https://explorer-studio-dev.genlayer.com/address/0xC2aBc36E01DEab31C1F24A66A8D010Cd9F7F7dfF
- AsVotedRegistry (explorer): https://explorer-studio-dev.genlayer.com/address/0x4Ec22423528e64B4f1d41B7F647c0BD42464a30C
- AsVotedRegistryDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x65dB1CD4b79Bc87e5d6dbA315ea8F4239eAea028
- DaoStanding (explorer): https://explorer-studio-dev.genlayer.com/address/0xA74Bb08f0e497fc18138bF5383e5f65974eE3CCb
- DaoStandingDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x6EC6F4fABd87C7A7DCA24044ED011631106c408c
- GrantGate (explorer): https://explorer-studio-dev.genlayer.com/address/0x9848d38C85E1DFc8920c353124De3c82B519a62e
- GrantGateDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x428727dF01a31202a66B2ED7d35F474Ba7B97C28
- Seeds: https://github.com/kenil1710/asvoted/blob/main/docs/SEEDS.md
- Final check: https://github.com/kenil1710/asvoted/blob/main/docs/FINAL_CHECK.md
- Attack report: https://github.com/kenil1710/asvoted/blob/main/docs/ATTACK_REPORT.md
- Attack report, round 4: https://github.com/kenil1710/asvoted/blob/main/docs/ATTACK_REPORT_R4.md
- Demo video: https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted.mp4
  Recorded on the previous deployment (addresses in docs/superseded/); the flow is unchanged.
- Vertical cut: https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted-vertical.mp4
  Recorded on the previous deployment (addresses in docs/superseded/); the flow is unchanged.
- Medium article (draft): https://github.com/kenil1710/asvoted/blob/main/docs/medium.md
