# Deployment 829e156 (superseded, partial run)

All 9 contracts were deployed from `829e156` (round 3 fixes up to `b733e9e`), byte-identical on chain (`deploy.log`, `deployments.json`). The run was stopped on purpose for a further contract change, after the transaction in flight finished. Nothing was left mid-transaction.

- **Canonical:** 14 of 15 seeds filed, judged and ruled. Every ruling matches the `93d5be9` run: 10 AS_VOTED, 2 DEVIATES and 3 UNCLEAR, less seed 11 (ParaSwap gas refunds, Base). Seed 11 could not be read: `read_execution` ended UNDETERMINED once, then `REFUSED: RPC_UNREADABLE` five times, while the same read run locally with the contract's own code agreed (`tools/live.py`). The AS_VOTED and DEVIATES checks were CONTESTABLE (72 h window) when the run stopped, and nobody finalizes them. Logs: `seed-canonical-run1.log`, `seed-canonical-run2.log`.
- **Demo:** stopped during setup, after the refusals, the claims, the pledges and the first GrantGate request. The last transaction was a `read_proposal` (FINALIZED, vote_id 17). No check was filed. A first attempt died on a local DNS failure. Log: `demo-run-partial.log`.
- **Demo registry balance:** the pledges posted in this run (5 + 2 GEN, and 1 GEN credited back to a non-controller) stay in that registry's books. They are not drained, because the registry is superseded.
