/**
 * Reconciliation: when the patrol's state and the chain disagree, the chain
 * wins, and nothing is filed twice.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { type Limits, runCore } from "../src/lib/patrol/core";
import { emptyState, execKey, loadState, safeKey } from "../src/lib/patrol/state";
import { LOST_AFTER_S } from "../src/lib/patrol/txlife";
import { World } from "./mock";

const HEAD = 1_000_000;
const L: Limits = { maxWrites: 20, timeBudgetMs: 100_000, graceMs: 60_000, maxSpan: { ethereum: 1_000 }, logChunk: 1_000, initialBackfill: { ethereum: 100 } };

function setup() {
  const w = new World();
  const d = w.addDao(0);
  const lg = w.addExec(d, HEAD - 10);
  const s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 20, origin: 0, updated: "" };
  return { w, d, lg, s, key: execKey(d.chain, d.safe, lg.safeTxHash) };
}

test("a state built against another registry is set aside; the new registry is scanned and filed afresh", () => {
  const s = emptyState();
  s.registry = "0xold";
  s.checkpoints["ethereum|0xsafe"] = { block: 5, origin: 1, updated: "" };
  s.processed["k"] = { status: "filed", check_id: 3, tx: "0x", block: 5, at: "" };
  const again = loadState(JSON.parse(JSON.stringify(s)), "0xNEW");
  assert.deepEqual([again.registry, Object.keys(again.checkpoints).length, Object.keys(again.processed).length], ["0xnew", 0, 0]);
  const same = loadState(JSON.parse(JSON.stringify(s)), "0xOLD");
  assert.equal(same.processed["k"].check_id, 3);
});

test("the core refuses a state that names another registry", async () => {
  const { w, s } = setup();
  s.registry = "0xother";
  await assert.rejects(runCore(w.deps(), s, L), /state is for registry 0xother/);
});

test("a stored hash the node does not know, whose filing is on the registry, is reconciled as landed", async () => {
  const { w, s, key } = setup();
  w.plan = (fn) => (fn === "file_check" ? { script: Array(1000).fill("ACCEPTED") } : {});
  w.ms = 0;
  await runCore(w.deps(), s, L);
  const hash = s.pending[0].hash;
  w.txs.delete(hash);                     // the node forgot it; the check is on the registry
  w.ms = 0;
  const rep = await runCore(w.deps(), s, L);
  assert.deepEqual(rep.resumed.map((r) => [r.ok, r.note]), [[true, "reconciled: the expected change is on chain"]]);
  assert.equal(s.pending.length, 0);
  assert.equal(w.writes.filter((x) => x.fn === "file_check").length, 1);
  assert.equal(s.processed[key].status, "on_registry");
});

test("a stored hash the node does not know and no change on chain: lost after LOST_AFTER_S, then filed once", async () => {
  const { w, s, key } = setup();
  w.plan = (fn) => (fn === "file_check" ? { script: Array(1000).fill("PENDING"), noEffect: true } : {});
  w.ms = 0;
  await runCore(w.deps(), s, L);
  const hash = s.pending[0].hash;
  w.txs.delete(hash);
  w.plan = () => ({});
  w.ms = 0;
  await runCore(w.deps(), s, L);
  assert.equal(s.pending.length, 1, "not given up early");
  assert.equal(w.writes.filter((x) => x.fn === "file_check").length, 1);
  w.t += LOST_AFTER_S + 1;
  w.ms = 0;
  await runCore(w.deps(), s, L);
  assert.ok(s.tx_log.some((x) => x.hash === hash && x.outcome === "lost"));
  assert.equal(w.writes.filter((x) => x.fn === "file_check").length, 2);
  assert.equal(w.checks.length, 1);
  assert.equal(s.processed[key].status, "filed");
});

test("processed records are bound to the registry, so a check missing from the registry is never assumed", async () => {
  const { w, s, key } = setup();
  s.registry = "0xregistry";
  w.ms = 0;
  await runCore(w.deps(), s, L);
  assert.equal(s.processed[key].status, "filed");
  assert.equal(w.checks.length, 1);
});
