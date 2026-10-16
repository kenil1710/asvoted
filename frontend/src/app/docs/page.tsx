"use client";

import { getConfig } from "@/lib/contract";
import { ADDR } from "@/lib/deployments";
import { formatGen } from "@/lib/format";
import { Section, Skeleton, useView } from "@/components/ui";

const CONTRACTS = [
  ["ExecReader", "Reads one Safe execution from two RPCs that must agree, at a finalized block the leader names. Recomputes the Safe transaction hash and requires the Safe's own ExecutionSuccess for it. Decodes every action, including every inner call of a MultiSend batch."],
  ["VoteReader", "Fetches the Snapshot proposal by IPFS CID and hashes the bytes against the CID in the contract. Requires the hub to report the same proposal, closed, with final scores. Computes from the scores whether it passed. Records whether the Safe is listed in the space's treasuries. Resolves the proposal's ENS names as voters saw them, at the Ethereum block of the vote's snapshot (mapped from the space's own network), and notes where any had moved by the execution."],
  ["AsVotedJudge", "Rules on every action: code first for every address and amount, the model only for calls the proposal describes in words, with a verbatim quote that code checks."],
  ["AsVotedRegistry", "DAO listings, pledges, checks, appeals, deadlines and money. Holds the stakes and pays by pull balances."],
  ["DaoStanding + GrantGate", "One question another contract can ask: has this DAO (a Snapshot space and its Safe) a final DEVIATES ruling on an execution from the last 30 days? GrantGate refuses to act for a DAO that has."],
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
        <p className="text-ink-2">When code cannot decide with certainty, the action is <em>unclear</em>, decided by code. The model is never asked.</p>
        <ol className="mt-3 list-decimal space-y-3 pl-5 text-ink-2">
          <li><strong className="text-ink">The action list is the calldata</strong> of one Safe transaction (or, for a relayed SafeL2 Safe, its own SafeMultiSigTransaction log), bound to the Safe&apos;s ExecutionSuccess. No model chooses which actions exist. A DELEGATECALL to anything that is not a known MultiSend stays a DELEGATECALL; unknown selectors stay raw calls; a gas refund is an action too.</li>
          <li><strong className="text-ink">Quoted calldata.</strong> An action whose exact calldata the proposal quotes, in a paragraph that names its target, is <em>authorized</em>.</li>
          <li><strong className="text-ink">Wrapping.</strong> Wrapping or unwrapping ETH with a listed WETH keeps the value in the Safe: <em>neutral</em>, a conversion, not a payment.</li>
          <li><strong className="text-ink">Who is paid.</strong> Every call&apos;s ETH value is a transfer to the call&apos;s target, and token transfers, transferFroms, approvals and gas refunds are payments. A payee (and a transferFrom&apos;s source) must be named in the proposal, by address or by an ENS name as it resolved when voters voted (at the Ethereum block of the vote&apos;s snapshot, on every network). A payee the proposal never names is <em>not in the proposal</em>. If a name had moved by the time the Safe paid, paying the address voters saw is fine, and paying the new address is <em>unclear</em>. If names cannot be resolved, an unnamed payee is <em>unclear</em>.</li>
          <li><strong className="text-ink">Tokens.</strong> A token counts only if it is on the judge&apos;s token list, fixed at deployment, or the proposal names its address. Its symbol() alone never identifies it; an unidentified token is <em>unclear</em>.</li>
          <li><strong className="text-ink">The cap.</strong> The cap is the one amount for that token on the payee&apos;s own line, list item or table row. These make the payment <em>unclear</em>, never authorized:
            <ul className="mt-1 list-disc pl-5">
              <li>no amount there, or two different ones;</li>
              <li>only a minimum;</li>
              <li>a refusal in the amount&apos;s sentence;</li>
              <li>a status word such as rejected, withdrawn, cancelled, not or void anywhere in its line or bullet subtree;</li>
              <li>a later paragraph that names the payee or amends a figure for that token with a different amount;</li>
              <li>an amount on a line that names several addresses ambiguously.</li>
            </ul>
            Text under a losing choice&apos;s heading or paragraph (Against, No, or another option) never sets a cap. If several choices approve something and the winner&apos;s own text cannot be found, nothing caps.</li>
          <li><strong className="text-ink">Totals.</strong> Payments to the payee in that token family are summed: within the execution, and across every other filing under the same proposal, whatever its outcome (per calendar period for &quot;per month&quot; amounts).
            <ul className="mt-1 list-disc pl-5">
              <li>Above the cap plus 0.5% is <em>over amount</em>. Amounts stated only in another token are also over. Dollar figures paid in another token are <em>unclear</em>, because no prices are used.</li>
              <li>The same payment is also counted with every filing of the DAO that paid this payee under any of its proposals. If that changes the ruling, the action is <em>unclear</em>, so switching proposals cannot reset a total.</li>
            </ul></li>
          <li><strong className="text-ink">Calls.</strong> These are <em>not in the proposal</em>: a DELEGATECALL to an unnamed address, a call to a contract the proposal does not identify, and a call that passes an unnamed address argument (a word at least 2^96 and below 2^160). Calls nested in bytes arguments (multicall, router sub-calls) are read through the ABI to three levels. An unnamed address there is <em>unclear</em>, and so is anything nested deeper.</li>
          <li><strong className="text-ink">Words.</strong> Only what is left, an identified contract called with named arguments, goes to the model. It answers authorized, not authorized or unclear, with a quote. The quote must appear in the proposal and two answers must agree; otherwise the action is <em>unclear</em>.</li>
        </ol>
        <p className="mt-4 text-ink-2">Overall, by code: <strong className="text-ok">as voted</strong> if every action is authorized or neutral and the vote passed; <strong className="text-dev">deviates</strong> if any action is not in the proposal or over amount; <strong className="text-unclear">unclear</strong> otherwise, with no slash and no bounty. The wording is always dated and neutral, and says only what it establishes about the one proposal the filer named: &quot;Execution X on date includes an action proposal CIP-16 (closed date) does not cover.&quot;</p>
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
            <p>Filing stake {formatGen(c.check_stake)} GEN, appeal bond {formatGen(c.appeal_bond)} GEN, read from the canonical registry. Contest window {c.contest_s / 3600} hours (demo: 90 seconds), opened again for the DAO if an appeal turns AS_VOTED into DEVIATES; judge deadline {c.judge_deadline_s / 3600} hours. A pledge withdrawal waits {c.withdraw_delay_s / 3600} hours plus {(c.withdraw_late_s ?? 0) / 3600} more, so an execution made just before the request can be filed and contested, and never leaves while a check of an earlier execution is open.</p>
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
          <li>Anyone can list a DAO, but only if the space&apos;s own Snapshot settings name the Safe as a treasury on that chain, read within the last hour. A DAO is the pair (space, Safe). A listing is <em>verified</em> only when the Safe itself owns the space&apos;s ENS name, so no single signer can earn the badge.</li>
          <li>Only an admin or moderator of the space, read from the hub, can claim a listing; only the controller can pledge or withdraw.</li>
          <li>Anyone can file a check. One check per execution; an execution and proposal pair is never filed twice.</li>
          <li>A DEVIATES ruling is the DAO&apos;s to answer. Its controller may appeal and may name the proposal the execution really implements; nobody else may name another proposal. On an unclaimed listing anyone but the filer may appeal a DEVIATES, but that never uses up the DAO&apos;s turn. An admin who claims within the window takes the appeal over, and if the stranger&apos;s appeal loses, the window reopens for the controller.</li>
          <li>An AS_VOTED ruling can be appealed by anyone but the controller. If the fresh panel says DEVIATES, the DAO gets its own window to answer before anything is final.</li>
          <li>There is no owner, admin or setter in any contract.</li>
        </ul>
      </Section>
    </div>
  );
}
