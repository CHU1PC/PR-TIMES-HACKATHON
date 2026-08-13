import { isHearingResponse, isProposalResponse, isSparringResponse } from "@/lib/guards";
import type {
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

async function post<T>(
  path: string,
  body: unknown,
  guard: (value: unknown) => value is T,
  signal?: AbortSignal,
  timeoutMs: number = TIMEOUT_MS,
): Promise<ApiResult<T>> {
  // 呼び出し側の中断とタイムアウトの両方で切る
  const timeout = AbortSignal.timeout(timeoutMs);
  const combined = signal ? AbortSignal.any([signal, timeout]) : timeout;
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: combined,
    });
    if (!response.ok) return { ok: false, kind: "server", message: MESSAGES.server };
    const payload: unknown = await response.json();
    if (!guard(payload)) return { ok: false, kind: "malformed", message: MESSAGES.malformed };
    return { ok: true, data: payload };
  } catch (error) {
    return { ok: false, ...failureOf(error) };
  }
}

export function sparringStep(turn: SparringTurn, signal?: AbortSignal): Promise<ApiResult<SparringResponse>> {
  return post<SparringResponse>("/api/sparring/step", turn, isSparringResponse, signal);
}

export function hearingStep(turn: HearingTurn, signal?: AbortSignal): Promise<ApiResult<HearingResponse>> {
  return post<HearingResponse>("/api/hearing/step", turn, isHearingResponse, signal);
}

export function fetchProposal(request: ProposalRequest, signal?: AbortSignal): Promise<ApiResult<ProposalResponse>> {
  return post<ProposalResponse>("/api/proposal", request, isProposalResponse, signal, PROPOSAL_TIMEOUT_MS);
}
