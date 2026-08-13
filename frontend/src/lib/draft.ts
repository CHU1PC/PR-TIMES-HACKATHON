import { formatDate } from "@/lib/date";
import type { PlanDraft, Presence, SlotCode, YesNo } from "@/types";

const SLOT_NAMES = {
  place: "場所",
  partner: "社外で関わる相手",
  people: "当日その場にいる人",
  novelty: "御社として初めてのこと",
  observation: "当日見聞きできそうなこと",
  video: "すでにある動画",
} as const satisfies Record<SlotCode, string>;

const PEOPLE_TEXT = {
  yes: "います",
  no: "いません",
  unknown: "わからない",
} as const satisfies Record<Presence, string>;

const VIDEO_TEXT = {
  yes: "あります",
  no: "ありません",
} as const satisfies Record<YesNo, string>;

/** 壁打ちの初回に投げる空の内容。title だけ入れる。 */
export function newDraft(title: string): PlanDraft {
  return {
    title,
    start_date: null,
    place: null,
    partner: [],
    people: null,
    novelty: null,
    observation: null,
    video: null,
    skipped: [],
    retried: [],
  };
}

export interface SummaryRow {
  label: string;
  value: string;
}

/** 埋まった項目だけを一覧にする。null は「まだ聞いていない」なので出さない。 */
export function summaryRows(draft: PlanDraft): SummaryRow[] {
  const rows: SummaryRow[] = [{ label: "やること", value: draft.title }];
  if (draft.start_date) rows.push({ label: "開始日", value: formatDate(draft.start_date) });
  if (draft.place) rows.push({ label: SLOT_NAMES.place, value: draft.place });
  if (draft.partner.length > 0) rows.push({ label: SLOT_NAMES.partner, value: draft.partner.join("、") });
  if (draft.people) rows.push({ label: SLOT_NAMES.people, value: PEOPLE_TEXT[draft.people] });
  if (draft.novelty) rows.push({ label: SLOT_NAMES.novelty, value: draft.novelty });
  if (draft.observation) rows.push({ label: SLOT_NAMES.observation, value: draft.observation });
  if (draft.video) rows.push({ label: SLOT_NAMES.video, value: VIDEO_TEXT[draft.video] });
  return rows;
}
