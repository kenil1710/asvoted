# Demo run on 0x9ce6CEAA (superseded)

This demo run on AsVotedRegistryDemo `0x9ce6CEAA2aEB76713DcE26b88b298bdAa0d4F265` (deployed from `b836f41`) passed 15 of 33 expectations. The script filed all ten checks before judging any of them. Each filing now waits for FINALIZED on several writes, so judging started after the 600 s judge windows had closed, and every `rule` was refused with `JUDGED_AFTER_THE_DEADLINE_USE_EXPIRE`.

The script now judges and rules each check right after filing it. A fresh demo set was deployed from the same commit `b836f41`. It was then settled with its own permissionless exits (`test/drain_superseded.mjs`, log in [drain.log](drain.log)):

- the nine open checks were expired (FINAL UNCLEAR, stakes refunded);
- both pledges were withdrawn (5.1 and 2.0 GEN);
- the filer, filer2 and DAO accounts claimed 0.5, 0.3 and 7.1 GEN, and each external transfer arrived at its recipient.

The registry's books hold 0 and its eth_getBalance is 0.
