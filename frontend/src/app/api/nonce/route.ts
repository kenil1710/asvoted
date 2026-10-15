import { findNonce } from "@/lib/safe";

export const dynamic = "force-dynamic";

/** GET /api/nonce?chain=&safe=&tx=  ->  the Safe nonce hint for ExecReader (it re-verifies it). */
export async function GET(req: Request) {
  const u = new URL(req.url);
  const chain = u.searchParams.get("chain") ?? "";
  const safe = u.searchParams.get("safe") ?? "";
  const tx = u.searchParams.get("tx") ?? "";
  if (!/^0x[0-9a-fA-F]{40}$/.test(safe) || !/^0x[0-9a-fA-F]{64}$/.test(tx)) return Response.json({ error: "bad safe or tx" }, { status: 400 });
  try {
    return Response.json(await findNonce(chain, safe, tx));
  } catch (e) {
    return Response.json({ error: String((e as Error).message ?? e).slice(0, 200) }, { status: 502 });
  }
}
