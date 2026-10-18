"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useWallet } from "./WalletProvider";
import { getDeployment, setDeployment, type Deployment } from "@/lib/genlayer";
import { shortAddress } from "@/lib/format";

const NAV = [
  { href: "/", label: "Checks" },
  { href: "/daos", label: "DAOs" },
  { href: "/file", label: "File a check" },
  { href: "/patrol", label: "Patrol" },
  { href: "/unmatched", label: "Unmatched" },
  { href: "/docs", label: "How it works" },
  { href: "/verify", label: "Verify" },
];

function Mark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className="size-7">
      <rect x="2" y="2" width="28" height="28" rx="5" fill="var(--ink)" />
      <rect x="8" y="8" width="16" height="16" rx="2" fill="none" stroke="var(--paper)" strokeWidth="2.2" />
      <path d="M11.5 16.5l3.5 3.5 6.5-8" fill="none" stroke="var(--ok)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark" | "system">("system");
  useEffect(() => {
    const t = document.documentElement.dataset.theme;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (t === "light" || t === "dark") setTheme(t);
  }, []);
  const next = theme === "system" ? "dark" : theme === "dark" ? "light" : "system";
  return (
    <button type="button" onClick={() => {
      setTheme(next);
      try {
        if (next === "system") { delete document.documentElement.dataset.theme; localStorage.removeItem("asvoted-theme"); }
        else { document.documentElement.dataset.theme = next; localStorage.setItem("asvoted-theme", next); }
      } catch { /* storage blocked */ }
    }} className="rounded-md border border-rule px-2.5 py-1.5 text-xs font-medium text-ink-2 hover:border-booth"
      aria-label={`Theme: ${theme}. Switch to ${next}.`}>
      {theme === "system" ? "Auto" : theme === "dark" ? "Dark" : "Light"}
    </button>
  );
}

export function DeploymentSwitch() {
  const [d, setD] = useState<Deployment>("canonical");
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setD(getDeployment()), []);
  return (
    <div role="group" aria-label="Registry" className="flex overflow-hidden rounded-md border border-rule text-xs font-medium">
      {(["canonical", "demo"] as const).map((x) => (
        <button key={x} type="button" aria-pressed={d === x} onClick={() => { setDeployment(x); setD(x); window.location.reload(); }}
          className={`px-2.5 py-1.5 ${d === x ? "bg-ink text-paper" : "text-ink-2 hover:bg-sheet"}`}
          title={x === "canonical" ? "Real DAO checks, 1 hour contest window" : "Same code, 90 second windows, for trying every path"}>
          {x === "canonical" ? "Canonical" : "Demo"}
        </button>
      ))}
    </div>
  );
}

export function Header() {
  const path = usePathname();
  const w = useWallet();
  const [open, setOpen] = useState(false);
  return (
    <header className="border-b border-rule bg-paper/95 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2" aria-label="AsVoted home">
          <Mark />
          <span className="font-serif text-xl font-semibold tracking-tight">AsVoted</span>
        </Link>
        <nav aria-label="Main" className="ml-4 hidden gap-1 lg:flex">
          {NAV.map((n) => {
            const on = n.href === "/" ? path === "/" || path.startsWith("/check") : path.startsWith(n.href);
            return (
              <Link key={n.href} href={n.href} aria-current={on ? "page" : undefined}
                className={`rounded px-2.5 py-1.5 text-sm ${on ? "font-semibold text-ink underline decoration-booth decoration-2 underline-offset-[6px]" : "text-ink-2 hover:text-ink"}`}>
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <div className="hidden sm:block"><DeploymentSwitch /></div>
          <ThemeToggle />
          {w.account ? (
            w.onWrongNetwork ? (
              <button onClick={() => void w.switchNetwork()} className="rounded-md bg-unclear px-3 py-1.5 text-xs font-semibold text-paper">Switch network</button>
            ) : (
              <span className="hidden rounded-md border border-rule px-2.5 py-1.5 font-mono text-xs sm:inline" title={w.account}>{shortAddress(w.account)}</span>
            )
          ) : (
            <button onClick={() => void w.connect()} disabled={w.connecting}
              className="rounded-md bg-ink px-3 py-1.5 text-xs font-semibold text-paper hover:bg-booth disabled:opacity-60">
              {w.connecting ? "Connecting" : w.hasWallet ? "Connect wallet" : "No wallet"}
            </button>
          )}
          <button className="rounded-md border border-rule px-2.5 py-1.5 text-xs lg:hidden" aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen(!open)}>
            Menu
          </button>
        </div>
      </div>
      {open && (
        <nav id="mobile-nav" aria-label="Main" className="border-t border-rule px-4 py-3 lg:hidden">
          <ul className="grid grid-cols-2 gap-1">
            {NAV.map((n) => (
              <li key={n.href}><Link href={n.href} onClick={() => setOpen(false)} className="block rounded px-2 py-2 text-sm hover:bg-sheet">{n.label}</Link></li>
            ))}
          </ul>
          <div className="mt-3 sm:hidden"><DeploymentSwitch /></div>
        </nav>
      )}
      {w.error && <p role="alert" className="mx-auto max-w-6xl px-4 pb-2 text-xs text-unclear sm:px-6">{w.error}</p>}
    </header>
  );
}
