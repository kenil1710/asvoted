"use client";

import Link from "next/link";
import useSWR from "swr";
import { getExecution, getProposal } from "@/lib/contract";
import type { Check } from "@/lib/types";
import { formatUnits, isoDate, shortAddress } from "@/lib/format";
import { Stamp } from "./ui";

/** The hero picture: a real check from the registry, ballot over receipt. */
export function Specimen({ checks }: { checks: Check[] | undefined }) {
  const pick = checks?.find((c) => (c.final_verdict || c.ruling) === "DEVIATES") ?? checks?.find((c) => c.ruling) ?? null;
  const ex = useSWR(pick ? `exec:${pick.exec_id}` : null, () => getExecution(pick!.exec_id));
  const vote = useSWR(pick ? `vote:${pick.vote_id}` : null, () => getProposal(pick!.vote_id));
  if (!pick || !ex.data || !vote.data) {
    return <div className="hidden h-72 rounded-md border border-dashed border-rule lg:block" aria-hidden="true" />;
  }
  const a = ex.data.actions[0];
  const tok = ex.data.tokens[a?.token ?? ""] ?? ex.data.tokens[""];
  const line = a && a.amount ? `${a.kind === "erc20_approve" ? "approve" : "transfer"} ${formatUnits(a.amount, tok?.decimals ?? 18)} ${tok?.symbol ?? ""}` : (a?.fn || a?.selector || "call");
  return (
    <Link href={`/check/${pick.check_id}`} className="group relative hidden h-80 lg:block" aria-label={`Check #${pick.check_id}: ${pick.ruling_summary}`}>
      <div className="absolute left-0 top-0 w-[62%] -rotate-2 rounded-md border border-rule bg-sheet p-5 shadow-sm transition-transform group-hover:-rotate-3">
        <p className="text-xs text-ink-3">The ballot, {vote.data.space}, closed {isoDate(vote.data.end)}</p>
        <p className="mt-2 line-clamp-4 font-serif text-[15px] font-semibold leading-snug">{vote.data.title}</p>
      </div>
      <div className="receipt absolute right-0 top-32 w-[50%] rotate-2 rounded-t-md border border-b-0 border-rule p-4 text-[12px] text-ink-2 shadow-sm transition-transform group-hover:rotate-3">
        <p className="text-ink">Executed {isoDate(ex.data.block_time)}</p>
        <p className="mt-2 break-anywhere">{line}</p>
        {a?.recipient && <p>to {shortAddress(a.recipient)}</p>}
        <p className="text-ink-3">{ex.data.actions.length} action{ex.data.actions.length === 1 ? "" : "s"} decoded</p>
        <div className="mt-4 flex justify-center"><Stamp verdict={(pick.final_verdict || pick.ruling) as Check["ruling"]} size="sm" /></div>
      </div>
    </Link>
  );
}
