"use client";

import Link from "next/link";
import useSWR from "swr";
import { getChecks, getAllDaos, getLedger, getStats, registry } from "@/lib/contract";
import { formatGen } from "@/lib/format";
import { CheckList } from "@/components/CheckList";
import { ErrorNote, Section, Skeleton } from "@/components/ui";
import { Specimen } from "@/components/Specimen";

function Figure({ n, label, k }: { n: React.ReactNode; label: string; k: string }) {
  return (
    <div className="border-l border-rule pl-4">
      <p className="font-serif text-3xl font-semibold tabular sm:text-4xl" data-k={k}>{n}</p>
      <p className="mt-0.5 text-sm text-ink-2">{label}</p>
    </div>
  );
}

export default function Home() {
  const reg = registry();
  const stats = useSWR(`stats:${reg}`, () => getStats(), { refreshInterval: 30_000 });
  const ledger = useSWR(`ledger:${reg}`, () => getLedger(), { refreshInterval: 60_000 });
  const checks = useSWR(`checks:${reg}`, () => getChecks(0, 12), { refreshInterval: 30_000 });
  const daos = useSWR(`daos:${reg}`, () => getAllDaos());
  const names = Object.fromEntries((daos.data?.daos ?? []).map((d) => [d.dao_id, d.space]));
  const s = stats.data;
  const n = (k: string) => (s ? Number(s[k] ?? 0) : <Skeleton className="h-8 w-12" />);
  return (
    <div>
      <section className="grid gap-10 pt-12 lg:grid-cols-[1.25fr_1fr] lg:items-end">
        <div>
          <h1 className="font-serif text-[2.4rem] font-semibold leading-[1.08] tracking-tight sm:text-6xl">
            Token holders voted.<br />Signers executed.<br />Did they match?
          </h1>
          <p className="mt-6 max-w-xl text-lg text-ink-2">
            Most DAOs vote on Snapshot and let a Safe multisig carry out the result. AsVoted decodes every action
            the Safe executed, holds it against the proposal that passed, and puts a pledge behind the answer.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link href="/file" className="inline-flex min-h-11 items-center rounded-md bg-ink px-5 font-semibold text-paper hover:bg-booth">File a check</Link>
            <Link href="/docs" className="inline-flex min-h-11 items-center rounded-md border border-rule bg-sheet px-5 font-semibold hover:border-booth">How a check is decided</Link>
          </div>
        </div>
        <Specimen checks={checks.data?.checks} />
      </section>

      <section aria-label="Registry figures" className="mt-14 grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-6">
        <Figure k="checks" n={n("checks")} label="checks filed" />
        <Figure k="final:AS_VOTED" n={n("final:AS_VOTED")} label="final as voted" />
        <Figure k="final:DEVIATES" n={n("final:DEVIATES")} label="final deviates" />
        <Figure k="final:UNCLEAR" n={n("final:UNCLEAR")} label="final unclear" />
        <Figure k="daos" n={n("daos")} label="DAOs listed" />
        <Figure k="pledges" n={ledger.data ? formatGen(ledger.data.pledges, 2) : <Skeleton className="h-8 w-12" />} label="GEN pledged" />
      </section>
      {stats.error && <div className="mt-4"><ErrorNote error={stats.error} retry={() => void stats.mutate()} /></div>}

      <Section title="Latest checks" aside={<span className="text-sm text-ink-2">{s ? `${Number(s["status:PROVISIONAL"] ?? 0) + Number(s["status:CONTESTABLE"] ?? 0) + Number(s["status:APPEALED"] ?? 0)} open` : ""}</span>}>
        {checks.error ? <ErrorNote error={checks.error} retry={() => void checks.mutate()} /> :
          checks.data ? <CheckList checks={checks.data.checks} daoNames={names} /> : <Skeleton className="h-64 w-full" />}
      </Section>
    </div>
  );
}
