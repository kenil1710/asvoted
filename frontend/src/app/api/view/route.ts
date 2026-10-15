/**
 * GET /api/view?a=<contract>&f=<view method>&args=<json array>
 *
 * One contract view, read server-side from Studio Dev and cached by Vercel's
 * CDN for 20 s (stale up to 2 min while it refreshes). Studio meters requests
 * per IP and every visitor of the site shares this deployment's IP, so the
 * same `get_stats` asked by a hundred browsers is one read, not a hundred.
 * Only view methods of the AsVoted contracts are served; writes never come here.
 */
import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { ADDR } from "@/lib/deployments";

export const dynamic = "force-dynamic";

const ALLOWED = new Set(Object.values(ADDR).map((a) => a.toLowerCase()));
const client = createClient({ chain: studioDevnet });

function plain(v: unknown): unknown {
  if (v instanceof Map) return Object.fromEntries([...v.entries()].map(([k, x]) => [String(k), plain(x)]));
  if (Array.isArray(v)) return v.map(plain);
  if (typeof v === "bigint") return Number(v) <= Number.MAX_SAFE_INTEGER ? Number(v) : v.toString();
  return v;
}

export async function GET(req: Request) {
  const u = new URL(req.url);
  const a = u.searchParams.get("a") ?? "";
  const f = u.searchParams.get("f") ?? "";
  let args: unknown[] = [];
  try { args = JSON.parse(u.searchParams.get("args") ?? "[]"); } catch { return Response.json({ error: "bad args" }, { status: 400 }); }
  if (!ALLOWED.has(a.toLowerCase()) || !/^(get_|claimable_of$|standing$|is_)/.test(f) || !Array.isArray(args) || args.length > 4) {
    return Response.json({ error: "not an AsVoted view" }, { status: 400 });
  }
  const addr = Object.values(ADDR).find((x) => x.toLowerCase() === a.toLowerCase())!;
  let last: unknown;
  for (let i = 0; i < 3; i++) {
    try {
      const raw = await client.readContract({ address: addr as `0x${string}`, functionName: f, args: args as never });
      const value = typeof raw === "string" ? raw : plain(raw);
      const fresh = u.searchParams.has("fresh");
      return Response.json({ value }, { headers: { "cache-control": fresh ? "no-store" : "public, s-maxage=20, stale-while-revalidate=120" } });
    } catch (e) {
      last = e;
      await new Promise((r) => setTimeout(r, 800 * (i + 1)));
    }
  }
  return Response.json({ error: String((last as Error)?.message ?? last).slice(0, 300) }, { status: 502, headers: { "cache-control": "no-store" } });
}
