"use client";

import { useState } from "react";
import { ADDR, PATROL_ADDRESS } from "@/lib/deployments";
import { getChecks } from "@/lib/contract";
import type { RunReport } from "@/lib/patrol";
import { CheckList } from "@/components/CheckList";
import { Addr, Button, ErrorNote, Section, Skeleton, useView } from "@/components/ui";

export default function PatrolPage() {
  const checks = useView(`patrolchecks:${ADDR.registry}`, () => getChecks(0, 50, ADDR.registry), 60_000);
  const mine = (checks.data?.checks ?? []).filter((c) => c.filer === PATROL_ADDRESS);
  const [rep, setRep] = useState<RunReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function dry() {
    setBusy(true); setErr("");
    try {
      const r = await fetch("/api/patrol?dry=1", { cache: "no-store" });
      setRep(await r.json());
    } catch (e) { setErr(String((e as Error).message ?? e)); } finally { setBusy(false); }
  }
  return (
    <div>
      <h1 className="mt-10 font-serif text-4xl font-semibold">Patrol</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        A bot watches every Safe listed on the canonical registry. Every 15 minutes it reads their ExecutionSuccess events,
        matches each new execution to the most recent passed proposal of the DAO&apos;s space, files a check, and later judges,
        rules on and closes its own filings. It never files the same Safe transaction twice. It signs as <Addr value={PATROL_ADDRESS} />.
      </p>
      <Section title="Its filings, read from the canonical registry">
        {checks.error ? <ErrorNote error={checks.error} /> : !checks.data ? <Skeleton className="h-40 w-full" /> :
          mine.length === 0 ? <p className="text-sm text-ink-2">No check filed by the patrol yet. It files only executions newer than its 3-hour look-back that have no check.</p> : <CheckList checks={mine} />}
      </Section>
      <Section title="What a run would do right now">
        <p className="mb-3 text-sm text-ink-2">A dry run makes the same reads and matches as the scheduled one and sends nothing.</p>
        <Button onClick={() => void dry()} disabled={busy}>{busy ? "Running, up to a minute" : "Run a dry patrol"}</Button>
        {err && <div className="mt-3"><ErrorNote error={err} /></div>}
        {rep && (
          <div className="mt-4 rounded-lg border border-rule bg-sheet p-4 text-sm">
            <p>{rep.started}: {rep.daos_watched} Safes watched, {rep.executions_seen} executions in the look-back, {rep.already_checked} already checked, {rep.not_final_yet} not final yet, {rep.matched.length} new, {rep.seconds}s.</p>
            {rep.matched.length > 0 && <ul className="mt-2 list-disc pl-5">{rep.matched.map((m) => <li key={m.tx}>{m.dao} <span className="font-mono text-xs">{m.tx.slice(0, 12)}…</span> matched to <span className="font-mono text-xs">{m.cid.slice(0, 14)}…</span>, {m.why}</li>)}</ul>}
            {rep.closed.length > 0 && <p className="mt-2">Would close: {rep.closed.join(", ")}</p>}
            {rep.writes.length > 0 && <ul className="mt-2 font-mono text-xs text-ink-2">{rep.writes.map((w, i) => <li key={i}>{w.fn} {w.args} ({w.note})</li>)}</ul>}
            {rep.notes.length > 0 && <ul className="mt-2 text-ink-3">{rep.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
          </div>
        )}
      </Section>
    </div>
  );
}
