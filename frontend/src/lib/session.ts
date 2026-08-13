import { z } from "zod";

import { candidateSchema, exchangeSchema, planDraftSchema, slotStateSchema } from "@/lib/schemas";

export const chatMessageSchema = z.object({
  /** ai はサーバーの質問、you は顧客の返答 */
  role: z.enum(["ai", "you"]),
  /** 画面に出す文言 */
  text: z.string(),
});

export const sparringSessionSchema = z.object({
  /** 入口で入力された予定。復元先を取り違えないための鍵にもする */
  title: z.string(),
  /** サーバーに送り返す現在のイベント内容 */
  draft: planDraftSchema,
  /** 画面に出す会話の記録。サーバーは保持しない */
  messages: z.array(chatMessageSchema),
  /** チェックリスト */
  slots: z.array(slotStateSchema),
  /** いま出ている質問 */
  question: z.string().nullable(),
  /** いま出ている例示 */
  hint: z.string().nullable(),
  /** 出せる形になったか */
  ready: z.boolean(),
});

export const hearingSessionSchema = z.object({
  /** サーバーに送り返す往復履歴 */
  history: z.array(exchangeSchema),
  /** 画面に出す会話の記録。サーバーは保持しない */
  messages: z.array(chatMessageSchema),
  /** いま出ている質問 */
  question: z.string().nullable(),
  /** いま出ている例示 */
  hint: z.string().nullable(),
  /** 見つかった予定候補 */
  candidates: z.array(candidateSchema),
  /** 聞き終わったか */
  done: z.boolean(),
});

export type ChatMessage = z.infer<typeof chatMessageSchema>;

export type SparringSession = z.infer<typeof sparringSessionSchema>;

export type HearingSession = z.infer<typeof hearingSessionSchema>;

const SPARRING_KEY = "prtimes.sparring";
const HEARING_KEY = "prtimes.hearing";

function read<T>(key: string, schema: z.ZodType<T>): T | null {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = schema.safeParse(JSON.parse(raw));
    return parsed.success ? parsed.data : null;
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
  return read(SPARRING_KEY, sparringSessionSchema);
}

export function saveSparring(session: SparringSession): void {
  write(SPARRING_KEY, session);
}

export function clearSparring(): void {
  remove(SPARRING_KEY);
}

export function loadHearing(): HearingSession | null {
  return read(HEARING_KEY, hearingSessionSchema);
}

export function saveHearing(session: HearingSession): void {
  write(HEARING_KEY, session);
}

export function clearHearing(): void {
  remove(HEARING_KEY);
}
