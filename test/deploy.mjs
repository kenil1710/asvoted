/**
 * Deploys every AsVoted contract to Studio Dev FROM HEAD.
 *
 *   node deploy.mjs [--set=final|smoke] [--reason="..."]
 *
 * The bytes sent are `git show HEAD:contracts/<File>.py`, never the working
 * tree, and the script refuses to run if contracts/ has uncommitted changes -
 * so what is on chain is byte-identical to the pushed commit. Order:
 *
 *   ExecReader, VoteReader, AsVotedJudge                  (shared by both registries)
 *   AsVotedRegistry  CANONICAL  (6 h contest window, no demo seam)
 *   AsVotedRegistry  DEMO       (90 s contest window, demo controller = the `dao` test account)
 *   DaoStanding x2 (30-day window, the patrol as monitor, 6 h staleness), GrantGate x2
 *
 * --set=smoke writes to deployments.smoke.json instead (throwaway checks).
 * --only=demo --commit=<sha> redeploys only the demo registry, standing and
 * gate, from the bytes at <sha> (refused unless contracts/ is unchanged since
 * <sha>), so every deployment still comes from that one commit.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { createClient, createAccount } from "genlayer-js";
import { CHAINS, accounts, fundOnStudio, deploy, argOf } from "./harness.mjs";

const root = new URL("..", import.meta.url).pathname;
const git = (...a) => execFileSync("git", ["-C", root, ...a]).toString();
if (git("status", "--porcelain", "contracts").trim() !== "") {
  console.error("contracts/ has uncommitted changes; commit first"); process.exit(1);
}
const pinned = argOf("commit", null);
const head = pinned ? git("rev-parse", pinned).trim() : git("rev-parse", "HEAD").trim();
if (pinned && git("log", "--format=%H", `${head}..HEAD`, "--", "contracts").trim() !== "") {
  console.error(`contracts/ changed since ${head}; cannot deploy from it`); process.exit(1);
}
const only = argOf("only", null);
const set = argOf("set", "final");
const chain = CHAINS.studiodev;
const acc = accounts();
const account = createAccount(acc.deployer.key);
const wallet = createClient({ chain, account });
const read = createClient({ chain });
await fundOnStudio(chain, account.address, 1000n * 10n ** 18n);
console.log(`deployer ${account.address}  HEAD ${head}  set ${set}`);

const path = new URL(set === "final" ? "../deployments.json" : `../deployments.${set}.json`, import.meta.url);
const doc = existsSync(path) ? JSON.parse(readFileSync(path, "utf8"))
  : { network: "studiodev", chain_id: 61997, rpc: "https://studio-dev.genlayer.com/api", explorer: "https://explorer-studio-dev.genlayer.com/", contracts: {} };
const persist = () => writeFileSync(path, JSON.stringify(doc, null, 2) + "\n");
const sha = (b) => createHash("sha256").update(b).digest("hex");

async function one(name, file, args, extra = {}) {
  const prev = doc.contracts[name];
  const wanted = only !== "demo" || /Demo$/.test(name);
  if (!wanted || (prev?.commit === head && prev?.address && !process.argv.includes("--force"))) {
    console.log(`${name} already deployed from HEAD at ${prev.address}`);
    return prev.address;
  }
  const code = execFileSync("git", ["-C", root, "show", `${head}:contracts/${file}.py`]);
  console.log(`\n${name}  ${file}.py  args=${JSON.stringify(args)}  ${code.length} bytes  sha256 ${sha(code)}`);
  const res = await deploy({ chain, wallet, read, code: code.toString("utf8"), args, label: name });
  if (!res.ok) { console.error(`${name} FAILED`, res.out?.status, res.reason ?? "", res.out?.revertReason ?? "", res.out?.stderr?.slice(-2000) ?? ""); process.exit(1); }
  console.log(`  address ${res.address}`);
  if (prev?.address && prev.address !== res.address) {
    doc.superseded ??= [];
    doc.superseded.push({ name, ...prev, superseded_by: res.address, why: argOf("reason", "redeployed") });
  }
  doc.contracts[name] = { address: res.address, deploy_tx: res.hash, file: `contracts/${file}.py`, commit: head,
    bytes: code.length, sha256: sha(code), constructor_args: args, deployer: account.address,
    deployed_at: new Date().toISOString(), ...extra };
  persist();
  return res.address;
}

const er = await one("ExecReader", "ExecReader", []);
const vr = await one("VoteReader", "VoteReader", []);
// the tokens the judge identifies by symbol, fixed at deployment (symbols read on chain: test/token_list.json)
const tokenList = JSON.stringify(JSON.parse(readFileSync(new URL("./token_list.json", import.meta.url), "utf8")));
const jg = await one("AsVotedJudge", "AsVotedJudge", [tokenList]);
const rc = await one("AsVotedRegistry", "AsVotedRegistry", ["CANONICAL", er, vr, jg, ""], { mode: "CANONICAL" });
const rd = await one("AsVotedRegistryDemo", "AsVotedRegistry", ["DEMO", er, vr, jg, acc.dao.address.toLowerCase()], { mode: "DEMO" });
// DaoStanding counts the patrol's coverage heartbeat, stale after 6 h
const monitor = acc.patrol.address.toLowerCase();
const sc = await one("DaoStanding", "DaoStanding", [rc, 30, monitor, 21600], { mode: "CANONICAL" });
const sd = await one("DaoStandingDemo", "DaoStanding", [rd, 30, monitor, 21600], { mode: "DEMO" });
await one("GrantGate", "GrantGate", [sc], { mode: "CANONICAL" });
await one("GrantGateDemo", "GrantGate", [sd], { mode: "DEMO" });
console.log(`\nwrote ${path.pathname}`);
