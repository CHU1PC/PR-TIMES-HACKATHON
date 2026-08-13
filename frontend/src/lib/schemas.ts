import { z } from "zod";

/** requirements §6.2 の8分類 */
export const planCategorySchema = z.enum([
  "販売・提供の開始/拡大",
  "提携・連携の開始",
  "場所・チャネルの追加",
  "商品・サービスの改訂",
  "人・組織の変化",
  "受賞・認定",
  "数字の節目",
  "外部イベント出展",
]);

export const slotCodeSchema = z.enum(["place", "partner", "people", "novelty", "observation", "video"]);

/** 当日その場に人がいるか。null は「まだ聞いていない」 */
export const presenceSchema = z.enum(["yes", "no", "unknown"]);

/** すでにある動画の有無。null は「まだ聞いていない」 */
export const yesNoSchema = z.enum(["yes", "no"]);

/** causal は判定クエリC を通ったスロットのみ */
export const toneSchema = z.enum(["causal", "functional"]);

export const planDraftSchema = z.object({
  /** これからやることを1行で */
  title: z.string(),
  /** 開始日 YYYY-MM-DD。未定なら null */
  start_date: z.string().nullable(),
  /** 市区町村または都道府県。オンライン可 */
  place: z.string().nullable(),
  /** 社外で関わる相手の名前 */
  partner: z.array(z.string()),
  /** 当日その場に人がいるか */
  people: presenceSchema.nullable(),
  /** 御社として初めてのこと */
  novelty: z.string().nullable(),
  /** 当日見聞きできそうなこと */
  observation: z.string().nullable(),
  /** すでにある動画の有無 */
  video: yesNoSchema.nullable(),
  /** 聞いたが該当が無かった項目 */
  skipped: z.array(slotCodeSchema),
  /** 読み取れず聞き直した項目 */
  retried: z.array(slotCodeSchema),
});

export const sparringTurnSchema = z.object({
  /** いま分かっているイベント内容 */
  draft: planDraftSchema,
  /** 直前の質問への顧客の返答。初回は空 */
  reply: z.string(),
});

export const slotStateSchema = z.object({
  /** スロット識別子 */
  code: slotCodeSchema,
  /** 顧客に見せる質問文 */
  label: z.string(),
  /** 値が入っているか */
  filled: z.boolean(),
  /** 聞いたが該当が無かったか */
  skipped: z.boolean(),
  /** 埋まると何が起きるか。サーバーの文言をそのまま出す */
  effect: z.string(),
  /** causal は判定クエリC を通ったスロットのみ */
  tone: toneSchema,
});

/** サーバー応答を信用しない。壊れた値を localStorage に書いてから落ちるのを防ぐ。 */
export const sparringResponseSchema = z.object({
  /** 返答を反映した後のイベント内容 */
  draft: planDraftSchema,
  /** 次に聞くこと。全部済んだら null */
  question: z.string().nullable(),
  /** 答えやすくするための例示 */
  hint: z.string().nullable(),
  /** チェックリスト。サーバーが決めた順に並ぶ */
  slots: z.array(slotStateSchema),
  /** 出せる形になったか */
  ready: z.boolean(),
});

export const exchangeSchema = z.object({
  /** こちらが聞いたこと */
  question: z.string(),
  /** 相手の返答。まだ答えていなければ空 */
  answer: z.string(),
});

export const hearingTurnSchema = z.object({
  /** ここまでの往復。初回は空 */
  history: z.array(exchangeSchema),
  /** 直前の質問への返答。初回は空 */
  answer: z.string(),
});

export const candidateSchema = z.object({
  /** 予定として登録する一文 */
  title: z.string(),
  /** requirements §6.2 の8分類 */
  category: planCategorySchema,
  /** 根拠になった回答の引用 */
  source: z.string(),
  /** なぜ発信できるかを1行で */
  reason: z.string(),
});

/** 同上。ヒアリング側。 */
export const hearingResponseSchema = z.object({
  /** 返答を追加した後の往復履歴 */
  history: z.array(exchangeSchema),
  /** 次に聞くこと。聞き終わったら null */
  question: z.string().nullable(),
  /** 答えやすくするための例示 */
  hint: z.string().nullable(),
  /** ここまでに見つかった予定候補 */
  candidates: z.array(candidateSchema),
  /** 聞き終わったか */
  done: z.boolean(),
});

/** 提案の根拠にした過去のリリース1件。転載件数はサーバーが応答に載せない */
export const proposalCaseSchema = z.object({
  /** PR TIMES 側の企業ID */
  company_id: z.number(),
  /** 企業内でのリリースID。企業をまたぐと重複するので単独では使わない */
  release_id: z.number(),
  title: z.string(),
  subtitle: z.string(),
  /** 本文冒頭をHTML除去して1000文字 */
  body_head: z.string(),
  company_name: z.string().nullable(),
  business_category: z.string().nullable(),
  release_type: z.string().nullable(),
  prefecture: z.string().nullable(),
  city: z.string().nullable(),
  /** 配信日 YYYY-MM-DD */
  published_on: z.string(),
  /** この事例を拾った媒体のうち特徴的なもの */
  media: z.array(z.string()),
});

export const suggestionSchema = z.object({
  /** この取り組みに足せること */
  action: z.string(),
  /** 事例のどこから言えるのか */
  reason: z.string(),
  /** 根拠にした事例。cases 配列の0始まりの添字 */
  cited: z.array(z.number()),
});

/** 同上。提案側。cited が cases の範囲に収まっているかまで見る。 */
export const proposalResponseSchema = z
  .object({
    /** 足せること */
    suggestions: z.array(suggestionSchema),
    /** 根拠にした事例 */
    cases: z.array(proposalCaseSchema),
    /** 事例群を拾っていた媒体のうち特徴的なもの */
    media: z.array(z.string()),
  })
  .superRefine((value, ctx) => {
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

export const proposalRequestSchema = z.object({
  /** 壁打ちで埋めたイベント内容 */
  draft: planDraftSchema,
});

/** Google カレンダーの予定1件。キーは Google Calendar API の名前のまま */
export const calendarEventSchema = z.object({
  id: z.string(),
  /** Google 側が空なら「(タイトルなし)」が入る */
  title: z.string(),
  /** 未設定なら空文字 */
  description: z.string(),
  /** 未設定なら空文字 */
  location: z.string(),
  /** RFC3339。終日の予定は YYYY-MM-DD */
  start: z.string(),
  /** RFC3339。終日の予定は YYYY-MM-DD */
  end: z.string(),
  /** Google カレンダーで開く先 */
  htmlLink: z.string().nullable(),
});

/** 予定を引く期間。キーもサーバーに合わせて camelCase */
export const calendarRangeSchema = z.object({
  /** 取得開始時刻 (RFC3339) */
  timeMin: z.string(),
  /** 取得終了時刻 (RFC3339) */
  timeMax: z.string(),
});

export const calendarStatusSchema = z.object({
  /** この環境で連携機能が使えるか。false なら連携ボタンを出さない */
  configured: z.boolean(),
  /** この人が Google と連携済みか */
  connected: z.boolean(),
});

export const calendarEventsSchema = z.object({
  /** Google と連携済みか */
  connected: z.boolean(),
  /** 未連携なら空 */
  events: z.array(calendarEventSchema),
});
