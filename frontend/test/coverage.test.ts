/**
 * The coverage heartbeat the patrol records on the registry
 * (record_coverage), which DaoStanding needs fresh before it can say
 * COMPLIANT.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { type Limits, runCore } from "../src/lib/patrol/core";
import { emptyState, safeKey } from "../src/lib/patrol/state";
import { PATROL, World } from "./mock";

const HEAD = 1_000_000;
const L: Limits = { maxWrites: 50, timeBudgetMs: 1e9, maxSpan: { ethereum: 1_000 }, logChunk: 1_000, initialBackfill: { ethereum: 500 } };
const beats = (w: World) => w.writes.filter((x) => x.fn === "record_coverage").map((x) => JSON.parse(String(x.args[0])));

test("after a scan the patrol records, per DAO, the checkpoint block and its timestamp", async () => {
  const w = new World();
  const a = w.addDao(0), b = w.addDao(1);
  await runCore(w.deps(), emptyState(), L);
  assert.deepEqual(beats(w), [[[a.dao_id, HEAD, w.t - 900], [b.dao_id, HEAD, w.t - 900]]]);
  assert.deepEqual(w.coverage.get(`${a.dao_id}|${PATROL}`), { block: HEAD, block_time: w.t - 900, recorded_at: w.t });
});

test("during backfill the heartbeat covers only what has been scanned, with that block's own time", async () => {
  const w = new World();
  const d = w.addDao(0);
  const s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 5_000, origin: HEAD - 5_000, updated: "" };
  await runCore(w.deps(), s, L);
  const blk = HEAD - 4_000;
  assert.deepEqual(beats(w), [[[d.dao_id, blk, w.t - 900 - 4_000 * 12]]]);
});

test("a queued execution holds the heartbeat back to the block before it", async () => {
  const w = new World();
  const d = w.addDao(0);
  w.addExec(d, HEAD - 200);
  w.failMatch = () => "hub down";
  const s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 300, origin: HEAD - 600, updated: "" };
  await runCore(w.deps(), s, L);
  assert.equal(s.checkpoints[safeKey(d.chain, d.safe)].block, HEAD);
  assert.deepEqual(beats(w).flat().map((e: number[]) => e[1]), [HEAD - 201]);
});

test("an unchanged heartbeat is not resent", async () => {
  const w = new World();
  w.addDao(0);
  const s = emptyState();
  await runCore(w.deps(), s, L);
  await runCore(w.deps(), s, L);
  assert.equal(beats(w).length, 1);
  w.heads.ethereum += 10;
  await runCore(w.deps(), s, L);
  assert.equal(beats(w).length, 2);
});

test("filings cannot use up the write held back for the heartbeat", async () => {
  const w = new World();
  const d = w.addDao(0);
  for (let i = 0; i < 5; i++) w.addExec(d, HEAD - 50 + i);
  const s = emptyState();
  await runCore(w.deps(), s, { ...L, maxWrites: 4 });
  assert.equal(w.writes.length, 4);
  assert.equal(w.writes.at(-1)!.fn, "record_coverage");
});

test("more than 50 DAOs: the heartbeat is split into calls of at most 50 entries", async () => {
  const w = new World();
  for (let i = 0; i < 120; i++) w.addDao(i);
  await runCore(w.deps(), emptyState(), L);
  assert.deepEqual(beats(w).map((b) => b.length), [50, 50, 20]);
});
