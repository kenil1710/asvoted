# Demo run on 0x9ce6CEAA (superseded)

This demo run on AsVotedRegistryDemo `0x9ce6CEAA2aEB76713DcE26b88b298bdAa0d4F265` (deployed from `b836f41`) passed 15 of 33 expectations. The script filed all ten checks before judging any of them. Each filing now waits for FINALIZED on several writes, so judging started after the 600 s judge windows had closed, and every `rule` was refused with `JUDGED_AFTER_THE_DEADLINE_USE_EXPIRE`.

The script now judges and rules each check right after filing it. A fresh demo set was deployed from the same commit `b836f41`. The 7.9 GEN still held by this registry is in pledges and in the stakes of unsettled checks; nothing on the canonical registry is affected.
