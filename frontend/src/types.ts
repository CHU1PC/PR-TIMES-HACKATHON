import type { z } from "zod";

import type {
  calendarEventSchema,
  calendarEventsSchema,
  calendarStatusSchema,
  candidateSchema,
  demoLoginSchema,
  eventCreateSchema,
  eventQuerySchema,
  exchangeSchema,
  hearingResponseSchema,
  hearingTurnSchema,
  planDraftSchema,
  proposalCaseSchema,
  proposalRequestSchema,
  proposalResponseSchema,
  slotStateSchema,
  sparringFormSchema,
  sparringResponseSchema,
  sparringTurnSchema,
  suggestionSchema,
} from "@/lib/schemas";

export type PlanDraft = z.infer<typeof planDraftSchema>;

export type SlotState = z.infer<typeof slotStateSchema>;

export type SlotCode = SlotState["code"];

/** causal は判定クエリC を通ったスロットのみ */
export type Tone = SlotState["tone"];

/** 当日その場に人がいるか。null は「まだ聞いていない」 */
export type Presence = NonNullable<PlanDraft["people"]>;

/** すでにある動画の有無。null は「まだ聞いていない」 */
export type YesNo = NonNullable<PlanDraft["video"]>;

export type SparringTurn = z.infer<typeof sparringTurnSchema>;

/** 6項目を一度に送るフォーム。空欄の項目は入れない */
export type SparringForm = z.infer<typeof sparringFormSchema>;

export type SparringResponse = z.infer<typeof sparringResponseSchema>;

export type Exchange = z.infer<typeof exchangeSchema>;

export type HearingTurn = z.infer<typeof hearingTurnSchema>;

export type Candidate = z.infer<typeof candidateSchema>;

/** requirements §6.2 の8分類 */
export type PlanCategory = Candidate["category"];

export type HearingResponse = z.infer<typeof hearingResponseSchema>;

/** 提案の根拠にした過去のリリース1件。転載件数はサーバーが応答に載せない */
export type ProposalCase = z.infer<typeof proposalCaseSchema>;

export type Suggestion = z.infer<typeof suggestionSchema>;

export type ProposalResponse = z.infer<typeof proposalResponseSchema>;

export type ProposalRequest = z.infer<typeof proposalRequestSchema>;

/** Google カレンダーの予定1件。キーは Google Calendar API の名前のまま */
export type CalendarEvent = z.infer<typeof calendarEventSchema>;

/** 予定を引く期間。キーもサーバーに合わせて camelCase */
export type CalendarRange = z.infer<typeof eventQuerySchema>;

export type CalendarStatus = z.infer<typeof calendarStatusSchema>;

/** デモでログインする人。名前だけ渡す */
export type DemoLogin = z.infer<typeof demoLoginSchema>;

/** 画面から足す予定1件 */
export type EventCreate = z.infer<typeof eventCreateSchema>;

export type CalendarEvents = z.infer<typeof calendarEventsSchema>;
