# Deployment 07ff3a3 (superseded: payouts never left the contract)

All 9 contracts were deployed from `07ff3a3` and verified byte-identical on chain (`deployments.json`, `ADDRESSES.md`). The 15 canonical seeds were filed and finalized (`SEEDS.md`, `seed-canonical.json`, `seed-run*.log`), and the demo ran every path (`seed-demo.json`, `demo-run*.log`, `FINAL_CHECK.md`).

**Why it was replaced:** `claim()` paid with `gl.chain.Account(who).emit_transfer(...)`, an internal message that only an Intelligent Contract can receive. For every claimer (all of them EOAs), Studio Dev recorded the transfer as skipped and refunded the value to the registry. Every claim finalized and was marked paid in the books, but no GEN reached anyone. The note in these logs ("queued and not delivered") was wrong; see the correction at the top of `demo-run.log`. Cause, probe and fix: [docs/research/PAYOUT_PROBE.md](../../research/PAYOUT_PROBE.md).

## Stuck GEN

No method can send this GEN out now: each registry's books count it as already claimed. Read with `eth_getBalance` on 2026-10-17T15:17:43Z:

| Deployment | Registry | Address | eth_getBalance (wei) |
|---|---|---|---|
| 07ff3a3 | canonical | `0x4Ec22423528e64B4f1d41B7F647c0BD42464a30C` | 1500000000000000000 |
| 07ff3a3 | demo | `0x65dB1CD4b79Bc87e5d6dbA315ea8F4239eAea028` | 13100000000000000002 |
| 93d5be9 | canonical | `0x2B4ac2D50978fc4937E9a479e4706688a6c5cCdc` | 1500000000000000000 |
| 93d5be9 | demo | `0x01AB66898cB6f1E949449f4a9B3D384f1079ea93` | 9200000000000000001 |
| 829e156 | canonical | `0x70e5Cfd6eE3e980792DF7588C501C2b547619C87` | 1400000000000000000 |
| 829e156 | demo | `0xbe11F753e6DC262097a6dF7d65A1bF1f01ca80c6` | 9700000000000000000 |
| 7a74665 | canonical | `0x1C2891FE54a5CfE98436F439e40A3043050eFF44` | 1500000000000000000 |
| 7a74665 | demo | `0x8B904F094F5b2A25C5004Ab09301dc9041c17B7a` | 12800000000000000002 |

The 07ff3a3 demo registry's 13100000000000000002 wei is exactly everything it received. Its books say all of it was claimed (`held_now` 0), yet all of it is still in the contract.
