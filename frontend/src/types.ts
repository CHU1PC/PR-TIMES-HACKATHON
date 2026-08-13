export type SlotCode = "place" | "partner" | "people" | "novelty" | "observation" | "video";

export type PlanCategory =
  | "販売・提供の開始/拡大"
  | "提携・連携の開始"
  | "場所・チャネルの追加"
  | "商品・サービスの改訂"
  | "人・組織の変化"
  | "受賞・認定"
  | "数字の節目"
  | "外部イベント出展";

/** 当日その場に人がいるか。null は「まだ聞いていない」 */
export type Presence = "yes" | "no" | "unknown";

/** すでにある動画の有無。null は「まだ聞いていない」 */
export type YesNo = "yes" | "no";

/** causal は判定クエリC を通ったスロットのみ */
export type Tone = "causal" | "functional";

export interface PlanDraft {
  /** これからやることを1行で */
  title: string;
  /** 開始日 YYYY-MM-DD。未定なら null */
  start_date: string | null;
  /** 市区町村または都道府県。オンライン可 */
  place: string | null;
  /** 社外で関わる相手の名前 */
  partner: string[];
  /** 当日その場に人がいるか */
  people: Presence | null;
  /** 御社として初めてのこと */
  novelty: string | null;
  /** 当日見聞きできそうなこと */
  observation: string | null;
  /** すでにある動画の有無 */
  video: YesNo | null;
  /** 聞いたが該当が無かった項目 */
  skipped: SlotCode[];
  /** 読み取れず聞き直した項目 */
  retried: SlotCode[];
}

export interface SparringTurn {
  /** いま分かっているイベント内容 */
  draft: PlanDraft;
  /** 直前の質問への顧客の返答。初回は空 */
  reply: string;
}

export interface SlotState {
  /** スロット識別子 */
  code: SlotCode;
  /** 顧客に見せる質問文 */
  label: string;
  /** 値が入っているか */
  filled: boolean;
  /** 聞いたが該当が無かったか */
  skipped: boolean;
  /** 埋まると何が起きるか。サーバーの文言をそのまま出す */
  effect: string;
  /** causal は判定クエリC を通ったスロットのみ */
  tone: Tone;
}

export interface SparringResponse {
  /** 返答を反映した後のイベント内容 */
  draft: PlanDraft;
  /** 次に聞くこと。全部済んだら null */
  question: string | null;
  /** 答えやすくするための例示 */
  hint: string | null;
  /** チェックリスト。サーバーが決めた順に並ぶ */
  slots: SlotState[];
  /** 出せる形になったか */
  ready: boolean;
}

export interface Exchange {
  /** こちらが聞いたこと */
  question: string;
  /** 相手の返答。まだ答えていなければ空 */
  answer: string;
}

export interface HearingTurn {
  /** ここまでの往復。初回は空 */
  history: Exchange[];
  /** 直前の質問への返答。初回は空 */
  answer: string;
}

export interface Candidate {
  /** 予定として登録する一文 */
  title: string;
  /** requirements §6.2 の8分類 */
  category: PlanCategory;
  /** 根拠になった回答の引用 */
  source: string;
  /** なぜ発信できるかを1行で */
  reason: string;
}

export interface HearingResponse {
  /** 返答を追加した後の往復履歴 */
  history: Exchange[];
  /** 次に聞くこと。聞き終わったら null */
  question: string | null;
  /** 答えやすくするための例示 */
  hint: string | null;
  /** ここまでに見つかった予定候補 */
  candidates: Candidate[];
  /** 聞き終わったか */
  done: boolean;
}
