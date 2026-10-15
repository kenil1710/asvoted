"use client";

import Link from "next/link";
import useSWR from "swr";
import type { ActionOutcome, Verdict } from "@/lib/types";
import { chainUrl, shortAddress } from "@/lib/format";
import { explorerUrl } from "@/lib/genlayer";

export const STAMP: Record<string, { label: string; cls: string; soft: string }> = {
  AS_VOTED: { label: "AS VOTED", cls: "text-ok", soft: "bg-ok-soft text-ok" },
  DEVIATES: { label: "DEVIATES", cls: "text-dev", soft: "bg-dev-soft text-dev" },
  UNCLEAR: { label: "UNCLEAR", cls: "text-unclear", soft: "bg-unclear-soft text-unclear" },
};

export function Stamp({ verdict, size = "lg", animate = false }: { verdict: Verdict | ""; size?: "sm" | "lg"; animate?: boolean }) {
  const s = STAMP[verdict || "UNCLEAR"];
  if (!verdict) return <span className="text-sm text-ink-3">not ruled yet</span>;
  return (
    <span className={`stamp ${s.cls} ${animate ? "stamp-in" : ""} ${size === "lg" ? "text-2xl sm:text-3xl" : "text-[11px]"}`}
      role="img" aria-label={`Verdict: ${s.label.toLowerCase()}`}>
      {s.label}
    </span>
  );
}

const OUTCOME: Record<ActionOutcome, { label: string; cls: string }> = {
  AUTHORIZED: { label: "Authorized", cls: "bg-ok-soft text-ok" },
  NOT_AUTHORIZED: { label: "Not in proposal", cls: "bg-dev-soft text-dev" },
  OVER_AMOUNT: { label: "Over amount", cls: "bg-dev-soft text-dev" },
  UNCLEAR: { label: "Unclear", cls: "bg-unclear-soft text-unclear" },
};

export function OutcomeChip({ outcome }: { outcome: ActionOutcome }) {
  const o = OUTCOME[outcome] ?? OUTCOME.UNCLEAR;
  return <span className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-xs font-semibold ${o.cls}`}>{o.label}</span>;
}

export function StatusPill({ status }: { status: string }) {
  const cls = status === "FINAL" ? "border-ink-3 text-ink-2" : status === "APPEALED" ? "border-booth text-booth" : "border-unclear text-unclear";
  const label = status.charAt(0) + status.slice(1).toLowerCase();
  return <span className={`inline-flex items-center rounded border px-1.5 py-px text-xs font-medium ${cls}`}>{label}</span>;
}

export function Addr({ value, chain, size = 4 }: { value: string; chain?: string; size?: number }) {
  if (!value) return <span className="text-ink-3">none</span>;
  const href = chain ? chainUrl(chain, "address", value) : explorerUrl("address", value);
  return (
    <a href={href} target="_blank" rel="noreferrer" title={value} className="font-mono text-[0.82em] text-booth underline decoration-rule underline-offset-2 hover:decoration-booth">
      {shortAddress(value, size)}
    </a>
  );
}

export function TxLink({ hash, chain, label }: { hash: string; chain?: string; label?: string }) {
  const href = chain ? chainUrl(chain, "tx", hash) : explorerUrl("tx", hash);
  return (
    <a href={href} target="_blank" rel="noreferrer" title={hash} className="font-mono text-[0.82em] text-booth underline decoration-rule underline-offset-2 hover:decoration-booth">
      {label ?? shortAddress(hash, 6)}
    </a>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <span aria-hidden="true" className={`inline-block animate-pulse rounded bg-rule-2 ${className}`} />;
}

export function ErrorNote({ error, retry }: { error: unknown; retry?: () => void }) {
  const msg = String((error as Error)?.message ?? error);
  return (
    <div role="alert" className="rounded-md border border-dev/40 bg-dev-soft px-3 py-2 text-sm text-dev">
      Could not read the contract: {msg.slice(0, 200)}
      {retry && <button onClick={retry} className="ml-2 font-semibold underline">Try again</button>}
    </div>
  );
}

export function Section({ title, children, aside }: { title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="mt-12">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2 border-b border-rule pb-2">
        <h2 className="font-serif text-xl font-semibold">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function Button({ children, className = "", variant = "primary", ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" }) {
  const base = variant === "primary"
    ? "bg-ink text-paper hover:bg-booth disabled:bg-rule disabled:text-ink-3"
    : "border border-rule bg-sheet text-ink hover:border-booth disabled:text-ink-3";
  return <button {...p} className={`inline-flex min-h-10 items-center justify-center rounded-md px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${base} ${className}`}>{children}</button>;
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-semibold">{label}</span>
      {hint && <span className="mt-0.5 block text-xs text-ink-3">{hint}</span>}
      <span className="mt-1.5 block">{children}</span>
    </label>
  );
}

export const inputCls = "w-full rounded-md border border-rule bg-sheet px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-booth focus:outline-none";

export function useView<T>(key: string | null, fetcher: () => Promise<T>, refresh = 0) {
  return useSWR<T>(key, fetcher, { refreshInterval: refresh, revalidateOnFocus: false, shouldRetryOnError: true, errorRetryCount: 3 });
}

export function InternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <Link href={href} className="text-booth underline decoration-rule underline-offset-2 hover:decoration-booth">{children}</Link>;
}
