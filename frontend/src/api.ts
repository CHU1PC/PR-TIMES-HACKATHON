import type { z } from "zod";

import {
  calendarEventSchema,
  calendarEventsSchema,
  calendarStatusSchema,
  hearingResponseSchema,
  proposalResponseSchema,
  sparringResponseSchema,
} from "@/lib/schemas";
import type {
  CalendarEvent,
  CalendarEvents,
  CalendarRange,
  CalendarStatus,
  DemoLogin,
  EventCreate,
  HearingResponse,
  HearingTurn,
  PlanDraft,
  ProposalRequest,
  ProposalResponse,
  SparringForm,
  SparringResponse,
  SparringTurn,
} from "@/types";

// 開発時は Vite の /api プロキシを使い、ブラウザから別オリジンへ直接アクセスしない。
const rawBase: string = import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE ?? "");

// dev は .env.local の http://localhost:8080 を指す。本番は空 = 同一オリジン
const API_BASE = rawBase.replace(/\/+$/, "");

// 壁打ちもヒアリングも毎ターン LLM を呼ぶので長めに取る
const TIMEOUT_MS = 30_000;

// 提案は 業種分類 + 埋め込み + 事例8件(各1000字)を読ませる生成 の3段なので, さらに長い
const PROPOSAL_TIMEOUT_MS = 60_000;

const UNAUTHORIZED = 401;

// dev は 5173 と 8000 が別オリジンなので, 指定しないとセッション Cookie が飛ばない
const WITH_SESSION: RequestInit = { credentials: "include" };

const MESSAGES = {
  timeout: "時間がかかっています。もう一度お試しください。",
  network: "サーバーにつながりませんでした。もう一度お試しください。",
  server: "サーバーが応答しませんでした。もう一度お試しください。",
  malformed: "サーバーの応答を読み取れませんでした。",
  unauthorized: "ログインが必要です。ホームの「デモで入る」から名前だけで始められます。",
  cancelled: "",
} as const satisfies Record<ApiFailureKind, string>;

export type ApiFailureKind = "timeout" | "network" | "server" | "malformed" | "unauthorized" | "cancelled";

export interface ApiFailure {
  kind: ApiFailureKind;
  message: string;
}

export type ApiResult<T> = { ok: true; data: T } | ({ ok: false } & ApiFailure);

function failureOf(error: unknown): ApiFailure {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "TimeoutError") return { kind: "timeout", message: MESSAGES.timeout };
  if (name === "AbortError") return { kind: "cancelled", message: MESSAGES.cancelled };
  // JSON として読めない = 繋がってはいるが別物が返っている(proxy 未設定で index.html が返る等)
  if (error instanceof SyntaxError) return { kind: "malformed", message: MESSAGES.malformed };
  return { kind: "network", message: MESSAGES.network };
}

type Sent = { ok: true; response: Response } | ({ ok: false } & ApiFailure);

async function send(path: string, init: RequestInit, signal: AbortSignal | undefined, timeoutMs: number): Promise<Sent> {
  // 呼び出し側の中断とタイムアウトの両方で切る
  const timeout = AbortSignal.timeout(timeoutMs);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal: combined });
    // 401 は呼び出し側が「未連携」に倒したいので, サーバー障害と分けて返す
    if (response.status === UNAUTHORIZED) {
      return { ok: false, kind: "unauthorized", message: MESSAGES.unauthorized };
    }
    if (!response.ok) return { ok: false, kind: "server", message: MESSAGES.server };
    return { ok: true, response };
  } catch (error) {
    return { ok: false, ...failureOf(error) };
  }
}

async function request<T>(
  path: string,
  init: RequestInit,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
  timeoutMs: number = TIMEOUT_MS,
): Promise<ApiResult<T>> {
  const sent = await send(path, init, signal, timeoutMs);
  if (!sent.ok) return sent;
  try {
    const payload: unknown = await sent.response.json();
    const parsed = schema.safeParse(payload);
    if (!parsed.success) return { ok: false, kind: "malformed", message: MESSAGES.malformed };
    return { ok: true, data: parsed.data };
  } catch (error) {
    return { ok: false, ...failureOf(error) };
  }
}

function post<T>(
  path: string,
  body: unknown,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
  timeoutMs: number = TIMEOUT_MS,
): Promise<ApiResult<T>> {
  const init: RequestInit = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  return request(path, init, schema, signal, timeoutMs);
}

export function sparringStep(turn: SparringTurn, signal?: AbortSignal): Promise<ApiResult<SparringResponse>> {
  return post<SparringResponse>("/api/sparring/step", turn, sparringResponseSchema, signal);
}

/** 6項目をまとめて反映する。粗くて読み取れなかった項目だけ question が返る */
export function sparringFill(form: SparringForm, signal?: AbortSignal): Promise<ApiResult<SparringResponse>> {
  return post<SparringResponse>("/api/sparring/fill", form, sparringResponseSchema, signal);
}

export function hearingStep(turn: HearingTurn, signal?: AbortSignal): Promise<ApiResult<HearingResponse>> {
  return post<HearingResponse>("/api/hearing/step", turn, hearingResponseSchema, signal);
}

export function fetchProposal(request: ProposalRequest, signal?: AbortSignal): Promise<ApiResult<ProposalResponse>> {
  return post<ProposalResponse>("/api/proposal", request, proposalResponseSchema, signal, PROPOSAL_TIMEOUT_MS);
}

/** 未ログインでも 401 にならない。連携ボタンを出すかの判断に使う */
export function calendarStatus(signal?: AbortSignal): Promise<ApiResult<CalendarStatus>> {
  const init: RequestInit = { ...WITH_SESSION, method: "GET" };
  return request("/api/calendar/status", init, calendarStatusSchema, signal);
}

/** 本人の予定だけを返す。未ログインとセッション切れは 401 */
export function calendarEvents(range: CalendarRange, signal?: AbortSignal): Promise<ApiResult<CalendarEvents>> {
  const init: RequestInit = {
    ...WITH_SESSION,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(range),
  };
  return request("/api/calendar/events", init, calendarEventsSchema, signal);
}

/** 連携はブラウザごと Google へ送るので, fetch せず遷移先だけ返す */
export function calendarLoginUrl(): string {
  return `${API_BASE}/api/calendar/login`;
}

/** このアプリに予定を1件足す。Google 側には書き込まない */
export function createPlan(plan: EventCreate, signal?: AbortSignal): Promise<ApiResult<CalendarEvent>> {
  const init: RequestInit = {
    ...WITH_SESSION,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(plan),
  };
  return request("/api/calendar/plans", init, calendarEventSchema, signal);
}

/** 壁打ちで埋めた内容をその予定に残す。本人の予定に無ければ 404 */
export function saveDraft(eventId: string, draft: PlanDraft, signal?: AbortSignal): Promise<ApiResult<CalendarEvent>> {
  const init: RequestInit = {
    ...WITH_SESSION,
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  };
  return request(`/api/calendar/plans/${encodeURIComponent(eventId)}/draft`, init, calendarEventSchema, signal);
}

/** 名前だけでログインする。初めての名前ならサーバーがデモの予定を積む。204 なので本文は読まない */
export async function demoLogin(name: string, signal?: AbortSignal): Promise<ApiResult<null>> {
  const body: DemoLogin = { name: name.trim() || null };
  const init: RequestInit = {
    ...WITH_SESSION,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  const sent = await send("/api/calendar/demo-login", init, signal, TIMEOUT_MS);
  if (!sent.ok) return sent;
  return { ok: true, data: null };
}

/** セッションだけ切る。Google の資格情報は残るので, 入り直せばまた連携済みになる */
export async function logout(signal?: AbortSignal): Promise<ApiResult<null>> {
  const init: RequestInit = { ...WITH_SESSION, method: "POST" };
  const sent = await send("/api/calendar/logout", init, signal, TIMEOUT_MS);
  if (!sent.ok) return sent;
  return { ok: true, data: null };
}

/** 資格情報を消して Google 側にも取り消しを伝える。204 なので本文は読まない */
export async function calendarDisconnect(signal?: AbortSignal): Promise<ApiResult<null>> {
  const init: RequestInit = { ...WITH_SESSION, method: "DELETE" };
  const sent = await send("/api/calendar/connection", init, signal, TIMEOUT_MS);
  if (!sent.ok) return sent;
  return { ok: true, data: null };
}
