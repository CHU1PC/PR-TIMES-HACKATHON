import { useCallback, useEffect, useRef, useState } from "react";
import { hearingStep, type ApiFailure } from "@/api";
import { AskPanel } from "@/components/AskPanel";
import { ChatLog } from "@/components/ChatLog";
import { ReplyForm } from "@/components/ReplyForm";
import { TurnStatus } from "@/components/TurnStatus";
import { isValidDate } from "@/lib/date";
import { clearHearing, loadHearing, saveHearing, type ChatMessage, type HearingSession } from "@/lib/session";
import { navigate, useQueryParam } from "@/router";
import type { HearingTurn } from "@/types";

const EMPTY_SESSION: HearingSession = {
  history: [],
  messages: [],
  question: null,
  hint: null,
  candidates: [],
  done: false,
};

/** 候補一覧は live region の外なので、聞き終わりを TurnStatus に読ませる。 */
function doneMessage(session: HearingSession): string | null {
  if (!session.done) return null;
  if (session.candidates.length === 0) return "聞き取りが終わりました。今回は候補が見つかりませんでした。";
  return `聞き取りが終わりました。出せそうな予定が${String(session.candidates.length)}件あります。`;
}

export function HearingPage() {
  const dateParam = useQueryParam("date");
  const selectedDate = isValidDate(dateParam) ? dateParam : null;
  const [session, setSession] = useState<HearingSession | null>(null);
  const [resumed, setResumed] = useState(false);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiFailure | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const lastTurnRef = useRef<HearingTurn | null>(null);
  const startedRef = useRef(false);

  const send = useCallback(async (turn: HearingTurn, base: HearingSession) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    lastTurnRef.current = turn;
    setPending(true);
    setFailure(null);

    const result = await hearingStep(turn, controller.signal);
    if (controller.signal.aborted) {
      // 後続の送信が無いまま中断されると pending が戻らず, 送信ボタンが永久に無効になる
      if (controllerRef.current === controller) setPending(false);
      return;
    }
    setPending(false);
    if (!result.ok) {
      if (result.kind !== "cancelled") setFailure(result);
      return;
    }

    const { history, question, hint, candidates, done } = result.data;
    const next: HearingSession = { history, messages: base.messages, question, hint, candidates, done };
    setSession(next);
    saveHearing(next);
  }, []);

  useEffect(() => {
    if (!startedRef.current) {
      startedRef.current = true;
      const saved = loadHearing();
      if (saved) {
        setSession(saved);
        setResumed(true);
      } else {
        setSession(EMPTY_SESSION);
        void send({ history: [], answer: "" }, EMPTY_SESSION);
      }
    }
    return () => {
      controllerRef.current?.abort();
      startedRef.current = false;
    };
  }, [send]);

  // 答え終わった往復だけを会話に積む。いま出ている質問は AskPanel が持つ
  const handleSend = (text: string) => {
    if (!session || !session.question || pending) return;
    const answered: ChatMessage[] = [
      { role: "ai", text: session.question },
      { role: "you", text },
    ];
    const echoed: HearingSession = { ...session, messages: [...session.messages, ...answered] };
    setResumed(false);
    setSession(echoed);
    saveHearing(echoed);
    void send({ history: echoed.history, answer: text }, echoed);
  };

  const handleRetry = () => {
    const turn = lastTurnRef.current;
    if (!session || !turn || pending) return;
    void send(turn, session);
  };

  const handleRestart = () => {
    clearHearing();
    setSession(EMPTY_SESSION);
    setResumed(false);
    void send({ history: [], answer: "" }, EMPTY_SESSION);
  };

  if (!session) {
    return (
      <p className="state" role="status" aria-live="polite">
        読み込んでいます…
      </p>
    );
  }

  return (
    <section className="page">
      <h1 className="page__title">すでにやっていることから探します</h1>
      <p className="page__lead">思いつかなくて構いません。いま続けていることを教えてください。</p>

      {resumed ? (
        <p className="resume-note">
          前回の続きから再開しました。
          <button type="button" className="button button--small" onClick={handleRestart}>
            最初から聞き直す
          </button>
        </p>
      ) : null}

      <ChatLog messages={session.messages} />

      {session.question ? <AskPanel question={session.question} hint={session.hint} /> : null}

      <TurnStatus pending={pending} failure={failure} completed={doneMessage(session)} onRetry={handleRetry} />

      {session.done ? (
        <section className="candidates">
          <h2 className="candidates__title">出せそうな予定</h2>
          {session.candidates.length === 0 ? (
            <p className="page__lead">今回は候補が見つかりませんでした。もう一度聞き直すこともできます。</p>
          ) : (
            <ul className="candidates__list">
              {session.candidates.map((candidate) => (
                <li key={`${candidate.category}-${candidate.title}`} className="candidate">
                  <p className="candidate__title">{candidate.title}</p>
                  <p className="candidate__category">{candidate.category}</p>
                  <p className="candidate__reason">{candidate.reason}</p>
                  <p className="candidate__source">お話しいただいたこと: {candidate.source}</p>
                  <button
                    type="button"
                    className="button button--primary"
                    onClick={() => {
                      const params = new URLSearchParams({ title: candidate.title });
                      if (selectedDate) params.set("date", selectedDate);
                      navigate(`/sparring?${params.toString()}`);
                    }}
                  >
                    この予定で進む
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="candidates__again">
            <button type="button" className="button button--small" onClick={handleRestart}>
              最初から聞き直す
            </button>
          </p>
        </section>
      ) : session.question ? (
        <ReplyForm pending={pending} onSend={handleSend} />
      ) : null}
    </section>
  );
}
