/**
 * Patrol recovery: durable per-Safe checkpoints, bounded backfill, idempotent
 * processing, the retry queue, and outages.
 *   cd frontend && npm test
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { type Limits, runCore } from "../src/lib/patrol/core";
import { type PatrolState, backoff, emptyState, execKey, loadState, safeKey } from "../src/lib/patrol/state";
import { World } from "./mock";

const L: Limits = { maxWrites: 100, timeBudgetMs: 10_000_000, maxSpan: { ethereum: 1_000 }, logChunk: 250, initialBackfill: { ethereum: 3_000 } };
const HEAD = 1_000_000;
/** One run with the state round-tripped through JSON, as the Action stores it. */
async function run(w: World, s: PatrolState, lim: Limits = L) {
  w.ms = 0;
  const rep = await runCore(w.deps(), s, lim);
  return { rep, state: loadState(JSON.parse(JSON.stringify(s))) };
}

test("first run starts at the initial backfill and scans at most maxSpan blocks", async () => {
  const w = new World();
  const d = w.addDao(0);
  const { rep, state } = await run(w, emptyState());
  const cp = state.checkpoints[safeKey(d.chain, d.safe)];
  assert.equal(cp.origin, HEAD - 3_000);
  assert.equal(cp.block, HEAD - 3_000 + 1_000 - 1);
  assert.deepEqual(rep.scans.map((s) => [s.from, s.to, s.complete]), [[HEAD - 3_000, HEAD - 2_001, true]]);
  assert.equal(w.logCalls.length, 4); // 1000 blocks in chunks of 250
});

test("backfill resumes from the checkpoint each run until the finalized head, with no gap or overlap", async () => {
  const w = new World();
  const d = w.addDao(0);
  for (const b of [HEAD - 2_999, HEAD - 2_001, HEAD - 2_000, HEAD - 1, HEAD]) w.addExec(d, b);
  let s = emptyState();
  for (let i = 0; i < 5; i++) s = (await run(w, s)).state;
  const ranges = w.logCalls.map((c) => [c.from, c.to]);
  for (let i = 1; i < ranges.length; i++) assert.equal(ranges[i][0], ranges[i - 1][1] + 1, "contiguous");
  assert.equal(ranges[0][0], HEAD - 3_000);
  assert.equal(ranges.at(-1)![1], HEAD);
  assert.equal(s.checkpoints[safeKey(d.chain, d.safe)].block, HEAD);
  assert.deepEqual(w.filedTxs().length, 5);
  assert.equal(new Set(w.filedTxs()).size, 5);
});

test("nothing past the finalized block is scanned; it is picked up once finalized", async () => {
  const w = new World();
  const d = w.addDao(0);
  let s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 10, origin: 0, updated: "" };
  w.addExec(d, HEAD + 5);
  s = (await run(w, s)).state;
  assert.equal(s.checkpoints[safeKey(d.chain, d.safe)].block, HEAD);
  assert.equal(w.filedTxs().length, 0);
  w.heads.ethereum = HEAD + 20;
  s = (await run(w, s)).state;
  assert.equal(w.filedTxs().length, 1);
});

test("an RPC outage holds the checkpoint at the last range read in full; the next run resumes there", async () => {
  const w = new World();
  const d = w.addDao(0);
  const sk = safeKey(d.chain, d.safe);
  let s = emptyState();
  s.checkpoints[sk] = { block: HEAD - 1_000, origin: 0, updated: "" };
  w.addExec(d, HEAD - 900);
  w.addExec(d, HEAD - 600);
  w.failLogs = (_c, _s, from) => from > HEAD - 750;
  let r = await run(w, s);
  s = r.state;
  assert.equal(s.checkpoints[sk].block, HEAD - 750);
  assert.equal(r.rep.scans[0].complete, false);
  assert.equal(w.filedTxs().length, 1);
  w.failLogs = () => false;
  r = await run(w, s);
  s = r.state;
  assert.equal(r.rep.scans[0].from, HEAD - 749);
  assert.equal(s.checkpoints[sk].block, HEAD);
  assert.equal(w.filedTxs().length, 2);
});

test("a total outage (finalized head unreadable) leaves every checkpoint where it was", async () => {
  const w = new World();
  const d = w.addDao(0);
  const s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 500, origin: 0, updated: "" };
  const deps = w.deps({ finalized: async () => { throw new Error("down"); } });
  await runCore(deps, s, L);
  assert.equal(s.checkpoints[safeKey(d.chain, d.safe)].block, HEAD - 500);
});

test("idempotent: an execution already on the registry is recorded, never filed", async () => {
  const w = new World();
  const d = w.addDao(0);
  const lg = w.addExec(d, HEAD - 10);
  w.addCheck({ chain: d.chain, safe: d.safe, tx: lg.tx, filer: "0xsomeoneelse" });
  const s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 20, origin: 0, updated: "" };
  const { rep, state } = await run(w, s);
  assert.equal(w.filedTxs().length, 0);
  assert.equal(rep.already_checked, 1);
  assert.equal(state.processed[execKey(d.chain, d.safe, lg.safeTxHash)].status, "on_registry");
});

test("idempotent: re-scanning a span (checkpoint lost) never files the same execution twice", async () => {
  const w = new World();
  const d = w.addDao(0);
  w.addExec(d, HEAD - 10);
  w.addExec(d, HEAD - 5);
  let s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 20, origin: 0, updated: "" };
  s = (await run(w, s)).state;
  assert.equal(w.filedTxs().length, 2);
  // the checkpoint and processed map are lost: the registry still prevents a second filing
  s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 20, origin: 0, updated: "" };
  s = (await run(w, s)).state;
  assert.equal(w.filedTxs().length, 2);
  assert.equal(new Set(w.filedTxs()).size, 2);
});

test("a failure goes to the persistent retry queue with an attempt count and backoff; the checkpoint still advances", async () => {
  const w = new World();
  const d = w.addDao(0);
  const lg = w.addExec(d, HEAD - 10);
  const sk = safeKey(d.chain, d.safe);
  let s = emptyState();
  s.checkpoints[sk] = { block: HEAD - 20, origin: 0, updated: "" };
  w.failMatch = () => "hub answered 502";
  s = (await run(w, s)).state;
  assert.equal(s.checkpoints[sk].block, HEAD);
  assert.equal(s.retry.length, 1);
  assert.deepEqual([s.retry[0].attempts, s.retry[0].last_error, s.retry[0].next_at], [1, "hub answered 502", w.t + backoff(1)]);
  // not retried before its backoff
  s = (await run(w, s)).state;
  assert.equal(s.retry[0].attempts, 1);
  w.t += backoff(1);
  s = (await run(w, s)).state;
  assert.equal(s.retry[0].attempts, 2);
  assert.equal(s.retry[0].next_at, w.t + backoff(2));
  w.failMatch = () => null;
  w.t += backoff(2);
  s = (await run(w, s)).state;
  assert.equal(s.retry.length, 0);
  assert.deepEqual(w.filedTxs(), [lg.tx]);
  assert.equal(s.processed[execKey(d.chain, d.safe, lg.safeTxHash)].status, "filed");
});

test("a failed write is queued, and the retry resumes the pipeline without repeating finished steps", async () => {
  const w = new World();
  const d = w.addDao(0);
  w.addExec(d, HEAD - 10);
  let s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 20, origin: 0, updated: "" };
  w.failWrite = (fn) => (fn === "file_check" ? "reverted: busy" : null);
  s = (await run(w, s)).state;
  assert.equal(s.retry[0].attempts, 1);
  w.failWrite = () => null;
  w.t += backoff(1);
  s = (await run(w, s)).state;
  assert.deepEqual(w.writes.map((x) => x.fn), ["read_execution", "read_proposal", "file_check", "file_check"]);
  assert.equal(w.checks.length, 1);
});

test("out of write budget: the rest of the span is deferred (attempts 0), the checkpoint advances, later runs file each once", async () => {
  const w = new World();
  const d = w.addDao(0);
  for (let i = 0; i < 7; i++) w.addExec(d, HEAD - 100 + i);
  const sk = safeKey(d.chain, d.safe);
  let s = emptyState();
  s.checkpoints[sk] = { block: HEAD - 200, origin: 0, updated: "" };
  const lim = { ...L, maxWrites: 6 }; // two executions per run
  s = (await run(w, s, lim)).state;
  assert.equal(s.checkpoints[sk].block, HEAD);
  assert.equal(s.retry.length, 5);
  assert.ok(s.retry.every((e) => e.attempts === 0));
  // later runs also judge and rule the new filings, so they file fewer per run
  for (let i = 0; i < 12 && s.retry.length > 0; i++) s = (await run(w, s, lim)).state;
  assert.equal(s.retry.length, 0);
  assert.equal(w.filedTxs().length, 7);
  assert.equal(new Set(w.filedTxs()).size, 7);
});

test("an unmatched execution is recorded visibly and never retried or filed", async () => {
  const w = new World();
  const d = w.addDao(0);
  const lg = w.addExec(d, HEAD - 10);
  w.unmatched = () => "no passed proposal names an address this execution touches";
  let s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 20, origin: 0, updated: "" };
  s = (await run(w, s)).state;
  assert.equal(s.unmatched.length, 1);
  assert.equal(s.unmatched[0].tx, lg.tx);
  assert.equal(s.retry.length, 0);
  assert.equal(s.processed[execKey(d.chain, d.safe, lg.safeTxHash)].status, "unmatched");
  assert.equal(w.filedTxs().length, 0);
});

test("a malformed state document loads as empty rather than failing the run", () => {
  assert.deepEqual(loadState("garbage").checkpoints, {});
  assert.deepEqual(loadState({ checkpoints: { "a|b": { block: -3 } }, retry: "x" }).retry, []);
  assert.deepEqual(loadState({ checkpoints: { "a|b": { block: -3 } } }).checkpoints, {});
});
