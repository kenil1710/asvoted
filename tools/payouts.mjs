/**
 * Did a payout really arrive? Read from the chain, never from the contract's
 * own books. Used by test/demo_paths.mjs (while claiming) and
 * tools/final_check.mjs (re-checking every recorded claim).
 *
 * A claim transaction can finalize, return ok and still pay nobody: Studio Dev
 * records a skipped message as `message_value_effects[*].skipped` and puts the
 * value back on the sender (docs/research/PAYOUT_PROBE.md). So a payout counts
 * only when the claim is FINALIZED, none of its value effects was skipped, an
 * external transfer of exactly the amount went to the recipient, and the
 * recipient's eth_getBalance moved by exactly amount - net fee of the claim.
 */
const RPC = process.env.STUDIO_RPC || "https://studio-dev.genlayer.com/api";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function rpc(method, params) {
  for (let i = 0; ; i++) {
    try {
      const res = await fetch(RPC, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
      const j = await res.json();
      if (j.error) throw new Error(`${method}: ${j.error.message}`);
      return j.result;
    } catch (e) {
      if (i >= 5) throw e;
      await sleep(3000 * (i + 1));
    }
  }
}

export const balanceOf = async (address) => BigInt(await rpc("eth_getBalance", [address, "latest"]));
export const getTx = (hash) => rpc("eth_getTransactionByHash", [hash]);

/** Polls until the transaction is FINALIZED (or another end state); null on timeout. */
export async function waitFinalized(hash, { timeoutMs = 30 * 60_000, pollMs = 5000 } = {}) {
  const t0 = Date.now();
  for (;;) {
    const tx = await getTx(hash).catch(() => null);
    if (tx && ["FINALIZED", "CANCELED", "UNDETERMINED"].includes(tx.status)) return tx;
    if (Date.now() - t0 > timeoutMs) return null;
    await sleep(pollMs);
  }
}

/** What the sender of `tx` paid in fees, net of refunds: the fee refund at
 *  finalization and the unused gas reservation of each external message,
 *  which is paid back to the sender (external_message_fee_payouts). */
export function netFee(tx) {
  const fa = tx?.data?.fee_accounting ?? {};
  const from = String(tx?.from_address ?? "").toLowerCase();
  const back = (fa.external_message_fee_payouts ?? []).filter((p) => String(p.recipient).toLowerCase() === from)
    .reduce((s, p) => s + BigInt(p.amount ?? 0), 0n);
  return BigInt(fa.paid_fee_value ?? 0) - BigInt(fa.total_refunded ?? 0) - back;
}

/** Waits until `address`'s balance has not moved for `quietMs`: the fee
 *  refunds of its earlier transactions land at their finalization, and one
 *  landing inside a claim's window would blur the before/after arithmetic. */
export async function settledBalance(address, { quietMs = 90_000, pollMs = 10_000, maxMs = 15 * 60_000 } = {}) {
  const t0 = Date.now();
  let last = await balanceOf(address), since = Date.now();
  while (Date.now() - since < quietMs && Date.now() - t0 < maxMs) {
    await sleep(pollMs);
    const b = await balanceOf(address);
    if (b !== last) { last = b; since = Date.now(); }
  }
  return last;
}

/** The transaction-level proof that `tx` sent `amount` wei to `to`. */
export function transferProof(tx, to, amount) {
  const reasons = [];
  const fa = tx?.data?.fee_accounting ?? {};
  const effects = Object.values(fa.message_value_effects ?? {});
  const events = fa.external_message_events ?? [];
  const lc = String(to).toLowerCase();
  if (tx?.status !== "FINALIZED") reasons.push(`status ${tx?.status}`);
  if (effects.length === 0) reasons.push("no value effect");
  for (const e of effects) if (e.skipped || e.skippedRefunded) reasons.push(`skipped ${e.value}${e.skippedRefunded ? ", refunded to the contract" : ""}`);
  if (effects.reduce((s, e) => s + BigInt(e.value ?? 0), 0n) !== BigInt(amount)) reasons.push(`effects total ${effects.map((e) => e.value).join("+")} != ${amount}`);
  const ev = events.filter((e) => String(e.recipient).toLowerCase() === lc);
  if (ev.length !== 1) reasons.push(`${ev.length} external transfers to ${lc}`);
  else if (!ev[0].executionRecorded) reasons.push("external transfer not executed");
  return { ok: reasons.length === 0, reasons, effects, external: ev[0] ?? null };
}

/**
 * Sends a claim through `send` (harness send of the claimer) and proves it:
 * the claimer's balance before and after, the claim finalized, the external
 * transfer and the exact balance arithmetic. Returns a record for seed-demo.json.
 */
export async function provenClaim(send, to, owed) {
  const before = await settledBalance(to);
  const out = await send("claim", []);
  const rec = { to: String(to).toLowerCase(), amount: String(owed), tx: out.hash, before: String(before) };
  if (!out.ok) return { ...rec, ok: false, reasons: [`claim ${out.status}: ${out.revertReason ?? ""}`] };
  const tx = await waitFinalized(out.hash);
  const proof = transferProof(tx, to, owed);
  const fee = netFee(tx);
  // the claim's fee refund and the transfer both land at finalization; wait for the balance to settle
  let after = await balanceOf(to);
  for (let i = 0; i < 12 && after - before !== owed - fee; i++) { await sleep(5000); after = await balanceOf(to); }
  if (after - before !== owed - fee) after = await settledBalance(to);
  const reasons = [...proof.reasons];
  if (after - before !== owed - fee) reasons.push(`balance moved ${after - before}, expected ${owed - fee} (amount ${owed} - fee ${fee})`);
  return { ...rec, after: String(after), fee: String(fee), delta: String(after - before), status: tx?.status ?? "TIMEOUT", ok: reasons.length === 0, reasons };
}
