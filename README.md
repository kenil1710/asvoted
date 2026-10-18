# patrol-state

The AsVoted patrol's durable state, written only by `.github/workflows/patrol.yml` on `main`.
`patrol-state.json` holds per-Safe checkpoints (last block fully scanned, per chain and Safe),
processed executions keyed by (chain, Safe, safeTxHash), the retry queue with attempt counts,
and unmatched executions. Each patrol run that changes it is one commit.
