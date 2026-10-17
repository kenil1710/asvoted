# Payout probe: which send reaches an EOA on Studio Dev

Run 2026-10-17 against https://studio-dev.genlayer.com/api with a throwaway contract that is not part of this repo (source below) and a throwaway funded key.

## Before the fix

Every `claim()` on the old demo registry `0x65dB1CD4b79Bc87e5d6dbA315ea8F4239eAea028` used `gl.chain.Account(who).emit_transfer(...)`. All 8 claims in the old `demo-run.log` finalized, but the transaction records show `message_value_effects: {skipped: true, skippedRefunded: true, declaredBudget: 0}`, so none of the value left the contract. `eth_getBalance` of the demo registry is still 13100000000000000002, which is everything it ever received.

~/dev/sentinel (`Sentinel.claim`) and ~/dev/_ref/fairdrop (`FairDrop._pay`) use the same call, and their claims were skipped the same way:

| repo | tx | value | effect |
|---|---|---|---|
| sentinel | 0xdb92b3684314127d9d2d8777fbd5d66ab91bc5b61007fe2156e93ea0c45dafa9 | 2.45 GEN | skipped, refunded |
| sentinel | 0x3ca49af9a7b316bcecd933fb3a2c8aeedbf00064aee719e489a06e30f163ce58 | 0.1 GEN | skipped, refunded |
| fairdrop | 0xacc338367f0e6f560e9ca768a29e0d9edabb10edfdbce6be0822d6b7cd0f59e8 | 0.35 GEN | skipped, refunded |
| fairdrop | 0x72345d72a02c83e9dc1e7c2ebaea1087dbc2032a6a3d0b78ecbcfffb83f0c2c9 | 3.2 GEN | skipped, refunded |

Neither repo has a send pattern that delivers.

## Cause

`gl.chain.Account(a).emit_transfer` is `get_at(a).emit_transfer`, which posts a `PostMessage`: an internal message to another Intelligent Contract. An EOA has no contract to receive it, so the message is skipped and its value refunded to the sender. A send to an EOA has to be an external message (`EthSend`), which is issued through an `@gl.evm.contract_interface` handle, as in docs.genlayer.com/developers/intelligent-contracts/features/value-transfers ("Sending Value to an EOA or EVM Contract").

## Probe

Probe contract `0x19cA4A039e74051aF5A826d2dD93eeeBFc493E04`, funded with 1 GEN (tx 0xb241b79c2f136990980e77efb80013819f6e6e14c4047338e843bcdb0220cf79). It sent 0.01 GEN to each of two fresh EOAs that had never been used:

| variant | tx | recipient | balance before | balance after | message effect |
|---|---|---|---|---|---|
| `gl.chain.Account(to).emit_transfer(v)` | 0x8b02b8063601f8133ee2f365dc4ac8d42ef516df98482082509ca9931c889e56 | 0xC954879482C383e835c0E3Aa4e8e045f64ea8E76 | 0 | **0** | skipped, refunded |
| `_Recipient(to).emit_transfer(value=v)` (EVM interface) | 0x34b012872fe2a7d814db40278e15239624c560226f49b7b10e31812e3154be72 | 0xc17f157EB425d6a7ad2ed7897bD85a175D211bB0 | 0 | **10000000000000000** | external message, executed |

The probe's own balance went from 1000000000000000000 to 990000000000000000, down by exactly the one delivered transfer.

```python
# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *


@gl.evm.contract_interface
class _Recipient:
    class View:
        pass

    class Write:
        pass


class SendProbe(gl.contract.Contract):
    n: u256

    def __init__(self):
        self.n = u256(0)

    @gl.public.write.payable
    def fund(self) -> None:
        self.n = u256(int(self.n) + 1)

    @gl.public.write
    def send_internal(self, to: str, amount: int) -> None:
        gl.chain.Account(Address(to)).emit_transfer(u256(amount))

    @gl.public.write
    def send_external(self, to: str, amount: int) -> None:
        _Recipient(Address(to)).emit_transfer(value=u256(amount))

    @gl.public.view
    def bal(self) -> int:
        return int(self.balance)
```
