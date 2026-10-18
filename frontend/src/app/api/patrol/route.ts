import { runPatrol } from "@/lib/patrol";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

/**
 * The GitHub Action calls this every 15 minutes with `x-patrol-secret: <PATROL_SECRET>`
 * (an `Authorization: Bearer` header works too) and a JSON body `{ "state": ... }`
 * read from the `patrol-state` branch; the response carries the new state,
 * which the Action commits back. Anything else is a DRY RUN: the same reads
 * and matching, no transaction is sent and no state is returned.
 */
function trusted(req: Request): boolean {
  const secret = (process.env.PATROL_SECRET ?? "").trim();
  if (!secret) return false;
  const h = (req.headers.get("x-patrol-secret") ?? req.headers.get("authorization")?.replace(/^bearer\s+/i, "") ?? "").trim();
  return h.length === secret.length && h === secret;
}

async function handle(req: Request) {
  const live = trusted(req) && new URL(req.url).searchParams.get("dry") !== "1";
  let state: unknown = undefined;
  if (req.method === "POST") {
    try { state = ((await req.json()) as { state?: unknown })?.state; } catch { state = undefined; }
  }
  const { report, state: next } = await runPatrol({ dry: !live, key: live ? process.env.PATROL_KEY : undefined, state });
  console.log(`[patrol] ${JSON.stringify({ dry: report.dry_run, writes: report.writes.length, seen: report.executions_seen, filed: report.filed, queued: report.queued, s: report.seconds })}`);
  return Response.json({ ...report, state: next }, { headers: { "cache-control": "no-store" } });
}

export const GET = handle;
export const POST = handle;
