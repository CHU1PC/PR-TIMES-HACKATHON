import type { Candidate, Exchange, PlanDraft, SlotCode, SlotState } from "@/types";

export interface ChatMessage {
  /** ai はサーバーの質問、you は顧客の返答 */
  role: "ai" | "you";
  /** 画面に出す文言 */
  text: string;
}

export interface SparringSession {
  /** 入口で入力された予定。復元先を取り違えないための鍵にもする */
  title: string;
  /** サーバーに送り返す現在のイベント内容 */
  draft: PlanDraft;
  /** 画面に出す会話の記録。サーバーは保持しない */
  messages: ChatMessage[];
  /** チェックリスト */
  slots: SlotState[];
  /** いま出ている質問 */
  question: string | null;
  /** いま出ている例示 */
  hint: string | null;
  /** 出せる形になったか */
  ready: boolean;
}

export interface HearingSession {
  /** サーバーに送り返す往復履歴 */
  history: Exchange[];
  /** いま出ている質問 */
  question: string | null;
  /** いま出ている例示 */
  hint: string | null;
  /** 見つかった予定候補 */
  candidates: Candidate[];
  /** 聞き終わったか */
  done: boolean;
}

const SPARRING_KEY = "prtimes.sparring";
const HEARING_KEY = "prtimes.hearing";

const SLOT_CODES = new Set<string>(["place", "partner", "people", "novelty", "observation", "video"]);
const PRESENCES = new Set<string>(["yes", "no", "unknown"]);
const YES_NO = new Set<string>(["yes", "no"]);
const TONES = new Set<string>(["causal", "functional"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isTextOrNull(value: unknown): value is string | null {
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

function isPlanDraft(value: unknown): value is PlanDraft {
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

function isSlotState(value: unknown): value is SlotState {
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

function isChatMessage(value: unknown): value is ChatMessage {
  if (!isRecord(value)) return false;
  return (value.role === "ai" || value.role === "you") && typeof value.text === "string";
}

function isExchange(value: unknown): value is Exchange {
  if (!isRecord(value)) return false;
  return typeof value.question === "string" && typeof value.answer === "string";
}

function isCandidate(value: unknown): value is Candidate {
  if (!isRecord(value)) return false;
  return (
    typeof value.title === "string" &&
    typeof value.category === "string" &&
    typeof value.source === "string" &&
    typeof value.reason === "string"
  );
}

function isSparringSession(value: unknown): value is SparringSession {
  if (!isRecord(value)) return false;
  return (
    typeof value.title === "string" &&
    isPlanDraft(value.draft) &&
    Array.isArray(value.messages) &&
    value.messages.every(isChatMessage) &&
    Array.isArray(value.slots) &&
    value.slots.every(isSlotState) &&
    isTextOrNull(value.question) &&
    isTextOrNull(value.hint) &&
    typeof value.ready === "boolean"
  );
}

function isHearingSession(value: unknown): value is HearingSession {
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

function read<T>(key: string, guard: (value: unknown) => value is T): T | null {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    return guard(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // 保存できなくても画面は動く
  }
}

function remove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // 消せなくても画面は動く
  }
}

export function loadSparring(): SparringSession | null {
  return read(SPARRING_KEY, isSparringSession);
}

export function saveSparring(session: SparringSession): void {
  write(SPARRING_KEY, session);
}

export function clearSparring(): void {
  remove(SPARRING_KEY);
}

export function loadHearing(): HearingSession | null {
  return read(HEARING_KEY, isHearingSession);
}

export function saveHearing(session: HearingSession): void {
  write(HEARING_KEY, session);
}

export function clearHearing(): void {
  remove(HEARING_KEY);
}
