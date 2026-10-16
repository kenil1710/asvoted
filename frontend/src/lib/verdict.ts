import type { Check, Proposal } from "./types";

/** A proposal's short name: the id its title starts with (CIP-16, SEP #22, PIP-59), else its title. */
export function proposalLabel(vote: Proposal | undefined, cid?: string): string {
  const t = vote?.title?.trim() ?? "";
  const m = t.match(/^\[?([A-Z]{2,6}[- #]*\d+[a-z]?)\]?[:\s]/);
  if (m) return m[1];
  if (t) return `“${t.length > 60 ? t.slice(0, 57) + "…" : t}”`;
  return cid ? `${cid.slice(0, 12)}…` : "the named proposal";
}

/**
 * The verdict sentence as the site shows it. The contract's DEVIATES wording is
 * "includes an action the proposal of <date> does not mention"; the site says
 * only what that establishes: the named proposal does not cover the action.
 */
export function verdictSentence(check: Check, vote?: Proposal): string {
  const s = check.appeal_summary || check.ruling_summary;
  if (!s) return "";
  const id = proposalLabel(vote, check.appeal_summary ? check.appeal_cid : check.cid);
  return s
    .replace(/includes an action the proposal of (\S+) does not mention\./, `includes an action proposal ${id} (closed $1) does not cover.`)
    .replace(/sends more than the proposal of (\S+) states\./, `sends more than proposal ${id} (closed $1) states.`);
}

/** The proposal a check's sentence is about: the appeal's when an appeal was ruled. */
export const sentenceVoteId = (c: Check) => (c.appeal_summary && c.appeal_vote_id ? c.appeal_vote_id : c.vote_id);
