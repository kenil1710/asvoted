"use client";

import { useMemo, useState } from "react";
import { getAddress } from "viem";
import type { Action, Check, Execution, Proposal, RuledAction } from "@/lib/types";
import { CHAIN_LABEL, chainUrl, formatUnits, ipfsUrl, isoDate, shortAddress } from "@/lib/format";
import { Addr, OutcomeChip, Stamp, TxLink } from "./ui";

/* ── the ballot: proposal text with the passages the ruling relied on marked ── */

function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

type Seg = { t: string; mark: boolean };

function markText(text: string, quotes: string[]): Seg[] {
  const ranges: [number, number][] = [];
  for (const q of quotes) {
    const words = q.trim().split(/\s+/).filter(Boolean).slice(0, 60);
    if (words.length === 0) continue;
    try {
      const re = new RegExp(words.map(escapeRe).join("\\s+"), "g");
      let m: RegExpExecArray | null;
      while ((m = re.exec(text))) {
        ranges.push([m.index, m.index + m[0].length]);
        if (m[0].length === 0) re.lastIndex++;
      }
    } catch { /* an unusual quote is simply not marked */ }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const out: Seg[] = [];
  let at = 0;
  for (const [a, b] of ranges) {
    if (b <= at) continue;
    const s = Math.max(a, at);
    if (s > at) out.push({ t: text.slice(at, s), mark: false });
    out.push({ t: text.slice(s, b), mark: true });
    at = b;
  }
  if (at < text.length) out.push({ t: text.slice(at), mark: false });
  return out;
}

function BallotText({ text, quotes }: { text: string; quotes: string[] }) {
  const [full, setFull] = useState(false);
  const segs = useMemo(() => markText(text, quotes), [text, quotes]);
  const firstMark = segs.findIndex((s) => s.mark);
  const long = text.length > 2400;
  return (
    <div className="relative">
      <div className={`prose-ballot whitespace-pre-wrap break-anywhere ${long && !full ? "max-h-[34rem] overflow-hidden" : ""}`}>
        {segs.map((s, i) => (s.mark ? <mark key={i} id={i === firstMark ? "first-quote" : undefined}>{s.t}</mark> : <span key={i}>{s.t}</span>))}
      </div>
      {long && (
        <div className={full ? "mt-3" : "absolute inset-x-0 bottom-0 flex justify-center bg-gradient-to-t from-sheet pt-16"}>
          <button type="button" onClick={() => setFull(!full)} className="rounded-md border border-rule bg-sheet px-3 py-1.5 text-sm font-medium hover:border-booth">
            {full ? "Show less" : `Show the whole proposal (${Math.round(text.length / 1000)}k characters)`}
          </button>
        </div>
      )}
    </div>
  );
}

export function Ballot({ vote, quotes }: { vote: Proposal; quotes: string[] }) {
  const total = Number(vote.scores_total) || 0;
  return (
    <article aria-label="The proposal as voted" className="rounded-lg border border-rule bg-sheet p-4 sm:p-6">
      <header className="border-b border-rule pb-4">
        <p className="text-sm text-ink-2">The ballot · {vote.space}</p>
        <h3 className="mt-1 font-serif text-xl font-semibold leading-snug sm:text-2xl">{vote.title}</h3>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-3">
          <div><dt className="text-ink-3">Voting closed</dt><dd className="tabular">{isoDate(vote.end)}</dd></div>
          <div><dt className="text-ink-3">Result</dt><dd className={vote.outcome === "PASSED" ? "font-semibold text-ok" : vote.outcome === "FAILED" ? "font-semibold text-dev" : "font-semibold text-unclear"}>{vote.outcome === "PASSED" ? "Passed" : vote.outcome === "FAILED" ? "Did not pass" : "Unclear"}</dd></div>
          <div><dt className="text-ink-3">Voting type</dt><dd>{vote.type}</dd></div>
          <div className="col-span-2 sm:col-span-3"><dt className="text-ink-3">Pinned text (IPFS, hash checked in the contract)</dt>
            <dd><a href={ipfsUrl(vote.cid)} target="_blank" rel="noreferrer" className="break-anywhere font-mono text-xs text-booth underline decoration-rule underline-offset-2">{vote.cid}</a></dd></div>
        </dl>
        {vote.choices.length > 0 && (
          <ul className="mt-4 space-y-1.5" aria-label="Final scores">
            {vote.choices.map((c, i) => {
              const s = Number(vote.scores[i] ?? 0);
              const pct = total > 0 ? (s / total) * 100 : 0;
              return (
                <li key={i} className="text-sm">
                  <div className="flex justify-between gap-3"><span className="truncate">{c}</span><span className="tabular text-ink-2">{pct.toFixed(1)}%</span></div>
                  <div className="mt-0.5 h-1.5 rounded bg-rule-2"><div className="h-1.5 rounded bg-ink" style={{ width: `${pct}%` }} /></div>
                </li>
              );
            })}
          </ul>
        )}
        <p className="mt-3 text-xs text-ink-3">{vote.outcome_why}. Computed by the contract from the hub&apos;s final scores.</p>
      </header>
      <div className="pt-4">
        {vote.text ? <BallotText text={vote.text} quotes={quotes} /> : <p className="text-sm text-ink-3">Loading the text.</p>}
      </div>
      {Object.keys(vote.ens || {}).length > 0 && (
        <p className="mt-4 border-t border-rule pt-3 text-xs text-ink-2">
          ENS names resolved at Ethereum block{vote.ens_blocks.length > 1 ? "s" : ""} {vote.ens_blocks.join(" and ")}:{" "}
          {Object.entries(vote.ens).map(([n, a]) => <span key={n} className="mr-2 inline-block">{n} = <span className="font-mono">{shortAddress(a)}</span></span>)}
        </p>
      )}
    </article>
  );
}

/* ── the receipt: every decoded action, one row each ── */

const LOGO_CHAIN: Record<string, string> = { ethereum: "ethereum", arbitrum: "arbitrum", optimism: "optimism", base: "base", polygon: "polygon" };

function TokenMark({ chain, token, symbol }: { chain: string; token: string; symbol: string }) {
  const [failed, setFailed] = useState(false);
  let src = "";
  try {
    src = token
      ? `https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/${LOGO_CHAIN[chain]}/assets/${getAddress(token)}/logo.png`
      : `https://raw.githubusercontent.com/trustwallet/assets/master/blockchains/${LOGO_CHAIN[chain]}/info/logo.png`;
  } catch { src = ""; }
  if (!src || failed) {
    return (
      <span aria-hidden="true" className="inline-flex size-6 shrink-0 items-center justify-center rounded-full border border-rule bg-paper text-[10px] font-semibold text-ink-2">
        {(symbol || "?").slice(0, 3)}
      </span>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={src} alt="" width={24} height={24} onError={() => setFailed(true)} className="size-6 shrink-0 rounded-full bg-paper" loading="lazy" />;
}

function describe(a: Action, ex: Execution) {
  const tok = ex.tokens[a.token] ?? (a.token === "" ? ex.tokens[""] : undefined);
  const sym = tok?.symbol || (a.token ? shortAddress(a.token) : ex.tokens[""]?.symbol ?? "ETH");
  const dec = tok?.decimals ?? 18;
  const amt = (raw: string) => (dec >= 0 ? formatUnits(raw, dec) : `${raw} (raw)`);
  switch (a.kind) {
    case "erc20_transfer": return { verb: "Transfer", amount: `${amt(a.amount)} ${sym}`, to: a.recipient, sym, token: a.token };
    case "erc20_transfer_from": return { verb: "Transfer from " + shortAddress(a.from), amount: `${amt(a.amount)} ${sym}`, to: a.recipient, sym, token: a.token };
    case "erc20_approve": return { verb: "Approve", amount: BigInt(a.amount || "0") >= 2n ** 255n ? `unlimited ${sym}` : `${amt(a.amount)} ${sym}`, to: a.recipient, sym, token: a.token };
    case "native": return { verb: "Send", amount: `${formatUnits(a.amount, 18)} ${ex.tokens[""]?.symbol ?? "ETH"}`, to: a.recipient, sym: ex.tokens[""]?.symbol ?? "ETH", token: "" };
    case "gas_refund": return { verb: "Gas refund", amount: `${amt(a.amount)} ${sym}`, to: a.recipient, sym, token: a.token };
    case "delegatecall": return { verb: "Delegatecall", amount: a.fn || a.selector || "no calldata", to: a.target, sym: "", token: null };
    default: return { verb: "Call", amount: a.fn || a.selector || "no calldata", to: a.target, sym: ex.symbols?.[a.target] ?? "", token: null };
  }
}

export function Receipt({ ex, ruled }: { ex: Execution; ruled: RuledAction[] | null }) {
  const byI = new Map((ruled ?? []).map((r) => [r.i, r]));
  return (
    <article aria-label="The execution as decoded" className="receipt rounded-t-lg border border-b-0 border-rule px-4 pt-4 text-[13px] sm:px-6 sm:pt-6">
      <header className="border-b border-dashed border-rule pb-4">
        <p className="text-ink-2">The receipt · {CHAIN_LABEL[ex.chain] ?? ex.chain}</p>
        <p className="mt-1 break-anywhere text-[15px] font-medium">Safe <Addr value={ex.safe} chain={ex.chain} size={6} /></p>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5">
          <div><dt className="text-ink-3">Executed</dt><dd className="tabular">{isoDate(ex.block_time)}</dd></div>
          <div><dt className="text-ink-3">Transaction</dt><dd><TxLink hash={ex.tx} chain={ex.chain} /></dd></div>
          <div><dt className="text-ink-3">Block</dt><dd><a className="text-booth underline decoration-rule underline-offset-2" href={chainUrl(ex.chain, "block", ex.block)} target="_blank" rel="noreferrer">{ex.block}</a></dd></div>
          <div><dt className="text-ink-3">Safe nonce</dt><dd className="tabular">{ex.nonce}</dd></div>
          <div className="col-span-2"><dt className="text-ink-3">Safe tx hash (recomputed in the contract)</dt><dd className="break-anywhere text-[11px]">{ex.safe_tx_hash}</dd></div>
          <div className="col-span-2"><dt className="text-ink-3">Read at finalized block {ex.pinned_block}, from two RPCs that agreed</dt><dd className="break-anywhere text-[11px] text-ink-2">{ex.rpcs.map((u) => u.replace("https://", "")).join(" + ")}</dd></div>
        </dl>
      </header>
      <ol className="divide-y divide-dashed divide-rule" aria-label={`${ex.actions.length} decoded actions`}>
        {ex.actions.map((a) => {
          const d = describe(a, ex);
          const r = byI.get(a.i);
          return (
            <li key={a.i} className="py-3.5">
              <div className="flex items-start gap-3">
                <span className="w-5 shrink-0 pt-0.5 text-right text-ink-3 tabular">{a.i + 1}</span>
                {d.token !== null ? <TokenMark chain={ex.chain} token={d.token} symbol={d.sym} /> : <span aria-hidden="true" className="inline-flex size-6 shrink-0 items-center justify-center rounded border border-rule text-[10px] text-ink-3">fn</span>}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                    <p className="break-anywhere">
                      <span className={a.op === "DELEGATECALL" ? "font-semibold text-dev" : "font-semibold"}>{d.verb}</span>{" "}
                      <span>{d.amount}</span>
                      <span className="text-ink-3"> to </span>
                      <Addr value={d.to} chain={ex.chain} />
                    </p>
                    {r ? <OutcomeChip outcome={r.outcome} /> : <span className="text-xs text-ink-3">not judged</span>}
                  </div>
                  <p className="mt-1 text-[11px] text-ink-3">
                    {a.op === "DELEGATECALL" ? "DELEGATECALL" : "call"} to <span className="font-mono">{shortAddress(a.target)}</span>
                    {a.batch ? <> · inside {a.batch} (path {a.path})</> : null}
                    {a.selector ? <> · selector {a.selector}</> : null}
                    {a.flags.length > 0 ? <> · {a.flags.join(", ").toLowerCase()}</> : null}
                  </p>
                  {r && (
                    <p className="mt-1.5 font-sans text-[13px] leading-snug text-ink-2">
                      {r.reason}
                      {r.basis === "model" && <span className="ml-1 text-ink-3">(read from the proposal&apos;s words by the validators&apos; model)</span>}
                    </p>
                  )}
                  {r?.quote && (
                    <blockquote className="mt-1.5 border-l-2 border-mark pl-2 font-serif text-[13px] italic text-ink-2">“{r.quote}”</blockquote>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </article>
  );
}

export function VerdictBanner({ check, ex, vote, animate }: { check: Check; ex?: Execution; vote?: Proposal; animate?: boolean }) {
  const verdict = (check.final_verdict || check.appeal_ruling || check.ruling) as Check["ruling"];
  const summary = check.appeal_summary || check.ruling_summary;
  const counts = (check.appeal_detail ?? check.ruling_detail)?.counts;
  const tone = verdict === "AS_VOTED" ? "border-ok bg-ok-soft" : verdict === "DEVIATES" ? "border-dev bg-dev-soft" : verdict ? "border-unclear bg-unclear-soft" : "border-rule bg-sheet";
  return (
    <section aria-label="Verdict" className={`flex flex-col gap-5 rounded-lg border-2 p-5 sm:flex-row sm:items-center sm:p-6 ${tone}`}>
      <div className="shrink-0 py-2 sm:pr-4"><Stamp verdict={verdict} animate={animate} /></div>
      <div className="min-w-0">
        <p className="font-serif text-lg leading-snug sm:text-xl">{summary || "Filed and waiting for the validators to judge it."}</p>
        <p className="mt-2 text-sm text-ink-2">
          {check.final_verdict ? "Final" : check.status === "CONTESTABLE" ? "Provisional, open to one appeal" : check.status === "APPEALED" ? "Under appeal" : "Awaiting judgment"}
          {counts && <> · {counts.authorized} authorized, {counts.not_authorized} not in the proposal, {counts.over_amount} over amount, {counts.unclear} unclear</>}
          {ex && vote && <> · {ex.actions.length} actions on {CHAIN_LABEL[ex.chain] ?? ex.chain}, proposal in {vote.space}</>}
        </p>
      </div>
    </section>
  );
}
