"use client";

import { useState } from "react";
import { ADDR } from "@/lib/deployments";
import { getCheck, getExecution, getJudgment, getProposal, registry, send } from "@/lib/contract";
import { formatGen, isoDate, relativeTime, shortAddress } from "@/lib/format";
import type { Check } from "@/lib/types";
import { Ballot, Receipt, VerdictBanner } from "./BallotReceipt";
import { TxStatus, useTx } from "./tx";
import { useWallet } from "./WalletProvider";
import { Addr, Button, ErrorNote, inputCls, Section, Skeleton, StatusPill, useView } from "./ui";

function now() { return Math.floor(Date.now() / 1000); }

function Timeline({ c }: { c: Check }) {
  const steps = [
    { key: "PROVISIONAL", label: "Filed", at: c.filed_at, note: c.status === "PROVISIONAL" ? `judge by ${isoDate(c.judge_deadline)} ${new Date(c.judge_deadline * 1000).toISOString().slice(11, 16)} UTC` : "" },
    { key: "CONTESTABLE", label: "Ruled, contestable", at: c.ruled_at, note: c.contest_deadline ? `appeals until ${new Date(c.contest_deadline * 1000).toISOString().slice(0, 16).replace("T", " ")} UTC` : "" },
    ...(c.appellant ? [{ key: "APPEALED", label: "Appealed", at: c.contest_deadline && c.appeal_deadline ? c.appeal_deadline - 1 : 0, note: `fresh panel by ${new Date(c.appeal_deadline * 1000).toISOString().slice(0, 16).replace("T", " ")} UTC` }] : []),
    { key: "FINAL", label: "Final", at: c.final_at, note: c.final_how ? c.final_how.toLowerCase().split("_").join(" ") : "" },
  ];
  const order = steps.map((s) => s.key);
  const reached = order.indexOf(c.status);
  return (
    <ol className="grid gap-3 sm:grid-cols-4" aria-label="Lifecycle">
      {steps.map((s, i) => {
        const done = i < reached || c.status === "FINAL";
        const current = i === reached && c.status !== "FINAL";
        return (
          <li key={s.key} className={`rounded-md border px-3 py-2.5 ${current ? "border-booth bg-booth-soft" : done ? "border-rule bg-sheet" : "border-dashed border-rule"}`}>
            <p className={`text-sm font-semibold ${done || current ? "text-ink" : "text-ink-3"}`}>{i + 1}. {s.label}</p>
            <p className="mt-0.5 text-xs text-ink-2">{s.at && (done || current) && s.key !== "APPEALED" ? relativeTime(s.at) : ""}{s.note ? (s.at && (done || current) && s.key !== "APPEALED" ? ", " : "") + s.note : ""}</p>
          </li>
        );
      })}
    </ol>
  );
}

/** What the contract would say right now, so a button is disabled with the contract's own reason. */
function reasons(c: Check, judged: boolean) {
  const t = now();
  return {
    judge: c.status === "PROVISIONAL" || c.status === "APPEALED" ? (judged ? "ALREADY_JUDGED" : (c.status === "PROVISIONAL" ? t > c.judge_deadline : t > c.appeal_deadline) ? "deadline passed, use expire" : "") : "CHECK_NOT_AWAITING_JUDGMENT",
    rule: c.status === "PROVISIONAL" || c.status === "APPEALED" ? (judged ? "" : "NOT_JUDGED_YET") : `NOTHING_TO_RULE_ON_IN_${c.status}`,
    finalize: c.status !== "CONTESTABLE" ? "NOT_CONTESTABLE" : t <= c.contest_deadline ? `CONTESTABLE_UNTIL_${c.contest_deadline}` : "",
    expire: c.status === "PROVISIONAL" ? (t <= c.judge_deadline ? `JUDGEABLE_UNTIL_${c.judge_deadline}` : "") : c.status === "APPEALED" ? (t <= c.appeal_deadline ? `APPEAL_JUDGEABLE_UNTIL_${c.appeal_deadline}` : "") : `NOTHING_TO_EXPIRE_IN_${c.status}`,
    appeal: c.status !== "CONTESTABLE" ? "NOT_CONTESTABLE" : t > c.contest_deadline ? "CONTEST_WINDOW_CLOSED" : "",
  };
}

function Actions({ c, judged, reload }: { c: Check; judged: boolean; reload: () => void }) {
  const w = useWallet();
  const tx = useTx();
  const [text, setText] = useState("");
  const [alt, setAlt] = useState("");
  const r = reasons(c, judged);
  const reg = registry();
  const noWallet = !w.account ? "connect a wallet first" : w.onWrongNetwork ? "switch to Studio Dev first" : "";
  const run = (label: string, address: string, fn: string, args: (string | number)[], value: bigint, confirm: () => Promise<boolean>) =>
    tx.run((onProgress) => send(w.account!, address, fn, args, value, { onProgress, confirm })).then(() => reload());
  const btn = (label: string, why: string, go: () => void) => (
    <div className="flex flex-col gap-1">
      <Button variant="quiet" disabled={Boolean(why || noWallet) || tx.busy} onClick={go}>{label}</Button>
      <span className="font-mono text-[11px] text-ink-3">{noWallet || why || "available now"}</span>
    </div>
  );
  return (
    <div>
      <div className="grid gap-3 sm:grid-cols-4">
        {btn("Ask validators to judge", r.judge, () => void run("judge", ADDR.judge, "judge", [reg, c.check_id], 0n,
          async () => Boolean((await getJudgment(reg, c.check_id, c.round)).found)))}
        {btn("Apply the ruling", r.rule, () => void run("rule", reg, "rule", [c.check_id], 0n,
          async () => (await getCheck(c.check_id)).status !== c.status))}
        {btn("Finalize", r.finalize, () => void run("finalize", reg, "finalize", [c.check_id], 0n,
          async () => (await getCheck(c.check_id)).status === "FINAL"))}
        {btn("Expire (deadline passed)", r.expire, () => void run("expire", reg, "expire", [c.check_id], 0n,
          async () => (await getCheck(c.check_id)).status === "FINAL"))}
      </div>
      {c.status === "CONTESTABLE" && (
        <form className="mt-6 rounded-lg border border-rule bg-sheet p-4" onSubmit={(e) => {
          e.preventDefault();
          void run("appeal", reg, "appeal", [c.check_id, text, Number(alt || 0)], 10n ** 17n,
            async () => (await getCheck(c.check_id)).status === "APPEALED");
        }}>
          <h3 className="font-serif text-lg font-semibold">Appeal this ruling</h3>
          <p className="mt-1 text-sm text-ink-2">
            One appeal per check, with a 0.1 GEN bond and new counter-evidence (40 to 2,000 characters, not a resend of what is on record).
            {c.ruling === "DEVIATES" ? " A DEVIATES ruling is appealed by the DAO's controller; on an unclaimed listing, by anyone but the filer." : " An AS_VOTED ruling can be appealed by anyone but the DAO's controller."}
            {" "}A fresh validator panel judges it. Counter-evidence cannot change what code settled; naming the proposal this execution really implements can.
          </p>
          <textarea className={`${inputCls} mt-3 min-h-28`} value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} aria-label="Counter-evidence" placeholder="What does the proposal say that the ruling missed?" />
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="block font-semibold">Different proposal (VoteReader record id, optional)</span>
              <input className={`${inputCls} mt-1 w-40`} inputMode="numeric" value={alt} onChange={(e) => setAlt(e.target.value.replace(/\D/g, ""))} placeholder="0" />
            </label>
            <Button type="submit" disabled={Boolean(r.appeal || noWallet) || tx.busy || text.trim().length < 40}>Appeal with 0.1 GEN</Button>
            <span className="font-mono text-[11px] text-ink-3">{noWallet || r.appeal || (text.trim().length < 40 ? `${40 - text.trim().length} more characters` : "")}</span>
          </div>
        </form>
      )}
      <TxStatus progress={tx.progress} />
    </div>
  );
}

export function CheckView({ id }: { id: number }) {
  const reg = registry();
  const check = useView(`check:${reg}:${id}`, () => getCheck(id), 20_000);
  const c = check.data;
  const ex = useView(c?.found ? `exec:${c.exec_id}` : null, () => getExecution(c!.exec_id));
  const voteId = c && c.round === 1 && c.appeal_vote_id > 0 ? c.appeal_vote_id : c?.vote_id;
  const vote = useView(c?.found ? `vote:${voteId}` : null, () => getProposal(voteId!));
  const judged = useView(c?.found ? `judged:${reg}:${id}:${c.round}` : null, () => getJudgment(reg, id, c!.round), 20_000);

  if (check.error) return <ErrorNote error={check.error} retry={() => void check.mutate()} />;
  if (!c) return <div className="mt-10 space-y-3"><Skeleton className="h-24 w-full" /><Skeleton className="h-96 w-full" /></div>;
  if (!c.found) return <p className="mt-10 text-ink-2">There is no check #{id} on this registry. Switch between Canonical and Demo at the top if it lives on the other one.</p>;
  const detail = c.appeal_detail ?? c.ruling_detail ?? null;
  const quotes = (detail?.actions ?? []).map((a) => a.quote).filter(Boolean);
  return (
    <div>
      <div className="mt-8 flex flex-wrap items-center gap-3">
        <h1 className="font-serif text-3xl font-semibold">Check #{c.check_id}</h1>
        <StatusPill status={c.status} />
        <span className="text-sm text-ink-2">filed {relativeTime(c.filed_at)} by <Addr value={c.filer} /> with {formatGen(c.stake)} GEN</span>
      </div>
      <div className="mt-6"><VerdictBanner check={c} ex={ex.data} vote={vote.data} animate /></div>
      <div className="mt-6"><Timeline c={c} /></div>
      <div className="mt-8 grid gap-6 lg:grid-cols-2 lg:items-start">
        {vote.data ? <Ballot vote={vote.data} quotes={quotes} /> : <Skeleton className="h-[30rem] w-full" />}
        {ex.data ? <Receipt ex={ex.data} ruled={detail?.actions ?? null} /> : <Skeleton className="h-[30rem] w-full" />}
      </div>
      {c.appeal_text && (
        <Section title="Appeal">
          <p className="text-sm text-ink-2">By <Addr value={c.appellant} /> with {formatGen(c.appeal_bond)} GEN{c.appeal_cid ? <>, naming proposal <span className="font-mono">{shortAddress(c.appeal_cid, 8)}</span></> : null}.</p>
          <blockquote className="mt-2 border-l-2 border-booth pl-3 font-serif">{c.appeal_text}</blockquote>
          {c.appeal_ruling && <p className="mt-2 text-sm">Fresh panel: <strong>{c.appeal_ruling.split("_").join(" ").toLowerCase()}</strong>. The first ruling was {c.ruling.split("_").join(" ").toLowerCase()}.</p>}
        </Section>
      )}
      {c.status === "FINAL" && (
        <Section title="Where the money went">
          <ul className="space-y-1 text-sm">
            {c.settlement.map(([what, who, amt], i) => (
              <li key={i} className="flex flex-wrap justify-between gap-2 border-b border-rule-2 py-1.5">
                <span>{what}</span><span className="tabular">{formatGen(amt)} GEN to {who.startsWith("0x") ? <Addr value={who} /> : who}</span>
              </li>
            ))}
          </ul>
          {c.final_verdict === "DEVIATES" && <p className="mt-2 text-sm text-ink-2">Severity {c.severity.toLowerCase()} ({c.severity_bps / 100}% of the pledge at filing, {formatGen(c.pledge_at_filing)} GEN), by the frozen table in the registry.</p>}
        </Section>
      )}
      <Section title="Move it forward">
        <p className="mb-4 text-sm text-ink-2">Every step is permissionless and every state has a deadline. These buttons call the contracts from your wallet; each is disabled with the reason the contract itself would give.</p>
        <Actions c={c} judged={Boolean(judged.data?.found)} reload={() => { void check.mutate(); void judged.mutate(); }} />
      </Section>
      <Section title="Evidence bound at filing">
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <div><dt className="text-ink-3">ExecReader record</dt><dd>#{c.exec_id}, evidence sha256 <span className="break-anywhere font-mono text-xs">{c.exec_sha}</span></dd></div>
          <div><dt className="text-ink-3">VoteReader record</dt><dd>#{c.vote_id}, evidence sha256 <span className="break-anywhere font-mono text-xs">{c.vote_sha}</span></dd></div>
          <div><dt className="text-ink-3">Filer&apos;s note</dt><dd>{c.note || "none"}</dd></div>
          <div><dt className="text-ink-3">Judged</dt><dd>{detail ? <>by <Addr value={detail.judged_by} /> {relativeTime(detail.judged_at)}, input sha256 <span className="break-anywhere font-mono text-xs">{detail.input_sha256}</span></> : "not yet"}</dd></div>
        </dl>
      </Section>
    </div>
  );
}
