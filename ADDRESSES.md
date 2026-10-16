# Addresses (GenLayer Studio Dev, chain 61997)

Every contract below was deployed from commit `829e156efcbaf799e227929eeb3b427f678d1099`. `tools/verify_source.mjs` reads each one back with `gen_getContractCode` and compares it byte for byte with that commit.

| Contract | Address | Source | sha256 | Constructor |
|---|---|---|---|---|
| ExecReader | [`0x995Dd0251F1b6ee07Ec50D599E4D426b1A0ee3E0`](https://explorer-studio-dev.genlayer.com/address/0x995Dd0251F1b6ee07Ec50D599E4D426b1A0ee3E0) | `contracts/ExecReader.py` | `7dd9e041c41cf465…` | `[]` |
| VoteReader | [`0xE84085D2e047FD51797EA4a5567aAa6378ed4c4C`](https://explorer-studio-dev.genlayer.com/address/0xE84085D2e047FD51797EA4a5567aAa6378ed4c4C) | `contracts/VoteReader.py` | `9534a440354bd60c…` | `[]` |
| AsVotedJudge | [`0xbDF72F0600350f37634c317A4f3A508dB225A265`](https://explorer-studio-dev.genlayer.com/address/0xbDF72F0600350f37634c317A4f3A508dB225A265) | `contracts/AsVotedJudge.py` | `b903bd1f4c8ade4e…` | `[]` |
| AsVotedRegistry | [`0x70e5Cfd6eE3e980792DF7588C501C2b547619C87`](https://explorer-studio-dev.genlayer.com/address/0x70e5Cfd6eE3e980792DF7588C501C2b547619C87) | `contracts/AsVotedRegistry.py` | `e1567ceafbeacec6…` | `["CANONICAL","0x995Dd0251F1b6ee07Ec50D599E4D426b1A0ee3E0","0xE84085D2e047FD51797EA4a5567aAa6378ed4c4C","0xbDF72F0600350f37634c317A4f3A508dB225A265",""]` |
| AsVotedRegistryDemo | [`0xbe11F753e6DC262097a6dF7d65A1bF1f01ca80c6`](https://explorer-studio-dev.genlayer.com/address/0xbe11F753e6DC262097a6dF7d65A1bF1f01ca80c6) | `contracts/AsVotedRegistry.py` | `e1567ceafbeacec6…` | `["DEMO","0x995Dd0251F1b6ee07Ec50D599E4D426b1A0ee3E0","0xE84085D2e047FD51797EA4a5567aAa6378ed4c4C","0xbDF72F0600350f37634c317A4f3A508dB225A265","0x88fe8ab95e561a57ce2dd375355858a0893d5d2d"]` |
| DaoStanding | [`0x24685092D9B79A9198Dc0c18eA7D5E002D0900e8`](https://explorer-studio-dev.genlayer.com/address/0x24685092D9B79A9198Dc0c18eA7D5E002D0900e8) | `contracts/DaoStanding.py` | `952d2995d8f12e54…` | `["0x70e5Cfd6eE3e980792DF7588C501C2b547619C87",30]` |
| DaoStandingDemo | [`0x38C15757387F8a7a680A80ce4d36Fc1Bca145971`](https://explorer-studio-dev.genlayer.com/address/0x38C15757387F8a7a680A80ce4d36Fc1Bca145971) | `contracts/DaoStanding.py` | `952d2995d8f12e54…` | `["0xbe11F753e6DC262097a6dF7d65A1bF1f01ca80c6",30]` |
| GrantGate | [`0x298b61AB164C8df97E1CEe74BF29139Cd6135B59`](https://explorer-studio-dev.genlayer.com/address/0x298b61AB164C8df97E1CEe74BF29139Cd6135B59) | `contracts/GrantGate.py` | `2fc4477e774a6871…` | `["0x24685092D9B79A9198Dc0c18eA7D5E002D0900e8"]` |
| GrantGateDemo | [`0x1C35c963392EB503Abd09D9B426b4bDdc486d094`](https://explorer-studio-dev.genlayer.com/address/0x1C35c963392EB503Abd09D9B426b4bDdc486d094) | `contracts/GrantGate.py` | `2fc4477e774a6871…` | `["0x38C15757387F8a7a680A80ce4d36Fc1Bca145971"]` |
