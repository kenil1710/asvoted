"use client";

import Link from "next/link";
import { CHAIN_LABEL } from "@/lib/format";
import type { PatrolState } from "@/lib/patrol/state";
import { Addr, ErrorNote, Section, Skeleton, TxLink, useView } from "@/components/ui";

/** The patrol's state, as the GitHub Action last committed it to the patrol-state branch. */
const STATE_URL = "https://raw.githubusercontent.com/kenil1710/asvoted/patrol-state/patrol-state.json";

export default function UnmatchedPage() {
  const st = useView("patrol-state", async () => {
    const r = await fetch(STATE_URL, { cache: "no-store" });
    if (!r.ok) throw new Error(`patrol state: HTTP ${r.status}`);
    return (await r.json()) as PatrolState;
  }, 120_000);
  const rows = [...(st.data?.unmatched ?? [])].sort((a, b) => b.at.localeCompare(a.at));
  const cps = Object.entries(st.data?.checkpoints ?? {});
  return (
    <div>
      <h1 className="mt-10 font-serif text-4xl font-semibold">Unmatched executions</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        Executions of listed Safes that the <Link className="underline" href="/patrol">patrol</Link> scanned and could not match to a passed
        proposal of the DAO&apos;s space that names an address the execution touches. They are not filed: filing against a guessed proposal would
        measure the guess, not the signers. Anyone can still file one by hand with the right proposal. Read from the patrol&apos;s state
        file on the <a className="underline" href="https://github.com/kenil1710/asvoted/tree/patrol-state">patrol-state</a> branch.
      </p>
      <Section title={`${rows.length} unmatched`}>
        {st.error ? <ErrorNote error={st.error} /> : !st.data ? <Skeleton className="h-40 w-full" /> : rows.length === 0 ? (
          <p className="text-sm text-ink-2">None so far.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-ink-3"><tr><th className="py-2 pr-4">DAO</th><th className="pr-4">Execution</th><th className="pr-4">Block</th><th className="pr-4">Why not filed</th><th>Seen</th></tr></thead>
              <tbody>
                {rows.map((u) => (
                  <tr key={u.key} className="border-t border-rule align-top">
                    <td className="py-2 pr-4">{u.space}<br /><span className="text-xs text-ink-3">{CHAIN_LABEL[u.chain] ?? u.chain} <Addr value={u.safe} chain={u.chain} /></span></td>
                    <td className="pr-4"><TxLink hash={u.tx} chain={u.chain} /><br /><span className="font-mono text-xs text-ink-3" title="safeTxHash">{u.safe_tx_hash.slice(0, 12)}…</span></td>
                    <td className="pr-4 tabular">{u.block}</td>
                    <td className="pr-4 text-ink-2">{u.reason}</td>
                    <td className="text-xs text-ink-3">{u.at.slice(0, 16).replace("T", " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
      <Section title="Coverage: last block scanned per Safe">
        {!st.data ? <Skeleton className="h-20 w-full" /> : cps.length === 0 ? <p className="text-sm text-ink-2">No Safe scanned yet.</p> : (
          <ul className="text-sm">
            {cps.map(([k, c]) => <li key={k} className="font-mono text-xs">{k} through block {c.block} (from {c.origin}, {c.updated.slice(0, 16).replace("T", " ")})</li>)}
          </ul>
        )}
        {st.data && <p className="mt-2 text-xs text-ink-3">{st.data.retry.length} execution(s) in the retry queue; state updated {st.data.updated || "never"}.</p>}
      </Section>
    </div>
  );
}
