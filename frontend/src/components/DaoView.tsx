"use client";

import { useState } from "react";
import { ADDR } from "@/lib/deployments";
import { gate, getBinding, getBindingId, getClaimable, getConfig, getDao, getDaoChecks, getGateRequests, getStanding, registry, send } from "@/lib/contract";
import { CHAIN_LABEL, formatGen, isoDate, parseGen, relativeTime } from "@/lib/format";
import { CheckList } from "./CheckList";
import { TxStatus, useTx } from "./tx";
import { useWallet } from "./WalletProvider";
import { Addr, Button, ErrorNote, inputCls, Section, Skeleton, useView } from "./ui";

function now() { return Math.floor(Date.now() / 1000); }

export function DaoView({ id }: { id: number }) {
  const reg = registry();
  const w = useWallet();
  const tx = useTx();
  const dao = useView(`dao:${reg}:${id}`, () => getDao(id), 30_000);
  const checks = useView(`daochecks:${reg}:${id}`, () => getDaoChecks(id, 0, 50), 30_000);
  const stand = useView(`standing:${reg}:${id}`, () => getStanding(id, now()), 60_000);
  const cfg = useView(`cfg:${reg}`, () => getConfig());
  const mine = useView(w.account ? `claimable:${reg}:${w.account}` : null, () => getClaimable(w.account!), 30_000);
  const gateLog = useView(`gate:${gate()}`, () => getGateRequests(), 60_000);
  const [amount, setAmount] = useState("1");
  const [purpose, setPurpose] = useState("Release grant tranche");
  const d = dao.data;
  if (dao.error) return <ErrorNote error={dao.error} retry={() => void dao.mutate()} />;
  if (!d) return <Skeleton className="mt-10 h-64 w-full" />;
  if (!d.found) return <p className="mt-10 text-ink-2">No DAO #{id} on this registry.</p>;
  const me = w.account?.toLowerCase() ?? "";
  const isController = Boolean(me) && d.controller === me;
  const noWallet = !w.account ? "connect a wallet first" : w.onWrongNetwork ? "switch to Studio Dev first" : "";
  const demoSeam = cfg.data?.mode === "DEMO" && (cfg.data?.demo_controllers ?? []).includes(me);
  const refresh = () => { void dao.mutate(); void mine.mutate(); void stand.mutate(); void gateLog.mutate(); };
  const wei = parseGen(amount);
  const withdrawWhy = !isController ? "ONLY_THE_DAOS_CONTROLLER" : d.open_checks > 0 ? `CHECKS_OPEN_${d.open_checks}` : wei === null || wei <= 0n || wei > BigInt(d.pledge) ? "AMOUNT_OUT_OF_RANGE" : "";
  const execWhy = BigInt(d.withdraw_amount) === 0n ? "NO_WITHDRAWAL_PENDING" : now() < d.withdraw_at ? `WITHDRAWAL_LOCKED_UNTIL_${d.withdraw_at}` : d.open_checks > 0 ? `CHECKS_OPEN_${d.open_checks}` : "";

  async function claimDao() {
    await tx.run(async (onProgress) => {
      const bid = Number(await getBindingId(d!.space, d!.chain, d!.safe));
      const b = bid ? await getBinding(bid) : null;
      if (!b || now() - b.read_at > 3000) {
        const r = await send(w.account!, ADDR.voteReader, "read_space", [d!.space, d!.chain, d!.safe], 0n, { onProgress,
          confirm: async () => Number(await getBindingId(d!.space, d!.chain, d!.safe)) > bid });
        if (r.kind !== "ok") return;
      }
      await send(w.account!, reg, "claim_dao", [id], 0n, { onProgress, confirm: async () => (await getDao(id)).controller === me });
    });
    refresh();
  }
  const act = (fn: string, args: (string | number)[], value: bigint, confirm: () => Promise<boolean>, address: string = reg) =>
    tx.run((onProgress) => send(w.account!, address, fn, args, value, { onProgress, confirm })).then(refresh);

  return (
    <div>
      <div className="mt-10 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-4xl font-semibold">{d.space}</h1>
          <p className="mt-1 text-ink-2">Safe <Addr value={d.safe} chain={d.chain} size={6} /> on {CHAIN_LABEL[d.chain]} · listed {isoDate(d.listed_at)} by <Addr value={d.lister} /></p>
        </div>
        <div className={`rounded-lg border-2 px-4 py-3 ${stand.data?.ok ? "border-ok bg-ok-soft" : "border-dev bg-dev-soft"}`}>
          <p className={`font-semibold ${stand.data?.ok ? "text-ok" : "text-dev"}`}>{stand.data ? (stand.data.ok ? "Executing as voted" : "Not in good standing") : "Reading standing"}</p>
          <p className="text-xs text-ink-2">{stand.data ? (stand.data.reasons[0] ?? `no final DEVIATES ruling in the last ${stand.data.window_days} days`) : ""} (DaoStanding)</p>
        </div>
      </div>
      <section aria-label="Record" className="mt-8 grid grid-cols-2 gap-6 sm:grid-cols-5">
        {[["final as voted", d.as_voted], ["final deviates", d.deviates], ["final unclear", d.unclear], ["open checks", d.open_checks], ["GEN pledged", formatGen(d.pledge, 2)]].map(([l, v]) => (
          <div key={String(l)} className="border-l border-rule pl-4"><p className="font-serif text-3xl font-semibold tabular">{v}</p><p className="text-sm text-ink-2">{l}</p></div>
        ))}
      </section>
      <Section title="Checks">
        {checks.data ? <CheckList checks={checks.data.checks} daoNames={{ [d.dao_id]: d.space }} /> : <Skeleton className="h-40 w-full" />}
      </Section>
      <Section title="The pledge">
        <p className="max-w-3xl text-sm text-ink-2">
          A pledge says &quot;we execute only what passed&quot;. A final DEVIATES ruling slashes it by the frozen severity table and pays the slash
          to whoever proved the deviation; a final AS_VOTED ruling adds the challenger&apos;s stake to it. Only the listing&apos;s controller, an
          admin or moderator of {d.space} on Snapshot, can pledge or withdraw. {d.controller ? <>Controller: <Addr value={d.controller} />.</> : "This listing is unclaimed."}
          {cfg.data?.mode === "DEMO" && " On the demo registry the test addresses fixed at deployment may also claim, so every path can be tried."}
        </p>
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <div className="rounded-lg border border-rule bg-sheet p-4">
            <h3 className="font-semibold">Claim the listing</h3>
            <p className="mt-1 text-xs text-ink-3">Reads the space&apos;s admins and moderators from the hub, then claims.</p>
            <Button className="mt-3" variant="quiet" disabled={Boolean(noWallet) || tx.busy || isController} onClick={() => void claimDao()}>Claim as space admin</Button>
            <p className="mt-1 font-mono text-[11px] text-ink-3">{noWallet || (isController ? "you control this listing" : demoSeam ? "allowed by the demo seam" : "refused unless you are a space admin or moderator")}</p>
          </div>
          <div className="rounded-lg border border-rule bg-sheet p-4">
            <h3 className="font-semibold">Pledge or withdraw</h3>
            <input className={`${inputCls} mt-2`} value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" aria-label="Amount in GEN" />
            <div className="mt-3 flex flex-wrap gap-2">
              <Button disabled={!isController || Boolean(noWallet) || tx.busy || wei === null || wei < 10n ** 17n}
                onClick={() => void act("pledge", [id], wei!, async () => BigInt((await getDao(id)).pledge) > BigInt(d.pledge))}>Pledge</Button>
              <Button variant="quiet" disabled={Boolean(withdrawWhy || noWallet) || tx.busy}
                onClick={() => void act("request_withdrawal", [id, wei!.toString()], 0n, async () => BigInt((await getDao(id)).withdraw_amount) > 0n)}>Request withdrawal</Button>
            </div>
            <p className="mt-1 font-mono text-[11px] text-ink-3">{noWallet || (!isController ? "ONLY_THE_DAOS_CONTROLLER" : withdrawWhy || "available now")}</p>
          </div>
          <div className="rounded-lg border border-rule bg-sheet p-4">
            <h3 className="font-semibold">Pending withdrawal</h3>
            <p className="mt-1 text-sm">{BigInt(d.withdraw_amount) > 0n ? <>{formatGen(d.withdraw_amount)} GEN, unlocks {relativeTime(d.withdraw_at) === "just now" ? "now" : new Date(d.withdraw_at * 1000).toISOString().slice(0, 16).replace("T", " ") + " UTC"}</> : "none"}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button variant="quiet" disabled={Boolean(execWhy || noWallet) || tx.busy} onClick={() => void act("execute_withdrawal", [id], 0n, async () => BigInt((await getDao(id)).withdraw_amount) === 0n)}>Execute</Button>
              <Button variant="quiet" disabled={!isController || BigInt(d.withdraw_amount) === 0n || tx.busy} onClick={() => void act("cancel_withdrawal", [id], 0n, async () => BigInt((await getDao(id)).withdraw_amount) === 0n)}>Cancel</Button>
            </div>
            <p className="mt-1 font-mono text-[11px] text-ink-3">{noWallet || execWhy || "anyone may execute it now"}</p>
          </div>
        </div>
        {w.account && (
          <div className="mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-rule bg-sheet p-4">
            <p className="text-sm">Your claimable balance on this registry: <strong className="tabular">{mine.data ? formatGen(mine.data.claimable) : "…"} GEN</strong> (claimed so far {mine.data ? formatGen(mine.data.claimed) : "…"})</p>
            <Button variant="quiet" disabled={!mine.data || BigInt(mine.data.claimable) === 0n || tx.busy}
              onClick={() => void act("claim", [], 0n, async () => BigInt((await getClaimable(me)).claimable) === 0n)}>Claim payout</Button>
            <span className="text-xs text-ink-3">On Studio Dev the transfer is posted but queued, not delivered.</span>
          </div>
        )}
        <TxStatus progress={tx.progress} />
      </Section>
      <Section title="A contract that asks before it acts">
        <p className="max-w-3xl text-sm text-ink-2">
          GrantGate is a small consumer: it carries out a request for a DAO only if DaoStanding says the DAO has no final DEVIATES ruling in the last 30 days. Every request is logged, carried out or refused.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <input className={`${inputCls} max-w-sm`} value={purpose} onChange={(e) => setPurpose(e.target.value)} aria-label="What to ask GrantGate to do" />
          <Button variant="quiet" disabled={Boolean(noWallet) || tx.busy} onClick={() => void act("request_grant", [id, purpose], 0n,
            async () => ((await getGateRequests()).total) > (gateLog.data?.total ?? 0), gate())}>Ask GrantGate</Button>
        </div>
        {gateLog.data && gateLog.data.requests.filter((r) => r.dao_id === id).length > 0 && (
          <ul className="mt-4 divide-y divide-rule rounded-lg border border-rule bg-sheet text-sm">
            {gateLog.data.requests.filter((r) => r.dao_id === id).map((r) => (
              <li key={r.request_id} className="flex flex-wrap justify-between gap-2 px-4 py-2.5">
                <span>#{r.request_id} {r.purpose}</span>
                <span className={r.carried_out ? "text-ok" : "text-dev"}>{r.carried_out ? "carried out" : `refused: ${r.reasons.join("; ")}`}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
