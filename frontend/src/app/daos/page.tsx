"use client";

import Link from "next/link";
import { useState } from "react";
import { ADDR } from "@/lib/deployments";
import { getBinding, getBindingId, getDaoId, getDaos, registry, send } from "@/lib/contract";
import { CHAIN_LABEL, formatGen, isAddress, shortAddress } from "@/lib/format";
import { TxStatus, useTx } from "@/components/tx";
import { useWallet } from "@/components/WalletProvider";
import { Button, ErrorNote, Field, inputCls, Section, Skeleton, useView } from "@/components/ui";

const CHAINS = ["ethereum", "arbitrum", "optimism", "base", "polygon"];

function ListForm({ onDone }: { onDone: () => void }) {
  const w = useWallet();
  const tx = useTx();
  const [space, setSpace] = useState("");
  const [chain, setChain] = useState("ethereum");
  const [safe, setSafe] = useState("");
  const [step, setStep] = useState("");
  const bad = !space.trim() ? "enter the Snapshot space id" : !isAddress(safe) ? "enter the Safe address" : "";
  const noWallet = !w.account ? "connect a wallet first" : w.onWrongNetwork ? "switch to Studio Dev first" : "";
  async function go() {
    const sp = space.trim().toLowerCase();
    const sf = safe.trim().toLowerCase();
    await tx.run(async (onProgress) => {
      const bid = Number(await getBindingId(sp, chain, sf));
      const b = bid ? await getBinding(bid) : null;
      if (!b || Date.now() / 1000 - b.read_at > 3000) {
        setStep("1 of 2: reading the space's treasury list from the Snapshot hub");
        const r = await send(w.account!, ADDR.voteReader, "read_space", [sp, chain, sf], 0n, { onProgress,
          confirm: async () => Number(await getBindingId(sp, chain, sf)) > bid });
        if (r.kind !== "ok") return;
        const nb = await getBinding(Number(await getBindingId(sp, chain, sf)));
        if (!nb.listed) {
          onProgress({ phase: "rejected", hash: r.hash, message: `${sp} does not list ${shortAddress(sf)} on ${CHAIN_LABEL[chain]} in its treasuries, so it cannot be listed.` });
          return;
        }
      }
      setStep("2 of 2: listing the DAO in the registry");
      await send(w.account!, registry(), "list_dao", [sp, chain, sf], 0n, { onProgress,
        confirm: async () => Number(await getDaoId(sp, chain, sf)) > 0 });
    });
    setStep("");
    onDone();
  }
  return (
    <form className="rounded-lg border border-rule bg-sheet p-5" onSubmit={(e) => { e.preventDefault(); void go(); }}>
      <p className="text-sm text-ink-2">
        A DAO is listed by its Snapshot space and the Safe that executes for it. The listing is refused unless the space&apos;s
        own settings name that Safe among its treasuries, read from the hub in the same hour. Anyone can list; only the
        space&apos;s admins or moderators can then claim the listing and pledge.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_10rem_1.4fr]">
        <Field label="Snapshot space"><input className={inputCls} value={space} onChange={(e) => setSpace(e.target.value)} placeholder="cow.eth" autoComplete="off" /></Field>
        <Field label="Chain">
          <select className={inputCls} value={chain} onChange={(e) => setChain(e.target.value)}>
            {CHAINS.map((c) => <option key={c} value={c}>{CHAIN_LABEL[c]}</option>)}
          </select>
        </Field>
        <Field label="Safe address"><input className={`${inputCls} font-mono`} value={safe} onChange={(e) => setSafe(e.target.value)} placeholder="0x…" autoComplete="off" spellCheck={false} /></Field>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={Boolean(bad || noWallet) || tx.busy}>List this DAO</Button>
        <span className="text-sm text-ink-3">{noWallet || bad || step}</span>
      </div>
      <TxStatus progress={tx.progress} />
    </form>
  );
}

export default function DaosPage() {
  const reg = registry();
  const daos = useView(`daos:${reg}`, () => getDaos(0, 50), 60_000);
  return (
    <div>
      <h1 className="mt-10 font-serif text-4xl font-semibold">DAOs</h1>
      <p className="mt-2 max-w-2xl text-ink-2">Each row is a Snapshot space and the Safe its settings list as a treasury. Counts are final rulings.</p>
      <Section title="Listed">
        {daos.error ? <ErrorNote error={daos.error} retry={() => void daos.mutate()} /> : !daos.data ? <Skeleton className="h-48 w-full" /> : daos.data.daos.length === 0 ? (
          <p className="text-sm text-ink-2">No DAO is listed on this registry yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-rule bg-sheet">
            <table className="w-full min-w-[40rem] text-sm">
              <caption className="sr-only">Listed DAOs</caption>
              <thead><tr className="border-b border-rule text-left text-ink-2">
                <th className="px-4 py-2.5 font-medium">Space</th><th className="px-4 py-2.5 font-medium">Safe</th>
                <th className="px-4 py-2.5 text-right font-medium">As voted</th><th className="px-4 py-2.5 text-right font-medium">Deviates</th>
                <th className="px-4 py-2.5 text-right font-medium">Unclear</th><th className="px-4 py-2.5 text-right font-medium">Open</th><th className="px-4 py-2.5 text-right font-medium">Pledge</th>
              </tr></thead>
              <tbody>
                {daos.data.daos.map((d) => (
                  <tr key={d.dao_id} className="border-b border-rule-2 last:border-0 hover:bg-paper">
                    <td className="px-4 py-3"><Link href={`/dao/${d.dao_id}`} className="font-semibold text-booth underline decoration-rule underline-offset-2">{d.space}</Link><span className="block text-xs text-ink-3">{d.controller ? "claimed" : "unclaimed listing"}</span></td>
                    <td className="px-4 py-3 font-mono text-xs">{shortAddress(d.safe)} <span className="font-sans text-ink-3">{CHAIN_LABEL[d.chain]}</span></td>
                    <td className="px-4 py-3 text-right tabular text-ok">{d.as_voted}</td>
                    <td className="px-4 py-3 text-right tabular text-dev">{d.deviates}</td>
                    <td className="px-4 py-3 text-right tabular text-unclear">{d.unclear}</td>
                    <td className="px-4 py-3 text-right tabular">{d.open_checks}</td>
                    <td className="px-4 py-3 text-right tabular">{formatGen(d.pledge, 2)} GEN</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
      <Section title="List a DAO"><ListForm onDone={() => void daos.mutate()} /></Section>
    </div>
  );
}
