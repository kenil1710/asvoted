import { runPatrol } from "@/lib/patrol";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

/**
 * cron-job.org calls this every 15 minutes with `x-patrol-secret: <PATROL_SECRET>`
 * (an `Authorization: Bearer` header works too). Anything else is a DRY RUN:
 * the same reads and matching, and no transaction is sent.
 */
function trusted(req: Request): boolean {
  const secret = (process.env.PATROL_SECRET ?? "").trim();
  if (!secret) return false;
  const h = (req.headers.get("x-patrol-secret") ?? req.headers.get("authorization")?.replace(/^bearer\s+/i, "") ?? "").trim();
  return h.length === secret.length && h === secret;
}

async function handle(req: Request) {
  const live = trusted(req) && new URL(req.url).searchParams.get("dry") !== "1";
  const report = await runPatrol({ dry: !live, key: live ? process.env.PATROL_KEY : undefined });
  console.log(`[patrol] ${JSON.stringify({ dry: report.dry_run, writes: report.writes.length, seen: report.executions_seen, matched: report.matched.length, s: report.seconds })}`);
  return Response.json(report, { headers: { "cache-control": "no-store" } });
}

export const GET = handle;
export const POST = handle;
