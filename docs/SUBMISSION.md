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

## Review verification (445/500)

All 9 contracts deployed from commit ab42d5c; node tools/verify_source.mjs (or the site's /verify) shows each is byte-identical on chain. Canonical registry: 15 real seeds, all 15 final (6 AS_VOTED, 2 DEVIATES, 7 UNCLEAR), each linked to Etherscan and IPFS. Demo registry: every path run on chain, 30/30; 4/4 payouts arrived (recipient eth_getBalance checked); registry eth_getBalance 0 after the claims. 207 offline tests incl. 4 attack rounds.

## Evidence

- Repository: https://github.com/kenil1710/asvoted
- Live site: https://asvoted.vercel.app
- ExecReader (explorer): https://explorer-studio-dev.genlayer.com/address/0xA08486C9b6518B734D19Af58948db36FE3bdD961
- VoteReader (explorer): https://explorer-studio-dev.genlayer.com/address/0x029870D42f42f808eFE707fea6BB3D78dA48147F
- AsVotedJudge (explorer): https://explorer-studio-dev.genlayer.com/address/0xa7c0123bBc8c1982C2cD037e723aA0d1AbB6a2a1
- AsVotedRegistry (explorer): https://explorer-studio-dev.genlayer.com/address/0x808bbc73B8C65312d14e421C51C774EB4E90121C
- AsVotedRegistryDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0xBcD9e80084C796CB3ca07126c5180CD0bdB537D1
- DaoStanding (explorer): https://explorer-studio-dev.genlayer.com/address/0xF12CA2B1440AAB7915879D84Abf04123D71d905f
- DaoStandingDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0xfcae1de4D6B42752bFeF59bEa9140B6e4e39c128
- GrantGate (explorer): https://explorer-studio-dev.genlayer.com/address/0xf4A21d3e39e6807202Cd9f656EAAF1F7C115e187
- GrantGateDemo (explorer): https://explorer-studio-dev.genlayer.com/address/0x3C77CA433b10E71a414203a7FFeB20Bf10e20296
- Seeds: https://github.com/kenil1710/asvoted/blob/main/docs/SEEDS.md
- Final check: https://github.com/kenil1710/asvoted/blob/main/docs/FINAL_CHECK.md
- Attack report: https://github.com/kenil1710/asvoted/blob/main/docs/ATTACK_REPORT.md
- Attack report, round 4: https://github.com/kenil1710/asvoted/blob/main/docs/ATTACK_REPORT_R4.md
- Demo video: https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted.mp4
  Recorded on the previous deployment (addresses in docs/superseded/); the flow is unchanged.
- Vertical cut: https://github.com/kenil1710/asvoted/blob/main/docs/demo/asvoted-vertical.mp4
  Recorded on the previous deployment (addresses in docs/superseded/); the flow is unchanged.
- Medium article (draft): https://github.com/kenil1710/asvoted/blob/main/docs/medium.md
