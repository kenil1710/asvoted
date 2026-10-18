/**
 * Proposal discovery for the patrol: which passed Snapshot proposal does a
 * Safe execution implement?
 *
 *   - candidates: every closed proposal of the space that ended before the
 *     execution, newest first, read in pages of PAGE from the hub up to
 *     maxPages (bounded; the report says how many were read);
 *   - normalization: addresses in a proposal are accepted all-lowercase,
 *     all-uppercase or EIP-55 checksummed, compared lowercase (a mixed-case
 *     address with a wrong checksum is not used, and is reported); ENS names
 *     are normalized (ENSIP-15) and resolved; stated amounts ("50,000 USDC",
 *     "1.5 ETH", "12k DAI") are compared with the execution's transfers in the
 *     token's own decimals;
 *   - a match needs a passed proposal that names (by address or ENS name) an
 *     address the execution touches; among those, one that also states an
 *     amount the execution moves is preferred, then the newest.
 *   - anything else is unmatched, with the reason, recorded visibly by the
 *     caller (state file and the site's "Unmatched executions" page).
 */
import { decodeFunctionData, getAddress, parseAbi, type Hex } from "viem";
import { normalize } from "viem/ens";

export const PAGE = 100;
export const MAX_PAGES = 10;
export const MAX_ENS = 8;
const MULTISEND = new Set(["0x40a2accbd92bca938b02010e17a5b8929b49130d", "0xa238cbeb142c10ef7ad8442c6d1f9e89e07e7761",
  "0x998739bfdaadde7c933b942a68053933098f9eda", "0x38869bf66a61cf6bdb996a6ae40d5853fd43b526", "0x9641d764fc13c8b624c04430c7356c1c7c8102e2"]);

const safeAbi = parseAbi(["function execTransaction(address to,uint256 value,bytes data,uint8 operation,uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,address gasToken,address refundReceiver,bytes signatures)"]);
const erc20 = parseAbi(["function transfer(address to,uint256 amount)", "function transferFrom(address from,address to,uint256 amount)", "function approve(address spender,uint256 amount)"]);
const multiAbi = parseAbi(["function multiSend(bytes transactions)"]);

export interface Transfer { token: string; to: string; amount: bigint }   // token "" = native
export interface Decoded { calls: { to: string; value: bigint; data: Hex; op: number }[]; transfers: Transfer[]; touched: Set<string> }

export interface Proposal { ipfs: string; body: string; title?: string; choices: string[]; scores: number[]; scores_state: string; end: number }

const ADDR_RE = /0x[0-9a-fA-F]{40}(?![0-9a-fA-F])/g;
const ENS_RE = /(?<![\w.-])((?:[a-z0-9-]+\.)+eth)(?![\w-])/gi;
const AMOUNT_RE = /(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*([kKmM])?\s*\$?([A-Za-z][A-Za-z0-9.]{1,9})\b/g;

/** Every call of a Safe execTransaction, MultiSend unpacked, with the token and native transfers it makes. */
export function decodeExecution(input: Hex): Decoded {
  const out: Decoded = { calls: [], transfers: [], touched: new Set() };
  let a;
  try { a = decodeFunctionData({ abi: safeAbi, data: input }).args; } catch { return out; }
  const [to, value, data, op] = a;
  const push = (t: string, v: bigint, d: Hex, o: number) => {
    const target = t.toLowerCase();
    out.calls.push({ to: target, value: v, data: d, op: o });
    out.touched.add(target);
    if (v > 0n) out.transfers.push({ token: "", to: target, amount: v });
    try {
      const f = decodeFunctionData({ abi: erc20, data: d });
      if (f.functionName === "transfer") { out.transfers.push({ token: target, to: (f.args[0] as string).toLowerCase(), amount: f.args[1] as bigint }); out.touched.add((f.args[0] as string).toLowerCase()); }
      if (f.functionName === "transferFrom") { out.transfers.push({ token: target, to: (f.args[1] as string).toLowerCase(), amount: f.args[2] as bigint }); out.touched.add((f.args[0] as string).toLowerCase()); out.touched.add((f.args[1] as string).toLowerCase()); }
      if (f.functionName === "approve") out.touched.add((f.args[0] as string).toLowerCase());
    } catch { /* not an ERC-20 call */ }
    // any other address-shaped argument word
    for (const w of (d.slice(10).match(/.{64}/g) ?? [])) if (/^0{24}/.test(w) && !/^0{28}/.test(w)) out.touched.add("0x" + w.slice(24).toLowerCase());
  };
  if (op === 1 && MULTISEND.has(to.toLowerCase())) {
    try {
      const packed = decodeFunctionData({ abi: multiAbi, data }).args[0] as Hex;
      const b = packed.slice(2);
      for (let i = 0; i + 170 <= b.length;) {
        const o = parseInt(b.slice(i, i + 2), 16);
        const t = "0x" + b.slice(i + 2, i + 42);
        const v = BigInt("0x" + b.slice(i + 42, i + 106));
        const len = Number(BigInt("0x" + b.slice(i + 106, i + 170)));
        const d = ("0x" + b.slice(i + 170, i + 170 + len * 2)) as Hex;
        push(t, v, d, o);
        i += 170 + len * 2;
      }
      return out;
    } catch { /* fall through: treat as one call */ }
  }
  push(to, value, data, op);
  return out;
}

/** Addresses a proposal names, lowercase. A mixed-case address must carry a valid EIP-55 checksum. */
export function namedAddresses(body: string): { addresses: Set<string>; badChecksum: string[] } {
  const addresses = new Set<string>();
  const badChecksum: string[] = [];
  for (const m of body.match(ADDR_RE) ?? []) {
    const hex = m.slice(2);
    const mixed = hex !== hex.toLowerCase() && hex !== hex.toUpperCase();
    if (mixed) {
      let ok = false;
      try { ok = getAddress(m) === m; } catch { ok = false; }
      if (!ok) { badChecksum.push(m); continue; }
    }
    addresses.add("0x" + hex.toLowerCase());
  }
  return { addresses, badChecksum };
}

/** ENS names a proposal mentions, ENSIP-15 normalized (names that do not normalize are dropped). */
export function ensNames(body: string): string[] {
  const out = new Set<string>();
  for (const m of body.match(ENS_RE) ?? []) {
    try { out.add(normalize(m)); } catch { /* not a valid name */ }
  }
  return [...out];
}

export interface Amount { symbol: string; units: bigint; scale: number }   // value = units / 10^scale
/** Amounts stated with a symbol: "50,000 USDC", "1.5 ETH", "12k DAI", "2.5M OP". */
export function statedAmounts(body: string): Amount[] {
  const out: Amount[] = [];
  for (const m of body.matchAll(AMOUNT_RE)) {
    const [, int, frac = "", mult = "", sym] = m;
    let digits = int.replace(/,/g, "") + frac.slice(1);
    let scale = frac.length ? frac.length - 1 : 0;
    const k = mult.toLowerCase() === "k" ? 3 : mult.toLowerCase() === "m" ? 6 : 0;
    if (k) { const drop = Math.min(k, scale); scale -= drop; digits += "0".repeat(k - drop); }
    out.push({ symbol: sym.toUpperCase().replace(/\.$/, ""), units: BigInt(digits), scale });
  }
  return out;
}

/** Whether a stated amount equals a raw token amount, to the precision it was stated in. */
export function sameAmount(a: Amount, raw: bigint, decimals: number): boolean {
  if (a.scale > decimals) {
    const f = 10n ** BigInt(a.scale - decimals);
    return a.units === raw * f;
  }
  const unit = 10n ** BigInt(decimals - a.scale);    // one step of the stated precision, in raw units
  const expected = a.units * unit;
  const diff = raw > expected ? raw - expected : expected - raw;
  return diff * 2n <= unit;
}

export function passed(p: Proposal): boolean {
  if (p.scores_state !== "final" || p.scores.length === 0 || p.scores.length !== p.choices.length) return false;
  const best = p.scores.indexOf(Math.max(...p.scores));
  const label = (p.choices[best] ?? "").toLowerCase().replace(/^[^a-z]+/, "");
  return /^(for|yes|yae|yay|aye|approve|accept|in favou?r|support|agree|pass|execute|enable|fund|adopt|ratify|confirm)\b/.test(label);
}

export interface Sources {
  /** one page of closed proposals of `space` that ended before `before`, newest first */
  page(space: string, before: number, skip: number, first: number): Promise<Proposal[]>;
  resolveEns(name: string): Promise<string | null>;
  token(address: string): Promise<{ symbol: string; decimals: number } | null>;
  native: string;
}

export type Discovery =
  | { cid: string; why: string; read: number; pages: number }
  | { error: string; read: number; pages: number; passed: number };

export async function discover(src: Sources, space: string, before: number, ex: Decoded, maxPages = MAX_PAGES): Promise<Discovery> {
  const rows: Proposal[] = [];
  let pages = 0;
  for (; pages < maxPages;) {
    const got = await src.page(space, before, pages * PAGE, PAGE);
    pages++;
    rows.push(...got);
    if (got.length < PAGE) break;
  }
  const ok = rows.filter(passed);
  const read = rows.length;
  if (ok.length === 0) return { error: `no passed proposal of the space ended before it (${read} closed proposals read)`, read, pages, passed: 0 };
  // what the execution moves, in each token's units
  const moved: { symbol: string; raw: bigint; decimals: number }[] = [];
  for (const t of ex.transfers) {
    const meta = t.token === "" ? { symbol: src.native, decimals: 18 } : await src.token(t.token).catch(() => null);
    if (meta) moved.push({ symbol: meta.symbol.toUpperCase(), raw: t.amount, decimals: meta.decimals });
  }
  const ensCache = new Map<string, string | null>();
  const naming: { p: Proposal; amount: boolean; via: string }[] = [];
  const bad = new Set<string>();
  for (const p of ok) {
    const text = (p.title ?? "") + "\n" + p.body;
    const { addresses, badChecksum } = namedAddresses(text);
    badChecksum.forEach((b) => bad.add(b));
    let via = [...addresses].find((a) => ex.touched.has(a)) ?? "";
    if (!via) {
      for (const n of ensNames(text).slice(0, MAX_ENS)) {
        if (!ensCache.has(n)) ensCache.set(n, (await src.resolveEns(n).catch(() => null))?.toLowerCase() ?? null);
        const a = ensCache.get(n);
        if (a && ex.touched.has(a)) { via = n; break; }
      }
    }
    if (!via) continue;
    const amount = statedAmounts(text).some((s) => moved.some((m) => m.symbol === s.symbol && sameAmount(s, m.raw, m.decimals)));
    naming.push({ p, amount, via });
  }
  if (naming.length === 0) {
    return { error: `no passed proposal names an address this execution touches (${ok.length} passed of ${read} read${bad.size ? `; ignored ${bad.size} address(es) with a bad checksum` : ""}); not filed`, read, pages, passed: ok.length };
  }
  const best = naming.find((n) => n.amount) ?? naming[0];
  return { cid: best.p.ipfs, read, pages,
    why: `${best === naming[0] ? "most recent " : ""}passed proposal naming ${best.via.startsWith("0x") ? "an address" : `the ENS name ${best.via}`} the execution touches${best.amount ? " and stating an amount it moves" : ""}` };
}
