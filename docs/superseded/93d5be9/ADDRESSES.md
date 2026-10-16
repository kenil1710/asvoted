# Addresses (GenLayer Studio Dev, chain 61997)

Every contract below was deployed from commit `93d5be9a66b98ba6d0b0e5f36b8f44562c30a83b`. `tools/verify_source.mjs` reads each one back with `gen_getContractCode` and compares it byte for byte with that commit.

| Contract | Address | Source | sha256 | Constructor |
|---|---|---|---|---|
| ExecReader | [`0x31EabbC7978d784e9EeaAf5c4FFD82eD9BC5eeB9`](https://explorer-studio-dev.genlayer.com/address/0x31EabbC7978d784e9EeaAf5c4FFD82eD9BC5eeB9) | `contracts/ExecReader.py` | `4909d23888c4da17…` | `[]` |
| VoteReader | [`0xe00Cc656c9cED6F61505E9b7440Dad2B690C19FB`](https://explorer-studio-dev.genlayer.com/address/0xe00Cc656c9cED6F61505E9b7440Dad2B690C19FB) | `contracts/VoteReader.py` | `4ee549d44fd54eda…` | `[]` |
| AsVotedJudge | [`0x4fFdAf25Fb27ba9bCeDAA0f94d93D14993a69Fb4`](https://explorer-studio-dev.genlayer.com/address/0x4fFdAf25Fb27ba9bCeDAA0f94d93D14993a69Fb4) | `contracts/AsVotedJudge.py` | `4c123527d890961d…` | `[]` |
| AsVotedRegistry | [`0x2B4ac2D50978fc4937E9a479e4706688a6c5cCdc`](https://explorer-studio-dev.genlayer.com/address/0x2B4ac2D50978fc4937E9a479e4706688a6c5cCdc) | `contracts/AsVotedRegistry.py` | `2810e1bb0f9a2e89…` | `["CANONICAL","0x31EabbC7978d784e9EeaAf5c4FFD82eD9BC5eeB9","0xe00Cc656c9cED6F61505E9b7440Dad2B690C19FB","0x4fFdAf25Fb27ba9bCeDAA0f94d93D14993a69Fb4",""]` |
| AsVotedRegistryDemo | [`0x01AB66898cB6f1E949449f4a9B3D384f1079ea93`](https://explorer-studio-dev.genlayer.com/address/0x01AB66898cB6f1E949449f4a9B3D384f1079ea93) | `contracts/AsVotedRegistry.py` | `2810e1bb0f9a2e89…` | `["DEMO","0x31EabbC7978d784e9EeaAf5c4FFD82eD9BC5eeB9","0xe00Cc656c9cED6F61505E9b7440Dad2B690C19FB","0x4fFdAf25Fb27ba9bCeDAA0f94d93D14993a69Fb4","0x88fe8ab95e561a57ce2dd375355858a0893d5d2d"]` |
| DaoStanding | [`0x2dee7BBc3e09E058B3AbEdfEeD2a2334ba69b870`](https://explorer-studio-dev.genlayer.com/address/0x2dee7BBc3e09E058B3AbEdfEeD2a2334ba69b870) | `contracts/DaoStanding.py` | `952d2995d8f12e54…` | `["0x2B4ac2D50978fc4937E9a479e4706688a6c5cCdc",30]` |
| DaoStandingDemo | [`0x5115162037A6aB89Bc70862b9C535e13f26D3693`](https://explorer-studio-dev.genlayer.com/address/0x5115162037A6aB89Bc70862b9C535e13f26D3693) | `contracts/DaoStanding.py` | `952d2995d8f12e54…` | `["0x01AB66898cB6f1E949449f4a9B3D384f1079ea93",30]` |
| GrantGate | [`0x31EAFAAbd993be7F837569cf8aecBb44CaA233D4`](https://explorer-studio-dev.genlayer.com/address/0x31EAFAAbd993be7F837569cf8aecBb44CaA233D4) | `contracts/GrantGate.py` | `2fc4477e774a6871…` | `["0x2dee7BBc3e09E058B3AbEdfEeD2a2334ba69b870"]` |
| GrantGateDemo | [`0x8e437a04970bc587adaE2764F8E18A171fe1d946`](https://explorer-studio-dev.genlayer.com/address/0x8e437a04970bc587adaE2764F8E18A171fe1d946) | `contracts/GrantGate.py` | `2fc4477e774a6871…` | `["0x5115162037A6aB89Bc70862b9C535e13f26D3693"]` |
