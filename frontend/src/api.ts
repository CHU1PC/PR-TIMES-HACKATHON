import type { z } from "zod";

import {
  calendarEventsResponseSchema,
  calendarStatusSchema,
  hearingResponseSchema,
  proposalResponseSchema,
  sparringResponseSchema,
} from "@/lib/schemas";
import type {
  CalendarEventsResponse,
  CalendarRange,
  CalendarStatus,
  HearingResponse,
  HearingTurn,
  ProposalRequest,
  ProposalResponse,
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

const MESSAGES = {
  timeout: "時間がかかっています。もう一度お試しください。",
  network: "サーバーにつながりませんでした。もう一度お試しください。",
  server: "サーバーが応答しませんでした。もう一度お試しください。",
  malformed: "サーバーの応答を読み取れませんでした。",
  cancelled: "",
} as const satisfies Record<ApiFailureKind, string>;

export type ApiFailureKind = "timeout" | "network" | "server" | "malformed" | "cancelled";

export interface ApiFailure {
  kind: ApiFailureKind;
  message: string;
}

export type ApiResult<T> = { ok: true; data: T } | ({ ok: false } & ApiFailure);

function failureOf(error: unknown): ApiFailure {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "TimeoutError") return { kind: "timeout", message: MESSAGES.timeout };
  if (name === "AbortError") return { kind: "cancelled", message: MESSAGES.cancelled };
  // JSON として読めない = 繋がってはいるが別物が返っている（proxy 未設定で index.html が返る等）
  if (error instanceof SyntaxError) return { kind: "malformed", message: MESSAGES.malformed };
  return { kind: "network", message: MESSAGES.network };
}

async function request<T>(
  path: string,
  init: RequestInit,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
  timeoutMs: number = TIMEOUT_MS,
): Promise<ApiResult<T>> {
  // 呼び出し側の中断とタイムアウトの両方で切る
  const timeout = AbortSignal.timeout(timeoutMs);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal: combined });
    if (!response.ok) return { ok: false, kind: "server", message: MESSAGES.server };
    const payload: unknown = await response.json();
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

function get<T>(
  path: string,
  schema: z.ZodType<T>,
  signal?: AbortSignal,
  timeoutMs: number = TIMEOUT_MS,
): Promise<ApiResult<T>> {
  return request(path, { method: "GET" }, schema, signal, timeoutMs);
}

export function sparringStep(turn: SparringTurn, signal?: AbortSignal): Promise<ApiResult<SparringResponse>> {
  return post<SparringResponse>("/api/sparring/step", turn, sparringResponseSchema, signal);
}

export function hearingStep(turn: HearingTurn, signal?: AbortSignal): Promise<ApiResult<HearingResponse>> {
  return post<HearingResponse>("/api/hearing/step", turn, hearingResponseSchema, signal);
}

export function fetchProposal(request: ProposalRequest, signal?: AbortSignal): Promise<ApiResult<ProposalResponse>> {
  return post<ProposalResponse>("/api/proposal", request, proposalResponseSchema, signal, PROPOSAL_TIMEOUT_MS);
}

export function calendarStatus(signal?: AbortSignal): Promise<ApiResult<CalendarStatus>> {
  return get<CalendarStatus>("/api/calendar/status", calendarStatusSchema, signal);
}

export function calendarEvents(
  range: CalendarRange,
  signal?: AbortSignal,
): Promise<ApiResult<CalendarEventsResponse>> {
  return post<CalendarEventsResponse>("/api/calendar/events", range, calendarEventsResponseSchema, signal);
}

/** 連携はブラウザごと Google へ送るので, fetch せず遷移先だけ返す */
export function calendarLoginUrl(): string {
  return `${API_BASE}/api/calendar/login`;
}
