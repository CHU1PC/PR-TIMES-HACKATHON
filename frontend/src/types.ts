import type { z } from "zod";

import type {
  calendarEventSchema,
  calendarEventsSchema,
  calendarRangeSchema,
  calendarStatusSchema,
  candidateSchema,
  exchangeSchema,
  hearingResponseSchema,
  hearingTurnSchema,
  planCategorySchema,
  planDraftSchema,
  presenceSchema,
  proposalCaseSchema,
  proposalRequestSchema,
  proposalResponseSchema,
  slotCodeSchema,
  slotStateSchema,
  sparringResponseSchema,
  sparringTurnSchema,
  suggestionSchema,
  toneSchema,
  yesNoSchema,
} from "@/lib/schemas";

export type SlotCode = z.infer<typeof slotCodeSchema>;

export type PlanCategory = z.infer<typeof planCategorySchema>;

/** 当日その場に人がいるか。null は「まだ聞いていない」 */
export type Presence = z.infer<typeof presenceSchema>;

/** すでにある動画の有無。null は「まだ聞いていない」 */
export type YesNo = z.infer<typeof yesNoSchema>;

/** causal は判定クエリC を通ったスロットのみ */
export type Tone = z.infer<typeof toneSchema>;

export type PlanDraft = z.infer<typeof planDraftSchema>;

export type SparringTurn = z.infer<typeof sparringTurnSchema>;

export type SlotState = z.infer<typeof slotStateSchema>;

export type SparringResponse = z.infer<typeof sparringResponseSchema>;

export type Exchange = z.infer<typeof exchangeSchema>;

export type HearingTurn = z.infer<typeof hearingTurnSchema>;

export type Candidate = z.infer<typeof candidateSchema>;

export type HearingResponse = z.infer<typeof hearingResponseSchema>;

/** 提案の根拠にした過去のリリース1件。転載件数はサーバーが応答に載せない */
export type ProposalCase = z.infer<typeof proposalCaseSchema>;

export type Suggestion = z.infer<typeof suggestionSchema>;

export type ProposalResponse = z.infer<typeof proposalResponseSchema>;

export type ProposalRequest = z.infer<typeof proposalRequestSchema>;

/** Google カレンダーの予定1件。キーは Google Calendar API の名前のまま */
export type CalendarEvent = z.infer<typeof calendarEventSchema>;

export type CalendarRange = z.infer<typeof calendarRangeSchema>;

export type CalendarStatus = z.infer<typeof calendarStatusSchema>;

export type CalendarEvents = z.infer<typeof calendarEventsSchema>;
