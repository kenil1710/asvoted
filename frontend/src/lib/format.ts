/**
 * Formatting helpers. Every amount arrives as a WEI STRING and is formatted by
 * integer arithmetic on that string — never by Number(wei)/1e18, which loses
 * precision above 2^53 and would show a bond of 1.0000000000000002 GEN.
 */

export function formatGen(wei: string | bigint | undefined, places = 4): string {
  if (wei === undefined || wei === null) return "0";
  let v: bigint;
  try {
    v = typeof wei === "bigint" ? wei : BigInt(String(wei).trim() || "0");
  } catch {
    return "0";
  }
  if (v < 0n) v = -v;
  const whole = v / 10n ** 18n;
  const frac = v % 10n ** 18n;
  if (frac === 0n) return whole.toString();
  const tail = frac.toString().padStart(18, "0").slice(0, places).replace(/0+$/, "");
  return tail ? `${whole}.${tail}` : whole.toString();
}

/**
 * "1.25" → 1250000000000000000n. `null` for anything that is not a plain
 * decimal amount, which the caller renders as a problem rather than sending.
 *
 * Deliberately string arithmetic, for the same reason `formatGen` is: a
 * top-up typed as 1.1 goes through `Number` as 1.1000000000000000888, and a
 * bond is not a place to lose the last three wei.
 */
export function parseGen(text: string): bigint | null {
  const t = String(text).trim();
  if (!/^\d+(\.\d{1,18})?$/.test(t)) return null;
  const [whole, frac = ""] = t.split(".");
  return BigInt(whole) * 10n ** 18n + BigInt((frac + "0".repeat(18)).slice(0, 18));
}

export function shortAddress(value: string | undefined, size = 4): string {
  if (!value) return "";
  const s = String(value);
  if (s.length <= size * 2 + 3) return s;
  return `${s.slice(0, size + 2)}…${s.slice(-size)}`;
}

export function percentFromBps(bps: number | undefined): number {
  if (typeof bps !== "number" || Number.isNaN(bps)) return 0;
  return Math.round(bps / 100);
}

/** Epoch seconds → "3 minutes ago". Returns "never" for 0. */
export function relativeTime(epochSeconds: number | undefined): string {
  if (!epochSeconds) return "never";
  const delta = Math.floor(Date.now() / 1000) - epochSeconds;
  if (delta < 0) return "just now";
  const units: [number, string][] = [
    [31536000, "year"], [2592000, "month"], [86400, "day"],
    [3600, "hour"], [60, "minute"],
  ];
  for (const [secs, name] of units) {
    if (delta >= secs) {
      const n = Math.floor(delta / secs);
      return `${n} ${name}${n === 1 ? "" : "s"} ago`;
    }
  }
  return delta <= 5 ? "just now" : `${delta} seconds ago`;
}

export function absoluteTime(epochSeconds: number | undefined): string {
  if (!epochSeconds) return "—";
  return new Date(epochSeconds * 1000).toLocaleString(undefined, {
    dateStyle: "medium", timeStyle: "short",
  });
}

export function durationText(seconds: number): string {
  if (seconds <= 0) return "now";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

export const CHAIN_LABEL: Record<string, string> = {
  ethereum: "Ethereum", arbitrum: "Arbitrum", optimism: "Optimism", base: "Base", polygon: "Polygon",
};

export const EXPLORER_HOST: Record<string, string> = {
  ethereum: "etherscan.io", arbitrum: "arbiscan.io", optimism: "optimistic.etherscan.io",
  base: "basescan.org", polygon: "polygonscan.com",
};

/** A block explorer link on one of the five chains. */
export function chainUrl(chain: string, kind: "address" | "tx" | "block", value: string | number): string {
  const host = EXPLORER_HOST[chain] ?? EXPLORER_HOST.ethereum;
  return `https://${host}/${kind}/${value}`;
}

/** A raw token amount as a decimal string with separators (integer arithmetic). */
export function formatUnits(raw: string, decimals: number, places = 4): string {
  if (decimals < 0) return raw;
  let v: bigint;
  try { v = BigInt(raw || "0"); } catch { return raw; }
  const base = 10n ** BigInt(decimals);
  const whole = (v / base).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const frac = (v % base).toString().padStart(decimals, "0").slice(0, places).replace(/0+$/, "");
  return frac ? `${whole}.${frac}` : whole;
}

export function isoDate(epoch: number): string {
  if (!epoch) return "";
  return new Date(epoch * 1000).toISOString().slice(0, 10);
}

export function ipfsUrl(cid: string): string {
  return `https://ipfs.snapshot.box/ipfs/${cid}`;
}

export function isTxHash(value: string): boolean {
  return /^0x[0-9a-fA-F]{64}$/.test(String(value).trim());
}

export function isAddress(value: string): boolean {
  return /^0x[0-9a-fA-F]{40}$/.test(String(value).trim());
}
