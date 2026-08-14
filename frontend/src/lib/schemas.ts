import {
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
  planDraftSchema as generatedPlanDraftSchema,
  proposalCaseSchema,
  proposalRequestSchema,
  proposalResponseSchema as generatedProposalResponseSchema,
  slotStateSchema,
  sparringFormSchema,
  sparringResponseSchema as generatedSparringResponseSchema,
  sparringTurnSchema,
  suggestionSchema,
} from "@/gen/zod";

export {
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
  proposalCaseSchema,
  proposalRequestSchema,
  slotStateSchema,
  sparringFormSchema,
  sparringTurnSchema,
  suggestionSchema,
};

// 応答は既定値込みで全キーを載せる。生成側は default 持ちを optional にするので締め直す
export const planDraftSchema = generatedPlanDraftSchema.required();

// 生成側の draft は緩いまま。.required() は浅いので入れ替える
export const sparringResponseSchema = generatedSparringResponseSchema.extend({ draft: planDraftSchema });

/** cited が cases の範囲に収まっているかまで見る。OpenAPI では表せないので手で足す。 */
export const proposalResponseSchema = generatedProposalResponseSchema.superRefine((value, ctx) => {
  // 範囲外の添字が来ると cases[i] が undefined になり, 描画時に落ちる
  const total = value.cases.length;
  value.suggestions.forEach((suggestion, order) => {
    suggestion.cited.forEach((index, position) => {
      if (Number.isInteger(index) && index >= 0 && index < total) return;
      ctx.addIssue({
        code: "custom",
        path: ["suggestions", order, "cited", position],
        message: `cited が cases の範囲外: ${String(index)}`,
      });
    });
  });
});
