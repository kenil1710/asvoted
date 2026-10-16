"use client";

import { getConfig } from "@/lib/contract";
import { ADDR } from "@/lib/deployments";
import { formatGen } from "@/lib/format";
import { Section, Skeleton, useView } from "@/components/ui";

const CONTRACTS = [
  ["ExecReader", "Reads one Safe execution from two RPCs that must agree, at a finalized block the leader names. Recomputes the Safe transaction hash and requires the Safe's own ExecutionSuccess for it. Decodes every action, including every inner call of a MultiSend batch."],
  ["VoteReader", "Fetches the Snapshot proposal by IPFS CID and hashes the bytes against the CID in the contract. Requires the hub to report the same proposal, closed, with final scores. Computes from the scores whether it passed. Records whether the Safe is listed in the space's treasuries, and resolves ENS names at two blocks."],
  ["AsVotedJudge", "Rules on every action: code first for every address and amount, the model only for calls the proposal describes in words, with a verbatim quote that code checks."],
  ["AsVotedRegistry", "DAO listings, pledges, checks, appeals, deadlines and money. Holds the stakes and pays by pull balances."],
  ["DaoStanding + GrantGate", "One question another contract can ask: has this DAO had a final DEVIATES ruling in the last 30 days? GrantGate refuses to act for a DAO that has."],
];

export default function Docs() {
  const cfg = useView(`cfg:${ADDR.registry}`, () => getConfig(ADDR.registry));
  const c = cfg.data;
  return (
    <div className="max-w-3xl">
      <h1 className="mt-10 font-serif text-4xl font-semibold">How a check is decided</h1>
      <p className="mt-4 font-serif text-lg leading-relaxed">
        Token holders vote on Snapshot, off chain. A Safe multisig then executes the result on chain. Nothing in between checks
        that what the signers executed is what passed. AsVoted reads both sides itself, rules on each action the Safe performed,
        and backs the ruling with money.
      </p>

      <Section title="Five contracts">
        <dl className="space-y-4">
          {CONTRACTS.map(([n, d]) => (
            <div key={n}><dt className="font-semibold">{n}</dt><dd className="mt-0.5 text-ink-2">{d}</dd></div>
          ))}
        </dl>
      </Section>

      <Section title="Per action, in this order">
        <ol className="list-decimal space-y-3 pl-5 text-ink-2">
          <li><strong className="text-ink">The action list is the calldata.</strong> No model chooses which actions exist. A DELEGATECALL to anything that is not a known MultiSend stays in the list as a DELEGATECALL; unknown function selectors stay as raw calls; a gas refund the Safe paid is an action too.</li>
          <li><strong className="text-ink">Value sent to an address the proposal never mentions</strong> (as 0x… or as an ENS name that resolved the same way at the vote and now) is <em>not in the proposal</em>.</li>
          <li><strong className="text-ink">Amounts.</strong> Code reads the amounts stated next to the recipient (same line, then paragraph, then section). All transfers to that recipient in one token family are summed, so splitting a payment does not get under the cap. More than the largest stated amount plus 0.5% is <em>over amount</em>. Amounts stated there only in other tokens also count as over. No amount stated at all is <em>unclear</em>.</li>
          <li><strong className="text-ink">Calls.</strong> A call to a contract the proposal does not identify, or one that passes an address the proposal does not mention, is <em>not in the proposal</em>. A DELEGATECALL to an unnamed address is the most severe case.</li>
          <li><strong className="text-ink">Words.</strong> Only what is left, an identified contract called with mentioned arguments, goes to the model, which answers authorized, not authorized or unclear, with a quote. The quote must appear in the proposal text, and two answers must agree; otherwise the action is unclear.</li>
        </ol>
        <p className="mt-4 text-ink-2">Overall, by code: <strong className="text-ok">as voted</strong> if every action is authorized and the vote passed; <strong className="text-dev">deviates</strong> if any action is not in the proposal or over amount; <strong className="text-unclear">unclear</strong> otherwise. The wording is always dated and neutral, and says only what it establishes about the one proposal the filer named: &quot;Execution X on date includes an action proposal CIP-16 (closed date) does not cover.&quot; If a different proposal covers it, the DAO appeals by naming that proposal.</p>
      </Section>

      <Section title="What the model is never allowed to decide">
        <ul className="list-disc space-y-1.5 pl-5 text-ink-2">
          <li>which actions an execution contains</li>
          <li>any address: who received what, which contract was called, what an ENS name resolves to</li>
          <li>any amount, decimal, token or tolerance</li>
          <li>any chain fact: the block, the transaction, whether it succeeded, the Safe hash</li>
          <li>whether the vote passed, and whether the Safe belongs to the space</li>
          <li>the overall verdict, its severity, or where money goes</li>
        </ul>
      </Section>

      <Section title="When validators disagree">
        <p className="text-ink-2">
          Every reader result must be byte-identical between leader and validators. In the judge, the leader asks the model twice and keeps
          a verdict only where both answers agree; a validator does the same and must arrive at the same verdict for every action. If it does
          not, the transaction is not accepted and nothing is written. The check stays provisional, anyone can ask for judgment again, and
          when the judge deadline passes, anyone can expire it, which records UNCLEAR and refunds the stake. A disagreement is never recorded
          as a verdict.
        </p>
      </Section>

      <Section title="Money and deadlines">
        {!c ? <Skeleton className="h-40 w-full" /> : (
          <div className="space-y-3 text-ink-2">
            <p>Filing stake {formatGen(c.check_stake)} GEN, appeal bond {formatGen(c.appeal_bond)} GEN, read from the canonical registry. Contest window {c.contest_s / 3600} hours (demo: 90 seconds), judge deadline {c.judge_deadline_s / 3600} hours, pledge withdrawal delay {c.withdraw_delay_s / 60} minutes, then {(c.withdraw_late_s ?? 0) / 3600} more hours so an execution made just before the unlock can finalize and be filed.</p>
            <p>A final DEVIATES ruling slashes the DAO&apos;s pledge, as it stood at filing, by the worst action&apos;s severity, and pays the slash to whoever proved the deviation. A final AS_VOTED ruling adds the challenger&apos;s stake to the pledge. UNCLEAR refunds everything.</p>
            <table className="w-full text-sm">
              <caption className="sr-only">Severity table</caption>
              <tbody>{c.severity_table.map(([l, bps, why], i) => <tr key={i} className="border-b border-rule-2"><td className="py-1.5 pr-3 font-semibold">{l.charAt(0) + l.slice(1).toLowerCase()}</td><td className="py-1.5 pr-3 tabular">{bps / 100}% of the pledge</td><td className="py-1.5">{why}</td></tr>)}</tbody>
            </table>
            <p>Every state has a deadline and an exit anyone may call: judge, rule, finalize, expire. Payouts are pull balances, claimed by their owner.</p>
          </div>
        )}
      </Section>

      <Section title="Who can do what">
        <ul className="list-disc space-y-1.5 pl-5 text-ink-2">
          <li>Anyone can list a DAO, but only if the space&apos;s own Snapshot settings name the Safe as a treasury on that chain, read within the last hour.</li>
          <li>Only an admin or moderator of the space, read from the hub, can claim a listing; only the controller can pledge or withdraw.</li>
          <li>Anyone can file a check. One check per execution; an execution and proposal pair is never filed twice.</li>
          <li>A DEVIATES ruling is appealed by the DAO&apos;s controller, who may name the proposal the execution really implements; an AS_VOTED ruling by anyone but the controller.</li>
          <li>There is no owner, admin or setter in any contract.</li>
        </ul>
      </Section>
    </div>
  );
}
