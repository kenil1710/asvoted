/**
 * Pagination: every page of get_daos and get_open_checks, the registry's
 * per-call scan cap, and cursors that carry a bounded run over to the next.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { type Limits, runCore } from "../src/lib/patrol/core";
import { type PatrolState, emptyState, loadState, safeKey } from "../src/lib/patrol/state";
import { MAX_PAGE, PATROL, SCAN_CAP, World } from "./mock";

const HEAD = 1_000_000;
const L: Limits = { maxWrites: 10_000, timeBudgetMs: 10_000_000, maxSpan: { ethereum: 1_000 }, logChunk: 1_000, initialBackfill: { ethereum: 500 } };
async function run(w: World, s: PatrolState, lim: Limits = L) {
  w.ms = 0;
  const rep = await runCore(w.deps(), s, lim);
  return { rep, state: loadState(JSON.parse(JSON.stringify(s))) };
}
const calls = (w: World, fn: string) => w.views.filter((v) => v.fn === fn).map((v) => v.args[0]);

test("more than 50 DAOs: every page of get_daos is read and every Safe is scanned and filed", async () => {
  const w = new World();
  for (let i = 0; i < 137; i++) w.addExec(w.addDao(i), HEAD - 100);
  const { rep, state } = await run(w, emptyState());
  assert.ok(137 > MAX_PAGE);
  assert.deepEqual(calls(w, "get_daos"), [0, 50, 100]);
  assert.equal(rep.daos_watched, 137);
  assert.equal(Object.keys(state.checkpoints).length, 137);
  assert.equal(new Set(w.filedTxs()).size, 137);
  assert.equal(w.filedTxs().length, 137);
});

test("more than 50 DAOs over time-bounded runs: the round-robin cursor reaches every DAO, none skipped, none twice", async () => {
  const w = new World();
  const daos = [];
  for (let i = 0; i < 137; i++) { const d = w.addDao(i); daos.push(d); w.addExec(d, HEAD - 100); }
  w.logMs = 1_000;
  w.writeMs = 0;
  const lim = { ...L, timeBudgetMs: 40_000 }; // ~40 Safes per run
  let s = emptyState();
  const cursors: number[] = [];
  for (let i = 0; i < 4; i++) { s = (await run(w, s, lim)).state; cursors.push(s.cursors.daos); }
  // run 4 scans the last 17, then finds every other Safe at the head and completes the pass
  assert.deepEqual(cursors, [40, 80, 120, 120]);
  for (const d of daos) assert.ok(s.checkpoints[safeKey(d.chain, d.safe)], d.space);
  assert.equal(w.filedTxs().length, 137);
  assert.equal(new Set(w.filedTxs()).size, 137);
});

function historical(w: World, n: number, openAt: number[], filer = PATROL) {
  for (let i = 1; i <= n; i++) {
    const open = openAt.includes(i);
    w.addCheck({ status: open ? "CONTESTABLE" : "FINAL", filer, contest_deadline: w.t - 10 });
  }
}

test("more than 500 historical checks: get_open_checks is followed past the scan cap, through empty pages, to done", async () => {
  const w = new World();
  const openAt = [3, 499, 500, 501, 777, 1000, 1001, 1499, 1650];
  historical(w, 1650, openAt);
  const { rep, state } = await run(w, emptyState());
  assert.ok(1650 > SCAN_CAP);
  assert.deepEqual(calls(w, "get_open_checks"), [0, 500, 1000, 1500]);
  assert.equal(rep.open_seen, openAt.length);
  assert.deepEqual(w.writes.filter((x) => x.fn === "finalize").map((x) => x.args[0]), openAt);
  assert.equal(state.cursors.open_checks, 0);
});

test("more than 500 historical checks and more than 50 open: pages of 50 are followed too", async () => {
  const w = new World();
  const openAt = Array.from({ length: 180 }, (_, i) => 400 + i * 4); // 400..1116
  historical(w, 1200, openAt);
  await run(w, emptyState());
  assert.deepEqual(w.writes.filter((x) => x.fn === "finalize").map((x) => x.args[0]), openAt);
});

test("open checks over write-bounded runs: the cursor carries over and every check is closed exactly once", async () => {
  const w = new World();
  const openAt = [10, 520, 530, 1020, 1100, 1180];
  historical(w, 1200, openAt);
  const lim = { ...L, maxWrites: 3 }; // two closings and the heartbeat
  let s = emptyState();
  const seen: number[] = [];
  for (let i = 0; i < 6; i++) { s = (await run(w, s, lim)).state; seen.push(s.cursors.open_checks); }
  const fin = w.writes.filter((x) => x.fn === "finalize").map((x) => Number(x.args[0]));
  assert.deepEqual(fin, openAt);
  assert.equal(new Set(fin).size, openAt.length);
  assert.deepEqual(seen.slice(0, 3), [529, 1029, 0]);
});

test("a run that starts mid-list wraps around to the checks before its cursor", async () => {
  const w = new World();
  historical(w, 700, [5, 650]);
  const s = emptyState();
  s.cursors.open_checks = 600;
  await run(w, s);
  assert.deepEqual(w.writes.filter((x) => x.fn === "finalize").map((x) => x.args[0]), [650, 5]);
  assert.equal(s.cursors.open_checks, 600);
});

test("other filers' open checks are read but never touched", async () => {
  const w = new World();
  historical(w, 600, [2, 550], "0xsomeoneelse");
  const { rep } = await run(w, emptyState());
  assert.equal(rep.open_seen, 2);
  assert.equal(w.writes.length, 0);
});
