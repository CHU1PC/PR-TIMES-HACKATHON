import type {
  Candidate,
  Exchange,
  HearingResponse,
  PlanDraft,
  SlotCode,
  SlotState,
  SparringResponse,
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
