/**
 * Round 2: the patrol closes a check by the deadline of its current round.
 * After the DAO responds to a DEVIATES an appeal produced, the original
 * appeal_deadline passes long before the response deadline; the patrol must
 * judge and rule the response, and must not expire it early.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { activeDeadline, runCore } from "../src/lib/patrol/core";
import { emptyState } from "../src/lib/patrol/state";
import { PATROL, World } from "./mock";

const L = { maxWrites: 10, timeBudgetMs: 1e9, maxSpan: {}, logChunk: 1000, initialBackfill: {} };

function responded(w: World) {
  // filed, ruled AS_VOTED, appealed (round 1 judged DEVIATES), the DAO responded (round 2)
  const c = w.addCheck({ filer: PATROL, status: "APPEALED", round: 2, judge_deadline: w.t - 2000, contest_deadline: w.t - 500,
    appeal_deadline: w.t - 100, resp_deadline: w.t + 3600 });
  w.judgments.add(`${c.check_id}|0`);
  w.judgments.add(`${c.check_id}|1`);
  return c;
}

test("activeDeadline: round 2 uses resp_deadline, round 1 appeal_deadline", () => {
  const base = { judge_deadline: 1, contest_deadline: 2, appeal_deadline: 3, resp_deadline: 4 };
  assert.equal(activeDeadline({ ...base, status: "PROVISIONAL", round: 0 }), 1);
  assert.equal(activeDeadline({ ...base, status: "CONTESTABLE", round: 1 }), 2);
  assert.equal(activeDeadline({ ...base, status: "APPEALED", round: 1 }), 3);
  assert.equal(activeDeadline({ ...base, status: "APPEALED", round: 2 }), 4);
  assert.equal(activeDeadline({ ...base, status: "APPEALED", round: 2, active_deadline: 9 }), 9);
});

test("the DAO's response is judged and ruled after the original appeal_deadline; no premature expire", async () => {
  const w = new World();
  const c = responded(w);
  assert.ok(w.t > c.appeal_deadline && w.t < c.resp_deadline);
  const rep = await runCore(w.deps(), emptyState(), L);
  assert.deepEqual(w.writes.map((x) => [x.fn, x.args[x.fn === "judge" ? 1 : 0]]), [["judge", c.check_id], ["rule", c.check_id]]);
  assert.ok(w.judgments.has(`${c.check_id}|2`), "judged in round 2");
  assert.equal(w.checks[c.check_id - 1].status, "FINAL");
  assert.ok(!rep.closed.some((x) => x.startsWith("expire")));
});

test("the response is expired only once resp_deadline has passed", async () => {
  const w = new World();
  const c = responded(w);
  w.t = c.resp_deadline;
  await runCore(w.deps(), emptyState(), { ...L, maxWrites: 2 }); // one write, and the one held for the heartbeat
  assert.deepEqual(w.writes.map((x) => x.fn), ["judge"]); // at the deadline: still judgeable
  const w2 = new World();
  const c2 = responded(w2);
  w2.t = c2.resp_deadline + 1;
  await runCore(w2.deps(), emptyState(), L);
  assert.deepEqual(w2.writes.map((x) => x.fn), ["expire"]);
});

test("without active_deadline in the row (older registry), the patrol still uses resp_deadline in round 2", async () => {
  const w = new World();
  const c = responded(w);
  const deps = w.deps();
  const view = deps.view;
  deps.view = async <T,>(a: string, fn: string, args: unknown[] = []) => {
    const r = (await view(a, fn, args as never)) as { checks?: Record<string, unknown>[] };
    if (fn === "get_open_checks") r.checks?.forEach((x) => delete x.active_deadline);
    return r as T;
  };
  await runCore(deps, emptyState(), L);
  assert.deepEqual(w.writes.map((x) => x.fn), ["judge", "rule"]);
  assert.equal(w.checks[c.check_id - 1].status, "FINAL");
});
