"use client";

import { useState } from "react";
import { ADDR, DEPLOY_COMMIT, DEPLOYMENTS } from "@/lib/deployments";
import { getLedger } from "@/lib/contract";
import { getReadClient, explorerUrl } from "@/lib/genlayer";
import { formatGen } from "@/lib/format";
import { Button, Section, Skeleton, useView } from "@/components/ui";

async function sha256(text: string) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

type Row = { name: string; chain: string; github: string; same: boolean | null; error?: string };

export default function VerifyPage() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [busy, setBusy] = useState(false);
  const canon = useView(`ledger:${ADDR.registry}`, () => getLedger(ADDR.registry), 60_000);
  const demo = useView(`ledger:${ADDR.registryDemo}`, () => getLedger(ADDR.registryDemo), 60_000);
  async function check() {
    setBusy(true);
    const out: Row[] = [];
    for (const [name, d] of Object.entries(DEPLOYMENTS)) {
      try {
        const code = String(await getReadClient().getContractCode(d.address as `0x${string}`));
        const src = await (await fetch(`https://raw.githubusercontent.com/kenil1710/asvoted/${d.commit}/${d.file}`, { cache: "no-store" })).text();
        const [a, b] = await Promise.all([sha256(code), sha256(src)]);
        out.push({ name, chain: a, github: b, same: a === b && a === d.sha256 });
      } catch (e) {
        out.push({ name, chain: "", github: "", same: null, error: String((e as Error).message ?? e).slice(0, 120) });
      }
      setRows([...out]);
    }
    setBusy(false);
  }
  const ledger = (label: string, l: typeof canon.data) => (
    <div className="rounded-lg border border-rule bg-sheet p-4 text-sm">
      <p className="font-semibold">{label}</p>
      {!l ? <Skeleton className="mt-2 h-20 w-full" /> : (
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 tabular">
          <dt className="text-ink-3">Received</dt><dd data-k={`${label}:received`}>{formatGen(l.received)} GEN</dd>
          <dt className="text-ink-3">Pledges</dt><dd data-k={`${label}:pledges`}>{formatGen(l.pledges)} GEN</dd>
          <dt className="text-ink-3">Open stakes and bonds</dt><dd data-k={`${label}:open`}>{formatGen(l.open)} GEN</dd>
          <dt className="text-ink-3">Claimable</dt><dd data-k={`${label}:claimable`}>{formatGen(l.claimable)} GEN</dd>
          <dt className="text-ink-3">Claimed</dt><dd data-k={`${label}:claimed`}>{formatGen(l.claimed)} GEN</dd>
          <dt className="text-ink-3">Held now</dt><dd data-k={`${label}:held_now`}>{formatGen(l.held_now)} GEN</dd>
          <dt className="text-ink-3">Invariant</dt><dd className={l.invariant_holds ? "font-semibold text-ok" : "font-semibold text-dev"}>{l.invariant_holds ? "holds" : "broken"}</dd>
          <dt className="text-ink-3">Recomputed from records</dt><dd className={l.views_match_storage ? "text-ok" : "text-dev"}>{l.views_match_storage === null ? "paged" : l.views_match_storage ? "matches" : "differs"}</dd>
          <dt className="text-ink-3">Contract balance</dt><dd>{formatGen(l.on_chain_balance)} GEN</dd>
        </dl>
      )}
      <p className="mt-2 text-xs text-ink-3">received = pledges + open + claimable + claimed. On Studio Dev a claim&apos;s transfer is queued and not delivered, so the balance can exceed what is held by up to the claimed total.</p>
    </div>
  );
  return (
    <div>
      <h1 className="mt-10 font-serif text-4xl font-semibold">Verify</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        Every contract was deployed from commit <a className="font-mono text-sm text-booth underline" href={`https://github.com/kenil1710/asvoted/tree/${DEPLOY_COMMIT}`}>{DEPLOY_COMMIT.slice(0, 12)}</a>.
        The button below reads each contract&apos;s code back from Studio Dev, fetches the same file at that commit from GitHub, and hashes both in your browser.
      </p>
      <Section title="Contracts">
        <div className="overflow-x-auto rounded-lg border border-rule bg-sheet">
          <table className="w-full min-w-[44rem] text-sm">
            <caption className="sr-only">Deployed contracts</caption>
            <thead><tr className="border-b border-rule text-left text-ink-2"><th className="px-4 py-2.5 font-medium">Contract</th><th className="px-4 py-2.5 font-medium">Address</th><th className="px-4 py-2.5 font-medium">Source</th><th className="px-4 py-2.5 font-medium">Constructor</th></tr></thead>
            <tbody>
              {Object.entries(DEPLOYMENTS).map(([name, d]) => (
                <tr key={name} className="border-b border-rule-2 last:border-0">
                  <td className="px-4 py-2.5 font-semibold">{name}</td>
                  <td className="px-4 py-2.5"><a href={explorerUrl("address", d.address)} target="_blank" rel="noreferrer" className="font-mono text-xs text-booth underline">{d.address}</a></td>
                  <td className="px-4 py-2.5 font-mono text-xs">{d.file}</td>
                  <td className="px-4 py-2.5 font-mono text-xs break-anywhere">{JSON.stringify(d.constructor_args).slice(0, 80)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4"><Button onClick={() => void check()} disabled={busy}>{busy ? "Comparing" : "Compare on-chain code with GitHub"}</Button></div>
        {rows && (
          <ul className="mt-4 space-y-1.5 text-sm">
            {rows.map((r) => (
              <li key={r.name} className="flex flex-wrap items-baseline gap-x-3 rounded border border-rule-2 bg-sheet px-3 py-2">
                <span className="w-44 font-semibold">{r.name}</span>
                {r.error ? <span className="text-dev">{r.error}</span> : <>
                  <span className={r.same ? "font-semibold text-ok" : "font-semibold text-dev"}>{r.same ? "byte-identical" : "differs"}</span>
                  <span className="break-anywhere font-mono text-[11px] text-ink-3">sha256 {r.chain}</span>
                </>}
              </li>
            ))}
          </ul>
        )}
      </Section>
      <Section title="The books">
        <div className="grid gap-4 md:grid-cols-2">{ledger("Canonical registry", canon.data)}{ledger("Demo registry", demo.data)}</div>
      </Section>
    </div>
  );
}
