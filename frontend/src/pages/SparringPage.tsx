import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { calendarEvents, fetchProposal, saveDraft, sparringFill, sparringStep, type ApiFailure } from "@/api";
import { AskPanel } from "@/components/AskPanel";
import { Icon } from "@/components/Icon";
import { ProposalPanel } from "@/components/ProposalPanel";
import { TurnStatus } from "@/components/TurnStatus";
import { dayRange, formatDate, isValidDate } from "@/lib/date";
import { clearSlots, draftAnswers, newDraft, restoredDraft, summaryRows } from "@/lib/draft";
import { loadSparring, saveSparring, type SparringSession } from "@/lib/session";
import { Link, navigate, useQueryParam } from "@/router";
import type { PlanDraft, ProposalResponse, SlotCode, SlotState, SparringForm } from "@/types";

type Answers = Record<SlotCode, string>;

const EMPTY_ANSWERS: Answers = { place: "", partner: "", people: "", novelty: "", observation: "", video: "" };

const STATUS_TEXT = { filled: "入りました", skipped: "該当なし", waiting: "まだ聞いていません" } as const;

/** 粗くて読み取れなかった項目。埋まっても該当なしでもない1件だけが残る */
function retrySlot(slots: SlotState[]): SlotCode | null {
  return slots.find((slot) => !slot.filled && !slot.skipped)?.code ?? null;
}

function statusOf(slot: SlotState): keyof typeof STATUS_TEXT {
  if (slot.filled) return "filled";
  if (slot.skipped) return "skipped";
  return "waiting";
}

function withAnswer(answers: Answers, code: SlotCode, text: string): Answers {
  const next: Answers = { ...answers };
  next[code] = text;
  return next;
}

export function SparringPage() {
  const titleParam = useQueryParam("title");
  const dateParam = useQueryParam("date");
  const eventIdParam = useQueryParam("eventId");
  const title = (titleParam ?? "").trim();
  const startDate = isValidDate(dateParam) ? dateParam : null;
  const eventId = eventIdParam && eventIdParam.trim() !== "" ? eventIdParam.trim() : null;

  const [session, setSession] = useState<SparringSession | null>(null);
  const [answers, setAnswers] = useState<Answers>(EMPTY_ANSWERS);
  const [baseline, setBaseline] = useState<Answers>(EMPTY_ANSWERS);
  const [retryText, setRetryText] = useState("");
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiFailure | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);

  const [proposal, setProposal] = useState<ProposalResponse | null>(null);
  const [proposalPending, setProposalPending] = useState(false);
  const [proposalFailure, setProposalFailure] = useState<ApiFailure | null>(null);
  const [proposalStale, setProposalStale] = useState(false);

  const formRef = useRef<AbortController | null>(null);
  const proposalRef = useRef<AbortController | null>(null);
  const lastFormRef = useRef<SparringForm | null>(null);
  const lastAnswersRef = useRef<Answers>(EMPTY_ANSWERS);
  const proposalLoadedRef = useRef(false);
  const startedRef = useRef(false);

  const loadProposal = useCallback(async (draft: PlanDraft) => {
    proposalRef.current?.abort();
    const controller = new AbortController();
    proposalRef.current = controller;
    setProposalPending(true);
    setProposalFailure(null);
    setProposalStale(false);

    const result = await fetchProposal({ draft }, controller.signal);
    if (controller.signal.aborted) {
      if (proposalRef.current === controller) setProposalPending(false);
      return;
    }
    setProposalPending(false);
    if (!result.ok) {
      if (result.kind !== "cancelled") setProposalFailure(result);
      return;
    }
    proposalLoadedRef.current = true;
    setProposal(result.data);
  }, []);

  const persist = useCallback(async (draft: PlanDraft) => {
    if (!eventId) return;
    const result = await saveDraft(eventId, draft);
    setSavedNote(result.ok ? "この予定に保存しました。" : "この予定に保存できませんでした。");
  }, [eventId]);

  const send = useCallback(
    async (form: SparringForm, texts: Answers) => {
      formRef.current?.abort();
      const controller = new AbortController();
      formRef.current = controller;
      lastFormRef.current = form;
      lastAnswersRef.current = texts;
      setPending(true);
      setFailure(null);
      setSavedNote(null);

      const result = await sparringFill(form, controller.signal);
      if (controller.signal.aborted) {
        // 後続の送信が無いまま中断されると pending が戻らず, 送信ボタンが永久に無効になる
        if (formRef.current === controller) setPending(false);
        return;
      }
      setPending(false);
      if (!result.ok) {
        if (result.kind !== "cancelled") setFailure(result);
        return;
      }

      const { draft, question, hint, slots, ready } = result.data;
      const next: SparringSession = { title, eventId, draft, slots, question, hint, ready };
      setSession(next);
      saveSparring(next);
      // 読み取れた形ではなく書いた文をそのまま残す。消えると直しようがない
      setAnswers(texts);
      setBaseline(texts);
      setRetryText("");

      void persist(draft);
      if (!ready) return;
      // 初回だけ自動で取りに行く。以降は作り直すボタンに任せて LLM 呼び出しを増やさない
      if (proposalLoadedRef.current) setProposalStale(true);
      else void loadProposal(draft);
    },
    [title, eventId, persist, loadProposal],
  );

  const start = useCallback(async () => {
    formRef.current?.abort();
    const controller = new AbortController();
    formRef.current = controller;
    setPending(true);
    setFailure(null);

    let restored: PlanDraft | null = null;
    if (eventId && startDate) {
      const found = await calendarEvents(dayRange(startDate), controller.signal);
      const event = found.ok ? found.data.events.find((item) => item.id === eventId) : undefined;
      if (event?.draft) restored = restoredDraft(event.draft, title, startDate);
    }
    if (!restored) {
      // ID を持たない経路の受け皿。同じ予定のときだけ引き継ぐ
      const saved = loadSparring();
      if (saved && saved.title === title && saved.eventId === eventId) restored = saved.draft;
    }

    const base = restored ?? newDraft(title, startDate);
    // slots の質問文と効果を取りに行くだけ。空の返答は内容を書き換えない
    const result = await sparringStep({ draft: base, reply: "" }, controller.signal);
    if (controller.signal.aborted) {
      if (formRef.current === controller) setPending(false);
      return;
    }
    setPending(false);
    if (!result.ok) {
      if (result.kind !== "cancelled") setFailure(result);
      return;
    }

    const { draft, slots, ready } = result.data;
    setSession({ title, eventId, draft, slots, question: null, hint: null, ready });
    const texts = draftAnswers(draft);
    setAnswers(texts);
    setBaseline(texts);
    if (ready) void loadProposal(draft);
  }, [title, startDate, eventId, loadProposal]);

  useEffect(() => {
    if (!title) {
      navigate("/", { replace: true });
      return;
    }
    if (!startedRef.current) {
      startedRef.current = true;
      void start();
    }
    return () => {
      formRef.current?.abort();
      proposalRef.current?.abort();
      startedRef.current = false;
    };
  }, [title, start]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!session || pending) return;

    const written: Record<string, string> = {};
    const changed: SlotCode[] = [];
    for (const slot of session.slots) {
      const text = answers[slot.code].trim();
      if (text !== baseline[slot.code].trim()) changed.push(slot.code);
      if (text) written[slot.code] = text;
    }
    // 書き換えた項目を空に戻さないと, サーバーが既存の値を残して新しい答えを捨てる
    void send({ draft: clearSlots(session.draft, changed), answers: written }, answers);
  };

  const handleRetryAnswer = () => {
    if (!session || pending) return;
    const code = retrySlot(session.slots);
    const text = retryText.trim();
    if (!code || !text) return;
    const written: Record<string, string> = {};
    written[code] = text;
    void send({ draft: session.draft, answers: written }, withAnswer(answers, code, text));
  };

  // 空の答えで送ると, サーバーは残りを該当なしにして先へ進める
  const handleRetrySkip = () => {
    if (!session || pending) return;
    void send({ draft: session.draft, answers: {} }, answers);
  };

  const handleRetrySend = () => {
    if (pending) return;
    const form = lastFormRef.current;
    if (form) void send(form, lastAnswersRef.current);
    else void start();
  };

  if (!session) {
    return failure ? (
      <section className="page">
        <TurnStatus pending={pending} failure={failure} completed={null} onRetry={handleRetrySend} />
      </section>
    ) : (
      <p className="state" role="status" aria-live="polite">
        読み込んでいます…
      </p>
    );
  }

  return (
    <section className="page home-page creation-page">
      <header className="home-hero creation-hero">
        <div className="creation-hero__toolbar">
          <Link to="/" className="creation-hero__back">
            <Icon name="arrow-left" size={16} />
            ホームに戻る
          </Link>
          {startDate ? (
            <p className="creation-hero__date">
              <Icon name="calendar" size={16} />
              {formatDate(startDate)}
            </p>
          ) : null}
        </div>
        <p className="home-hero__eyebrow">
          <Icon name="sparkles" size={17} />
          イベント内容の詳細
        </p>
        <h1 className="page__title">{session.title}</h1>
      </header>

      <form className="entry entry--dashboard" onSubmit={handleSubmit}>
        <div className="entry__heading">
          <span className="entry__heading-icon">
            <Icon name="lightbulb" size={21} />
          </span>
          <div>
            <p className="entry__kicker">EVENT DETAIL</p>
            <h2 className="entry__title">この予定の中身を決める</h2>
          </div>
        </div>

        <p className="entry__description">
          すべて任意です。書ける項目だけ埋めてください。埋めた内容はこの予定に残るので、次に開いたときは聞き直しません。
        </p>

        <ul className="checklist__list slot-fields">
          {session.slots.map((slot) => {
            const status = statusOf(slot);
            return (
              <li key={slot.code} className="slot" data-code={slot.code} data-state={status} data-tone={slot.tone}>
                <label className="slot__head" htmlFor={`slot-${slot.code}`}>
                  <span className="slot__label">{slot.label}</span>
                </label>
                <p className="slot__status">{STATUS_TEXT[status]}</p>
                {/* effect はサーバーの文字列をそのまま出す。フロントで因果を足さない */}
                <p className="slot__effect">{slot.effect}</p>
                {slot.tone === "causal" ? <p className="slot__tone">実測で確かめた項目</p> : null}
                <input
                  id={`slot-${slot.code}`}
                  className="entry__input slot__input"
                  type="text"
                  value={answers[slot.code]}
                  disabled={pending}
                  onChange={(event) => setAnswers(withAnswer(answers, slot.code, event.target.value))}
                  placeholder="空欄のままでも進めます"
                />
              </li>
            );
          })}
        </ul>

        <button type="submit" className="button button--primary button--wide entry__submit" disabled={pending}>
          {session.ready ? "決めた内容を更新する" : "この内容で決める"}
          <Icon name="arrow-right" size={18} />
        </button>
      </form>

      <TurnStatus
        pending={pending}
        failure={failure}
        completed={session.ready ? "内容が決まりました。下に提案を出しています。" : null}
        onRetry={handleRetrySend}
      />

      {savedNote ? <p className="state">{savedNote}</p> : null}

      {!eventId ? (
        <p className="state">この予定はカレンダーに無いので、決めた内容はこの端末にだけ残ります。</p>
      ) : null}

      {session.question ? (
        <section className="entry entry--dashboard">
          <AskPanel question={session.question} hint={session.hint} />
          <label className="reply__label" htmlFor="retry-text">
            書き足す
          </label>
          <input
            id="retry-text"
            className="entry__input"
            type="text"
            value={retryText}
            disabled={pending}
            onChange={(event) => setRetryText(event.target.value)}
            placeholder="市区町村か都道府県だけでも構いません"
          />
          <div className="reply__actions">
            <button
              type="button"
              className="button button--primary"
              disabled={pending || retryText.trim() === ""}
              onClick={handleRetryAnswer}
            >
              {pending ? "送信中…" : "送る"}
            </button>
            <button type="button" className="button" disabled={pending} onClick={handleRetrySkip}>
              この項目は飛ばす
            </button>
          </div>
        </section>
      ) : null}

      {session.ready ? (
        <section className="ready">
          <h2 className="ready__title">決まったこと</h2>
          <dl className="ready__list">
            {summaryRows(session.draft).map((row) => (
              <div key={row.label} className="ready__row">
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}

      {session.ready || proposal ? (
        <ProposalPanel
          result={proposal}
          pending={proposalPending}
          failure={proposalFailure}
          stale={proposalStale}
          onReload={() => void loadProposal(session.draft)}
        />
      ) : null}
    </section>
  );
}
