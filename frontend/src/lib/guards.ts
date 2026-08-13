import type {
  Candidate,
  Exchange,
  HearingResponse,
  PlanDraft,
  ProposalCase,
  ProposalResponse,
  SlotCode,
  SlotState,
  SparringResponse,
  Suggestion,
} from "@/types";

const SLOT_CODES = new Set<string>(["place", "partner", "people", "novelty", "observation", "video"]);
const PRESENCES = new Set<string>(["yes", "no", "unknown"]);
const YES_NO = new Set<string>(["yes", "no"]);
const TONES = new Set<string>(["causal", "functional"]);

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function isTextOrNull(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isEnumOrNull(value: unknown, allowed: Set<string>): boolean {
  return value === null || (typeof value === "string" && allowed.has(value));
}

function isTextArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isSlotCodeArray(value: unknown): value is SlotCode[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string" && SLOT_CODES.has(item));
}

export function isPlanDraft(value: unknown): value is PlanDraft {
  if (!isRecord(value)) return false;
  return (
    typeof value.title === "string" &&
    isTextOrNull(value.start_date) &&
    isTextOrNull(value.place) &&
    isTextArray(value.partner) &&
    isEnumOrNull(value.people, PRESENCES) &&
    isTextOrNull(value.novelty) &&
    isTextOrNull(value.observation) &&
    isEnumOrNull(value.video, YES_NO) &&
    isSlotCodeArray(value.skipped) &&
    isSlotCodeArray(value.retried)
  );
}

export function isSlotState(value: unknown): value is SlotState {
  if (!isRecord(value)) return false;
  return (
    typeof value.code === "string" &&
    SLOT_CODES.has(value.code) &&
    typeof value.label === "string" &&
    typeof value.filled === "boolean" &&
    typeof value.skipped === "boolean" &&
    typeof value.effect === "string" &&
    typeof value.tone === "string" &&
    TONES.has(value.tone)
  );
}

export function isExchange(value: unknown): value is Exchange {
  if (!isRecord(value)) return false;
  return typeof value.question === "string" && typeof value.answer === "string";
}

export function isCandidate(value: unknown): value is Candidate {
  if (!isRecord(value)) return false;
  return (
    typeof value.title === "string" &&
    typeof value.category === "string" &&
    typeof value.source === "string" &&
    typeof value.reason === "string"
  );
}

/** サーバー応答を信用しない。壊れた値を localStorage に書いてから落ちるのを防ぐ。 */
export function isSparringResponse(value: unknown): value is SparringResponse {
  if (!isRecord(value)) return false;
  return (
    isPlanDraft(value.draft) &&
    isTextOrNull(value.question) &&
    isTextOrNull(value.hint) &&
    Array.isArray(value.slots) &&
    value.slots.every(isSlotState) &&
    typeof value.ready === "boolean"
  );
}

export function isProposalCase(value: unknown): value is ProposalCase {
  if (!isRecord(value)) return false;
  return (
    typeof value.company_id === "number" &&
    typeof value.release_id === "number" &&
    typeof value.title === "string" &&
    typeof value.subtitle === "string" &&
    typeof value.body_head === "string" &&
    isTextOrNull(value.company_name) &&
    isTextOrNull(value.business_category) &&
    isTextOrNull(value.release_type) &&
    isTextOrNull(value.prefecture) &&
    isTextOrNull(value.city) &&
    typeof value.published_on === "string" &&
    isTextArray(value.media)
  );
}

export function isSuggestion(value: unknown): value is Suggestion {
  if (!isRecord(value)) return false;
  return (
    typeof value.action === "string" &&
    typeof value.reason === "string" &&
    Array.isArray(value.cited) &&
    value.cited.every((item) => typeof item === "number")
  );
}

/** 同上。提案側。cited が cases の範囲に収まっているかまで見る。 */
export function isProposalResponse(value: unknown): value is ProposalResponse {
  if (!isRecord(value)) return false;
  if (!Array.isArray(value.cases) || !value.cases.every(isProposalCase)) return false;
  if (!Array.isArray(value.suggestions) || !value.suggestions.every(isSuggestion)) return false;
  if (!isTextArray(value.media)) return false;
  // 範囲外の添字が来ると cases[i] が undefined になり, 描画時に落ちる
  const total = value.cases.length;
  return value.suggestions.every((s) => s.cited.every((i) => Number.isInteger(i) && i >= 0 && i < total));
}

/** 同上。ヒアリング側。 */
export function isHearingResponse(value: unknown): value is HearingResponse {
  if (!isRecord(value)) return false;
  return (
    Array.isArray(value.history) &&
    value.history.every(isExchange) &&
    isTextOrNull(value.question) &&
    isTextOrNull(value.hint) &&
    Array.isArray(value.candidates) &&
    value.candidates.every(isCandidate) &&
    typeof value.done === "boolean"
  );
}
