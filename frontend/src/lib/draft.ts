import { formatDate } from "@/lib/date";
import type { CalendarEvent, PlanDraft, Presence, SlotCode, YesNo } from "@/types";

/** サーバーが予定に載せてくる draft。既定値持ちのキーは省かれることがある */
type SavedDraft = NonNullable<CalendarEvent["draft"]>;

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

/** 壁打ちの初回に投げる空の内容。選択済みの日付があれば開始日に入れる。 */
export function newDraft(title: string, startDate: string | null = null): PlanDraft {
  return {
    title,
    start_date: startDate,
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

/** 予定に保存されていた内容を, 欠けの無い形に揃える。 */
export function restoredDraft(saved: SavedDraft, title: string, startDate: string | null): PlanDraft {
  return {
    title: saved.title || title,
    start_date: saved.start_date ?? startDate,
    place: saved.place ?? null,
    partner: saved.partner ?? [],
    people: saved.people ?? null,
    novelty: saved.novelty ?? null,
    observation: saved.observation ?? null,
    video: saved.video ?? null,
    skipped: saved.skipped ?? [],
    retried: saved.retried ?? [],
  };
}

/** 決まっている値をフォームの初期値にする。未回答は空欄 */
export function draftAnswers(draft: PlanDraft): Record<SlotCode, string> {
  return {
    place: draft.place ?? "",
    partner: draft.partner.join("、"),
    people: draft.people ? PEOPLE_TEXT[draft.people] : "",
    novelty: draft.novelty ?? "",
    observation: draft.observation ?? "",
    video: draft.video ? VIDEO_TEXT[draft.video] : "",
  };
}

/** 書き換えた項目を空に戻す。サーバーは値が入っている項目を上書きしない */
export function clearSlots(draft: PlanDraft, codes: readonly SlotCode[]): PlanDraft {
  const next: PlanDraft = { ...draft };
  for (const code of codes) {
    if (code === "partner") next.partner = [];
    else if (code === "people") next.people = null;
    else if (code === "video") next.video = null;
    else next[code] = null;
  }
  return next;
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
