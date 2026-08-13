import { useCallback, useEffect, useRef, useState } from "react";
import { sparringStep, type ApiFailure } from "@/api";
import { AskPanel } from "@/components/AskPanel";
import { ChatLog } from "@/components/ChatLog";
import { ReplyForm } from "@/components/ReplyForm";
import { SlotChecklist } from "@/components/SlotChecklist";
import { TurnStatus } from "@/components/TurnStatus";
import { newDraft, summaryRows } from "@/lib/draft";
import { clearSparring, loadSparring, saveSparring, type ChatMessage, type SparringSession } from "@/lib/session";
import { Link, navigate, useQueryParam } from "@/router";
import type { SparringTurn } from "@/types";

function freshSession(title: string): SparringSession {
  return { title, draft: newDraft(title), messages: [], slots: [], question: null, hint: null, ready: false };
}

export function SparringPage() {
  const titleParam = useQueryParam("title");
  const title = (titleParam ?? "").trim();

  const [session, setSession] = useState<SparringSession | null>(null);
  const [resumed, setResumed] = useState(false);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiFailure | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const lastTurnRef = useRef<SparringTurn | null>(null);
  const startedRef = useRef(false);

  const send = useCallback(async (turn: SparringTurn, base: SparringSession) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    lastTurnRef.current = turn;
    setPending(true);
    setFailure(null);

    const result = await sparringStep(turn, controller.signal);
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

    const { draft, question, hint, slots, ready } = result.data;
    const next: SparringSession = { title: base.title, draft, messages: base.messages, slots, question, hint, ready };
    setSession(next);
    saveSparring(next);
  }, []);

  useEffect(() => {
    if (!title) {
      navigate("/", { replace: true });
      return;
    }
    if (!startedRef.current) {
      startedRef.current = true;
      const saved = loadSparring();
      if (saved && saved.title === title) {
        setSession(saved);
        setResumed(true);
      } else {
        const started = freshSession(title);
        setSession(started);
        void send({ draft: started.draft, reply: "" }, started);
      }
    }
    return () => {
      controllerRef.current?.abort();
      startedRef.current = false;
    };
  }, [title, send]);

  // 答え終わった往復だけを会話に積む。いま出ている質問は AskPanel が持つ
  const handleSend = (text: string) => {
    if (!session || !session.question || pending) return;
    const answered: ChatMessage[] = [
      { role: "ai", text: session.question },
      { role: "you", text },
    ];
    const echoed: SparringSession = { ...session, messages: [...session.messages, ...answered] };
    setResumed(false);
    setSession(echoed);
    saveSparring(echoed);
    void send({ draft: echoed.draft, reply: text }, echoed);
  };

  const handleRetry = () => {
    const turn = lastTurnRef.current;
    if (!session || !turn || pending) return;
    void send(turn, session);
  };

  const handleRestart = () => {
    clearSparring();
    const started = freshSession(title);
    setSession(started);
    setResumed(false);
    void send({ draft: started.draft, reply: "" }, started);
  };

  if (!session) {
    return (
      <p className="state" role="status" aria-live="polite">
        読み込んでいます…
      </p>
    );
  }

  return (
    <section className="page sparring">
      <div className="sparring__main">
        <h1 className="page__title">{session.title}</h1>

        {resumed ? (
          <p className="resume-note">
            前回の続きから再開しました。
            <button type="button" className="button button--small" onClick={handleRestart}>
              最初からやり直す
            </button>
          </p>
        ) : null}

        <ChatLog messages={session.messages} />

        {session.question ? <AskPanel question={session.question} hint={session.hint} /> : null}

        <TurnStatus
          pending={pending}
          failure={failure}
          completed={session.ready ? "出せる形になりました。決まった内容を下にまとめています。" : null}
          onRetry={handleRetry}
        />

        {session.ready ? (
          <section className="ready">
            <h2 className="ready__title">出せる形になりました</h2>
            <dl className="ready__list">
              {summaryRows(session.draft).map((row) => (
                <div key={row.label} className="ready__row">
                  <dt>{row.label}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
            </dl>
            <button type="button" className="button button--wide" onClick={() => navigate("/proposal")}>
              似た事例から, 足せることを見る
            </button>
            <p className="ready__note">
              <Link to="/" className="entry__link">
                別の予定を入れる
              </Link>
            </p>
          </section>
        ) : session.question ? (
          <ReplyForm pending={pending} onSend={handleSend} />
        ) : null}
      </div>

      <aside className="sparring__side">
        <SlotChecklist slots={session.slots} />
      </aside>
    </section>
  );
}
