/**
 * Transaction lifecycle: ACCEPTED is never success; success is FINALIZED +
 * GenVM SUCCESS + the expected state change read back; an undecided
 * transaction is resumed from its stored hash and never sent twice.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { type Limits, runCore } from "../src/lib/patrol/core";
import { type PatrolState, emptyState, execKey, loadState, safeKey } from "../src/lib/patrol/state";
import { Lifecycle } from "../src/lib/patrol/txlife";
import { World } from "./mock";

const HEAD = 1_000_000;
const L: Limits = { maxWrites: 20, timeBudgetMs: 100_000, graceMs: 60_000, maxSpan: { ethereum: 1_000 }, logChunk: 1_000, initialBackfill: { ethereum: 100 } };
const ACCEPTED_FOREVER = Array(1000).fill("ACCEPTED");
const fns = (w: World) => w.writes.map((x) => x.fn).filter((f) => f !== "record_coverage");

function setup() {
  const w = new World();
  const d = w.addDao(0);
  const lg = w.addExec(d, HEAD - 10);
  const s = emptyState();
  s.checkpoints[safeKey(d.chain, d.safe)] = { block: HEAD - 20, origin: 0, updated: "" };
  return { w, d, lg, s, key: execKey(d.chain, d.safe, lg.safeTxHash) };
}
async function run(w: World, s: PatrolState, lim = L) {
  w.ms = 0;
  const rep = await runCore(w.deps(), s, lim);
  return { rep, state: loadState(JSON.parse(JSON.stringify(s))) };
}

test("ACCEPTED is not success: a file_check still ACCEPTED at the end of the run is stored as pending, not counted as filed", async () => {
  const { w, s, key } = setup();
  w.plan = (fn) => (fn === "file_check" ? { script: ACCEPTED_FOREVER } : {});
  const { rep, state } = await run(w, s);
  assert.equal(rep.filed, 0);
  assert.equal(state.processed[key], undefined);
  assert.deepEqual(state.pending.map((p) => [p.id, p.fn]), [[`file_check|${key}`, "file_check"]]);
  assert.equal(state.retry[0].attempts, 0);            // a deferral, not a failure
  assert.match(rep.writes.find((x) => x.fn === "file_check")!.note, /ACCEPTED when the run ended/);
});

test("an uncertain transaction is resumed from its stored hash in the next run and never sent twice", async () => {
  const { w, s, key } = setup();
  w.plan = (fn) => (fn === "file_check" ? { script: ACCEPTED_FOREVER } : {});
  let st = (await run(w, s)).state;
  const hash = st.pending[0].hash;
  // it finalizes between runs
  const t = w.txs.get(hash)!;
  t.script = ["FINALIZED"]; t.polls = 0;
  const r = await run(w, st);
  st = r.state;
  assert.deepEqual(r.rep.resumed.map((x) => [x.hash, x.ok]), [[hash, true]]);
  assert.equal(st.pending.length, 0);
  assert.deepEqual(fns(w).filter((f) => f === "file_check"), ["file_check"]);
  assert.equal(w.checks.length, 1);
  assert.equal(st.processed[key].check_id, 1);
  assert.equal(st.retry.length, 0);
  assert.ok(st.tx_log.some((x) => x.hash === hash && x.outcome === "finalized, verified"));
});

test("still in flight across several runs: followed each time, sent once", async () => {
  const { w, s } = setup();
  w.plan = (fn) => (fn === "file_check" ? { script: ACCEPTED_FOREVER } : {});
  let st = s;
  for (let i = 0; i < 4; i++) st = (await run(w, st)).state;
  assert.equal(fns(w).filter((f) => f === "file_check").length, 1);
  assert.equal(st.pending.length, 1);
});

test("FINALIZED with a GenVM error is a failure: retry queue with an attempt counted, nothing pending", async () => {
  const { w, s, key } = setup();
  w.plan = (fn) => (fn === "file_check" ? { exec: "ERROR", error: "REFUSED: X", noEffect: true } : {});
  const { state, rep } = await run(w, s);
  assert.equal(state.pending.length, 0);
  assert.equal(state.retry[0].attempts, 1);
  assert.match(state.retry[0].last_error, /FINALIZED with ERROR: REFUSED: X/);
  assert.equal(state.processed[key], undefined);
  assert.equal(rep.filed, 0);
});

test("FINALIZED with a rollback is a failure", async () => {
  const { w, s } = setup();
  w.plan = (fn) => (fn === "read_execution" ? { rolledBack: true } : {});
  const { state } = await run(w, s);
  assert.match(state.retry[0].last_error, /read_execution: FINALIZED with rollback/);
  assert.deepEqual(fns(w), ["read_execution"]);
});

test("FINALIZED and SUCCESS but the registry shows no check (a refused payable call) is a failure", async () => {
  const { w, s, key } = setup();
  w.plan = (fn) => (fn === "file_check" ? { noEffect: true } : {});
  const { state } = await run(w, s);
  assert.match(state.retry[0].last_error, /expected state change is not on chain/);
  assert.equal(state.processed[key], undefined);
  assert.equal(w.checks.length, 0);
});

test("UNDETERMINED and CANCELED are failures", async () => {
  for (const status of ["UNDETERMINED", "CANCELED"]) {
    const { w, s } = setup();
    w.plan = (fn) => (fn === "read_execution" ? { script: ["PROPOSING", status], noEffect: true } : {});
    const { state } = await run(w, s);
    assert.match(state.retry[0].last_error, new RegExp(`read_execution: ${status}`));
    assert.equal(state.pending.length, 0);
  }
});

test("a submit that fails leaves nothing pending and counts an attempt", async () => {
  const { w, s } = setup();
  w.failSubmit = true;
  const { state } = await run(w, s);
  assert.equal(state.pending.length, 0);
  assert.match(state.retry[0].last_error, /submit failed/);
});

test("ACCEPTED then FINALIZED within the run: success only once FINALIZED and verified", async () => {
  const { w, s, key } = setup();
  w.plan = (fn) => (fn === "file_check" ? { script: ["PENDING", "ACCEPTED", "ACCEPTED", "FINALIZED"] } : {});
  const { state, rep } = await run(w, s);
  assert.equal(rep.filed, 1);
  assert.equal(state.processed[key].status, "filed");
  assert.equal(w.txs.get(rep.writes.find((x) => x.fn === "file_check")!.hash!)!.polls, 4);
});

test("a hash lost with the state (run killed): the registry is read first, so the landed filing is not repeated", async () => {
  const { w, s, key } = setup();
  w.plan = (fn) => (fn === "file_check" ? { script: ACCEPTED_FOREVER } : {});
  await run(w, s);
  // the state of that run never reached the branch
  const fresh = emptyState();
  fresh.checkpoints = { ...s.checkpoints, [Object.keys(s.checkpoints)[0]]: { block: HEAD - 20, origin: 0, updated: "" } };
  const { state } = await run(w, fresh);
  assert.equal(fns(w).filter((f) => f === "file_check").length, 1);
  assert.equal(state.processed[key].status, "on_registry");
});

test("an operation whose effect is already on chain is not sent", async () => {
  const w = new World();
  w.judgments.add("1|0");
  w.addCheck({ status: "PROVISIONAL" });
  const s = emptyState();
  const lc = new Lifecycle(w.deps(), w.deps().addr, s, 1e9);
  const r = await lc.send("judge|1|0|PROVISIONAL", "0xjudge", "judge", ["0xregistry", 1], 0n, { kind: "judgment", check_id: 1, round: 0 });
  assert.deepEqual([r.ok, r.skipped, w.writes.length, lc.sent], [true, true, 0, 0]);
});

test("closing writes are verified by reading the check back: a rule that moves nothing is not success", async () => {
  const w = new World();
  const c = w.addCheck({ status: "PROVISIONAL", judge_deadline: w.t + 1000 });
  w.judgments.add(`${c.check_id}|0`);
  w.plan = (fn) => (fn === "rule" ? { noEffect: true } : {});
  const rep = (await run(w, emptyState())).rep;
  const rule = rep.writes.find((x) => x.fn === "rule")!;
  assert.deepEqual([rule.ok, /expected state change/.test(rule.note)], [false, true]);
});
