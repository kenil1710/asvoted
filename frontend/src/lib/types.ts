export type Verdict = "AS_VOTED" | "DEVIATES" | "UNCLEAR";
export type ActionOutcome = "AUTHORIZED" | "NOT_AUTHORIZED" | "OVER_AMOUNT" | "UNCLEAR";
export type CheckStatus = "PROVISIONAL" | "CONTESTABLE" | "APPEALED" | "FINAL";

export interface Action {
  i: number;
  path: string;
  op: "CALL" | "DELEGATECALL";
  target: string;
  value: string;
  selector: string;
  fn: string;
  kind: string;
  token: string;
  from: string;
  recipient: string;
  amount: string;
  data_len: number;
  batch: string;
  flags: string[];
  args: string[];
  addr_args: string[];
}

export interface Execution {
  found: boolean;
  exec_id: number;
  chain: string;
  safe: string;
  tx: string;
  nonce: number;
  safe_tx_hash: string;
  executor: string;
  block: number;
  block_hash: string;
  block_time: number;
  pinned_block: number;
  pinned_hash: string;
  pinned_time: number;
  read_at: number;
  n_actions: number;
  has_delegatecall: boolean;
  actions: Action[];
  tokens: Record<string, { symbol: string; decimals: number }>;
  symbols: Record<string, string>;
  outer: Record<string, string | number>;
  rpcs: string[];
  evidence_sha256: string;
}

export interface Proposal {
  found: boolean;
  vote_id: number;
  cid: string;
  proposal_id: string;
  space: string;
  author: string;
  title: string;
  text?: string;
  body_sha256: string;
  type: string;
  choices: string[];
  scores: string[];
  scores_total: string;
  quorum: string;
  start: number;
  end: number;
  snapshot: number;
  outcome: "PASSED" | "FAILED" | "UNCLEAR";
  outcome_why: string;
  chain: string;
  safe: string;
  listed: boolean;
  treasuries: [string, string][];
  controllers: string[];
  ens: Record<string, string>;
  ens_blocks: number[];
  pinned_block: number;
  read_at: number;
  evidence_sha256: string;
}

export interface RuledAction {
  i: number;
  outcome: ActionOutcome;
  basis: "code" | "model";
  reason: string;
  quote: string;
  over_bps: number;
  level: string;
}

export interface RulingDetail {
  actions: RuledAction[];
  counts: Record<string, number>;
  judged_at: number;
  judged_by: string;
  input_sha256: string;
  severity: [string, number, string];
}

export interface Check {
  found?: boolean;
  check_id: number;
  dao_id: number;
  chain: string;
  safe: string;
  tx: string;
  block: number;
  exec_time: number;
  exec_id: number;
  vote_id: number;
  cid: string;
  exec_sha: string;
  vote_sha: string;
  filer: string;
  stake: string;
  note: string;
  filed_at: number;
  status: CheckStatus;
  round: number;
  judge_deadline: number;
  ruling: Verdict | "";
  ruling_summary: string;
  ruled_at: number;
  contest_deadline: number;
  appellant: string;
  appeal_bond: string;
  appeal_text: string;
  appeal_vote_id: number;
  appeal_cid: string;
  appeal_deadline: number;
  appeal_ruling: Verdict | "";
  appeal_summary: string;
  final_verdict: Verdict | "";
  final_how: string;
  final_at: number;
  severity: string;
  severity_bps: number;
  pledge_at_filing: string;
  slash: string;
  bounty_to: string;
  settlement: [string, string, string][];
  ruling_detail?: RulingDetail | null;
  appeal_detail?: RulingDetail | null;
}

export interface Dao {
  found?: boolean;
  dao_id: number;
  space: string;
  chain: string;
  safe: string;
  listed_at: number;
  bind_id: number;
  lister: string;
  controller: string;
  pledge: string;
  withdraw_amount: string;
  withdraw_at: number;
  withdraw_requested: number;
  open_checks: number;
  n_checks: number;
  as_voted: number;
  deviates: number;
  unclear: number;
  last_deviates_at: number;
  last_deviates_check: number;
  slashed_total: string;
}

export interface Stats {
  daos: number;
  checks: number;
  [k: string]: number | string;
}

export interface Ledger {
  received: string;
  pledges: string;
  open: string;
  claimable: string;
  claimed: string;
  held_now: string;
  invariant_holds: boolean;
  views_match_storage: boolean | null;
  on_chain_balance: string;
  balance_minus_held: string;
  note: string;
}

export interface RegistryConfig {
  version: string;
  mode: "CANONICAL" | "DEMO";
  exec_reader: string;
  vote_reader: string;
  judge: string;
  demo_controllers: string[];
  contest_s: number;
  judge_deadline_s: number;
  appeal_deadline_s: number;
  withdraw_delay_s: number;
  binding_max_age_s: number;
  check_stake: string;
  appeal_bond: string;
  min_pledge: string;
  severity_table: [string, number, string][];
}

export type TxPhase = "signing" | "submitted" | "accepted" | "finalized" | "failed" | "rejected";
export interface TxProgress {
  phase: TxPhase;
  hash: string | null;
  message: string;
}
export type WriteResult<T> =
  | { kind: "ok"; hash: string; data: T }
  | { kind: "rejected"; hash: string; reason: string }
  | { kind: "failed"; hash: string | null; error: string };
