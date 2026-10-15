"use client";

import Link from "next/link";
import type { Check } from "@/lib/types";
import { CHAIN_LABEL, isoDate, shortAddress } from "@/lib/format";
import { Stamp, StatusPill } from "./ui";

export function CheckList({ checks, daoNames }: { checks: Check[]; daoNames?: Record<number, string> }) {
  if (checks.length === 0) return <p className="rounded-lg border border-dashed border-rule p-6 text-sm text-ink-2">No checks on this registry yet. <Link href="/file" className="text-booth underline">File the first one</Link>.</p>;
  return (
    <ul className="divide-y divide-rule rounded-lg border border-rule bg-sheet">
      {checks.map((c) => {
        const v = (c.final_verdict || c.appeal_ruling || c.ruling) as Check["ruling"];
        return (
          <li key={c.check_id}>
            <Link href={`/check/${c.check_id}`} className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-1 px-4 py-4 hover:bg-paper sm:grid-cols-[7.5rem_1fr_auto]">
              <span className="row-span-2 flex w-[6.5rem] justify-center sm:row-span-1"><Stamp verdict={v} size="sm" /></span>
              <span className="min-w-0">
                <span className="block font-serif text-[15px] leading-snug">{c.ruling_summary || `Execution ${shortAddress(c.tx, 6)} filed, waiting for judgment.`}</span>
                <span className="mt-0.5 block text-xs text-ink-2">#{c.check_id} · {daoNames?.[c.dao_id] ?? `DAO #${c.dao_id}`} · {CHAIN_LABEL[c.chain] ?? c.chain} · filed {isoDate(c.filed_at)}</span>
              </span>
              <span className="col-start-2 sm:col-start-auto"><StatusPill status={c.status} /></span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
