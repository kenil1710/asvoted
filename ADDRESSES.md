# Addresses (GenLayer Studio Dev, chain 61997)

Every contract below was deployed from commit `790d6952d7bf6d7e3a39e485f02ec04f2e79f3fe`. `tools/verify_source.mjs` reads each one back with `gen_getContractCode` and compares it byte for byte with that commit.

| Contract | Address | Source | sha256 | Constructor |
|---|---|---|---|---|
| ExecReader | [`0xE2e7C95764F8B79f290fF6508615288892E2D3DF`](https://explorer-studio-dev.genlayer.com/address/0xE2e7C95764F8B79f290fF6508615288892E2D3DF) | `contracts/ExecReader.py` | `4909d23888c4da17…` | `[]` |
| VoteReader | [`0xCc11fecbc480F5504005310720ab6Acd28eB67fF`](https://explorer-studio-dev.genlayer.com/address/0xCc11fecbc480F5504005310720ab6Acd28eB67fF) | `contracts/VoteReader.py` | `4ee549d44fd54eda…` | `[]` |
| AsVotedJudge | [`0xA551073A2aA7949AFE22997a6d261ecCE1e99D66`](https://explorer-studio-dev.genlayer.com/address/0xA551073A2aA7949AFE22997a6d261ecCE1e99D66) | `contracts/AsVotedJudge.py` | `97c7fc99c1953482…` | `[]` |
| AsVotedRegistry | [`0xE6cA8E64fBD3f2Cb68ACa2E8Af144e435EAe7528`](https://explorer-studio-dev.genlayer.com/address/0xE6cA8E64fBD3f2Cb68ACa2E8Af144e435EAe7528) | `contracts/AsVotedRegistry.py` | `e2bc0b60ed49ba40…` | `["CANONICAL","0xE2e7C95764F8B79f290fF6508615288892E2D3DF","0xCc11fecbc480F5504005310720ab6Acd28eB67fF","0xA551073A2aA7949AFE22997a6d261ecCE1e99D66",""]` |
| AsVotedRegistryDemo | [`0x9cCdDe5f5AAefC1387F437Baf96A1FC5E2be2F3F`](https://explorer-studio-dev.genlayer.com/address/0x9cCdDe5f5AAefC1387F437Baf96A1FC5E2be2F3F) | `contracts/AsVotedRegistry.py` | `e2bc0b60ed49ba40…` | `["DEMO","0xE2e7C95764F8B79f290fF6508615288892E2D3DF","0xCc11fecbc480F5504005310720ab6Acd28eB67fF","0xA551073A2aA7949AFE22997a6d261ecCE1e99D66","0x88fe8ab95e561a57ce2dd375355858a0893d5d2d"]` |
| DaoStanding | [`0x16fec6B9ce8A069c9262a209884360378037083C`](https://explorer-studio-dev.genlayer.com/address/0x16fec6B9ce8A069c9262a209884360378037083C) | `contracts/DaoStanding.py` | `952d2995d8f12e54…` | `["0xE6cA8E64fBD3f2Cb68ACa2E8Af144e435EAe7528",30]` |
| DaoStandingDemo | [`0xA8b2467277f32562ce01c789217D995C21982BCF`](https://explorer-studio-dev.genlayer.com/address/0xA8b2467277f32562ce01c789217D995C21982BCF) | `contracts/DaoStanding.py` | `952d2995d8f12e54…` | `["0x9cCdDe5f5AAefC1387F437Baf96A1FC5E2be2F3F",30]` |
| GrantGate | [`0x869752052e4dd8A8d1B9BB50d76fF1aEAeD09332`](https://explorer-studio-dev.genlayer.com/address/0x869752052e4dd8A8d1B9BB50d76fF1aEAeD09332) | `contracts/GrantGate.py` | `2fc4477e774a6871…` | `["0x16fec6B9ce8A069c9262a209884360378037083C"]` |
| GrantGateDemo | [`0xDadfBfC4bC8a08aD7485e4A31C7A2fc1bF21AA72`](https://explorer-studio-dev.genlayer.com/address/0xDadfBfC4bC8a08aD7485e4A31C7A2fc1bF21AA72) | `contracts/GrantGate.py` | `2fc4477e774a6871…` | `["0xA8b2467277f32562ce01c789217D995C21982BCF"]` |
