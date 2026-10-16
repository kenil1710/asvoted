"use client";

import Link from "next/link";
import { useState } from "react";
import { ADDR } from "@/lib/deployments";
import { getCheckIdByTx, getDaos, getExecution, getExecutionId, getJudgment, getNamesAt, getProposal, getProposalId, registry, send } from "@/lib/contract";
import { CHAIN_LABEL, isTxHash, shortAddress } from "@/lib/format";
import { TxStatus, useTx } from "@/components/tx";
import { useWallet } from "@/components/WalletProvider";
import { Button, Field, inputCls, Section, useView } from "@/components/ui";

const STEPS = ["Find the Safe nonce", "Read the execution", "Read the proposal", "File with 0.1 GEN", "Judge", "Apply the ruling"];

export default function FilePage() {
  const w = useWallet();
  const tx = useTx();
  const reg = registry();
  const daos = useView(`daos:${reg}`, () => getDaos(0, 50));
  const [daoId, setDaoId] = useState(0);
  const [hash, setHash] = useState("");
  const [cid, setCid] = useState("");
  const [note, setNote] = useState("");
  const [at, setAt] = useState(-1);
  const [log, setLog] = useState<string[]>([]);
  const [done, setDone] = useState(0);
  const dao = daos.data?.daos.find((d) => d.dao_id === daoId);
  const noWallet = !w.account ? "connect a wallet first" : w.onWrongNetwork ? "switch to Studio Dev first" : "";
  const bad = !dao ? "choose a DAO" : !isTxHash(hash) ? "enter the execution's transaction hash" : !/^(Qm[1-9A-HJ-NP-Za-km-z]{44}|b[a-z2-7]{50,})$/.test(cid.trim().replace(/^ipfs:\/\//, "")) ? "enter the proposal's IPFS CID" : "";
  const say = (s: string) => setLog((l) => [...l, s]);

  async function go() {
    if (!dao) return;
    const t = hash.trim().toLowerCase();
    const c = cid.trim().replace(/^ipfs:\/\//, "");
    setLog([]);
    setDone(0);
    await tx.run(async (onProgress) => {
      const existing = Number(await getCheckIdByTx(dao.chain, dao.safe, t));
      if (existing) { say(`This execution already has check #${existing}; duplicates are refused.`); setDone(existing); return; }
      setAt(0);
      let execId = Number(await getExecutionId(dao.chain, dao.safe, t));
      if (!execId) {
        const n = await (await fetch(`/api/nonce?chain=${dao.chain}&safe=${dao.safe}&tx=${t}`)).json();
        if (n.error) { say(`Nonce: ${n.error}.`); onProgress({ phase: "failed", hash: null, message: n.error }); return; }
        say(`Safe nonce ${n.nonce} reproduces Safe tx hash ${shortAddress(n.safeTxHash, 6)} (the contract checks this again).`);
        setAt(1);
        const r = await send(w.account!, ADDR.execReader, "read_execution", [dao.chain, dao.safe, t, n.nonce], 0n, { onProgress,
          confirm: async () => Number(await getExecutionId(dao.chain, dao.safe, t)) > 0 });
        if (r.kind !== "ok") return;
        execId = Number(await getExecutionId(dao.chain, dao.safe, t));
      }
      say(`Execution record #${execId}.`);
      setAt(2);
      let voteId = Number(await getProposalId(c, dao.chain, dao.safe));
      const v = voteId ? await getProposal(voteId) : null;
      if (!v || Date.now() / 1000 - v.read_at > 3000) {
        const before = voteId;
        const r = await send(w.account!, ADDR.voteReader, "read_proposal", [c, dao.chain, dao.safe], 0n, { onProgress,
          confirm: async () => Number(await getProposalId(c, dao.chain, dao.safe)) > before });
        if (r.kind !== "ok") return;
        voteId = Number(await getProposalId(c, dao.chain, dao.safe));
      }
      say(`Proposal record #${voteId}.`);
      // ENS names count only as they resolved when the Safe acted (the execution's L1 block)
      const pv = await getProposal(voteId);
      const ev = await getExecution(execId);
      if (pv.ens_names?.length && ev.l1_block > 0 && !(await getNamesAt(voteId, ev.l1_block)).found) {
        const r = await send(w.account!, ADDR.voteReader, "read_names_at", [voteId, ev.l1_block], 0n, { onProgress,
          confirm: async () => Boolean((await getNamesAt(voteId, ev.l1_block)).found) });
        if (r.kind !== "ok") return;
        say(`ENS names resolved as of Ethereum block ${ev.l1_block}.`);
      }
      setAt(3);
      const f = await send<{ check_id: number }>(w.account!, reg, "file_check", [dao.dao_id, execId, voteId, note], 10n ** 17n, { onProgress,
        confirm: async () => Number(await getCheckIdByTx(dao.chain, dao.safe, t)) > 0 });
      if (f.kind !== "ok") return;
      const checkId = Number(await getCheckIdByTx(dao.chain, dao.safe, t));
      say(`Filed as check #${checkId}.`);
      setDone(checkId);
      setAt(4);
      const j = await send(w.account!, ADDR.judge, "judge", [reg, checkId], 0n, { onProgress,
        confirm: async () => Boolean((await getJudgment(reg, checkId, 0)).found) });
      if (j.kind !== "ok") { say("Judging did not complete; anyone can ask again from the check page before the deadline."); return; }
      setAt(5);
      await send(w.account!, reg, "rule", [checkId], 0n, { onProgress, confirm: async () => true });
      setAt(6);
    });
  }

  return (
    <div>
      <h1 className="mt-10 font-serif text-4xl font-semibold">File a check</h1>
      <p className="mt-2 max-w-2xl text-ink-2">
        Name one execution of a listed DAO&apos;s Safe and the Snapshot proposal it should implement. The contracts read both themselves;
        nothing you type here is taken as evidence except the two identifiers. The stake is 0.1 GEN: refunded on DEVIATES or UNCLEAR, added to the DAO&apos;s pledge on AS_VOTED.
      </p>
      <form className="mt-8 grid gap-5 rounded-lg border border-rule bg-sheet p-5 sm:p-6" onSubmit={(e) => { e.preventDefault(); void go(); }}>
        <Field label="DAO" hint="Listed DAOs on this registry. Not here? List it on the DAOs page first.">
          <select className={inputCls} value={daoId} onChange={(e) => setDaoId(Number(e.target.value))}>
            <option value={0}>Choose a DAO</option>
            {(daos.data?.daos ?? []).map((d) => <option key={d.dao_id} value={d.dao_id}>{d.space}: Safe {shortAddress(d.safe)} on {CHAIN_LABEL[d.chain]}</option>)}
          </select>
        </Field>
        <Field label="Execution transaction hash" hint="A direct execTransaction call to the Safe, already finalized on its chain.">
          <input className={`${inputCls} font-mono`} value={hash} onChange={(e) => setHash(e.target.value)} placeholder="0x…" spellCheck={false} autoComplete="off" />
        </Field>
        <Field label="Proposal IPFS CID" hint="On snapshot.org, the proposal's IPFS link. The contract hashes the bytes against it.">
          <input className={`${inputCls} font-mono`} value={cid} onChange={(e) => setCid(e.target.value)} placeholder="bafkrei…" spellCheck={false} autoComplete="off" />
        </Field>
        <Field label="Note (optional)" hint="Shown on the check. Not evidence; the model never sees it.">
          <input className={inputCls} value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} />
        </Field>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={Boolean(bad || noWallet) || tx.busy}>File and judge</Button>
          <span className="text-sm text-ink-3">{noWallet || bad}</span>
        </div>
      </form>
      {at >= 0 && (
        <Section title="Progress">
          <ol className="grid gap-2 sm:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s} className={`rounded-md border px-3 py-2 text-sm ${i < at ? "border-rule bg-sheet text-ink" : i === at ? "border-booth bg-booth-soft font-semibold" : "border-dashed border-rule text-ink-3"}`}>
                {i + 1}. {s}{i < at ? ", done" : ""}
              </li>
            ))}
          </ol>
          <TxStatus progress={tx.progress} />
          <ul className="mt-3 space-y-1 text-sm text-ink-2">{log.map((l, i) => <li key={i}>{l}</li>)}</ul>
          {done > 0 && <p className="mt-4"><Link href={`/check/${done}`} className="font-semibold text-booth underline">Open check #{done}</Link></p>}
        </Section>
      )}
    </div>
  );
}
