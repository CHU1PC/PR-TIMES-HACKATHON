import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { calendarEvents, createPlan } from "@/api";
import { Icon } from "@/components/Icon";
import { dayRange, formatDate, isValidDate } from "@/lib/date";
import { Link, navigate, useQueryParam } from "@/router";
import type { CalendarEvent } from "@/types";

const DEFAULT_START = "10:00";
const DEFAULT_END = "11:00";

function todayKey(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const date = String(now.getDate()).padStart(2, "0");
  return `${String(now.getFullYear())}-${month}-${date}`;
}

/** "YYYY-MM-DD" と "HH:MM" を地域時間の RFC3339 にする */
function atTime(day: string, time: string): string {
  const [year, month, date] = day.split("-").map(Number);
  const [hour, minute] = time.split(":").map(Number);
  return new Date(year ?? 0, (month ?? 1) - 1, date ?? 1, hour ?? 0, minute ?? 0, 0).toISOString();
}

/** 翌日の 0時。終日の終端に使う */
function nextMidnight(day: string): string {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year ?? 0, (month ?? 1) - 1, (date ?? 1) + 1, 0, 0, 0).toISOString();
}

/** 予定の開始を画面に出す。終日は時刻を持たない */
function startLabel(event: CalendarEvent): string {
  if (event.start.length === 10) return "終日";
  return new Intl.DateTimeFormat("ja-JP", { hour: "2-digit", minute: "2-digit" }).format(new Date(event.start));
}

/** 予定IDまで渡す。決めた内容をその予定に保存できるのは ID があるときだけ */
function entryPath(day: string, title: string, eventId: string): string {
  return `/entry?${new URLSearchParams({ date: day, title, eventId }).toString()}`;
}

export function DayPage() {
  const dateParam = useQueryParam("date");
  const day = isValidDate(dateParam) ? dateParam : todayKey();

  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [allDay, setAllDay] = useState(false);
  const [startTime, setStartTime] = useState(DEFAULT_START);
  const [endTime, setEndTime] = useState(DEFAULT_END);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);

  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback((): AbortController => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    void (async () => {
      const result = await calendarEvents(dayRange(day), controller.signal);
      if (controller.signal.aborted) return;
      if (!result.ok) {
        if (result.kind === "cancelled") return;
        // 未ログインとセッション切れだけ一覧を空にする。追加を押した時点で改めて知らせる
        if (result.kind === "unauthorized") {
          setEvents([]);
          setLoadError(false);
          return;
        }
        // 一時的な失敗は直前の一覧を残して知らせる
        setLoadError(true);
        return;
      }
      setEvents(result.data.events);
      setLoadError(false);
    })();

    return controller;
  }, [day]);

  useEffect(() => {
    // その回のコントローラだけを閉じ込め, cleanup では別の呼び出しを止めない
    const controller = load();

    return () => {
      controller.abort();
    };
  }, [load]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = title.trim();
    if (!trimmed || pending) return;

    setPending(true);
    setMessage(null);
    const result = await createPlan({
      title: trimmed,
      description: description.trim(),
      allDay,
      // 終日は日付の頭から翌日の頭まで。Google の終日予定と同じ持ち方に揃える
      startsAt: allDay ? atTime(day, "00:00") : atTime(day, startTime),
      endsAt: allDay ? nextMidnight(day) : atTime(day, endTime),
    });
    setPending(false);

    if (!result.ok) {
      setMessage(result.kind === "unauthorized" ? "ログインしてから追加してください。" : result.message);
      return;
    }

    setTitle("");
    setDescription("");
    load();
  };

  return (
    <section className="page home-page creation-page">
      <header className="home-hero creation-hero">
        <div className="creation-hero__toolbar">
          <Link to="/" className="creation-hero__back">
            <Icon name="arrow-left" size={16} />
            ホームに戻る
          </Link>
          <p className="creation-hero__date">
            <Icon name="calendar" size={16} />
            {formatDate(day)}
          </p>
        </div>
        <p className="home-hero__eyebrow">
          <Icon name="calendar" size={17} />
          この日の予定
        </p>
      </header>

      <section className="entry entry--dashboard">
        <div className="entry__heading">
          <span className="entry__heading-icon">
            <Icon name="calendar" size={21} />
          </span>
          <div>
            <p className="entry__kicker">SCHEDULE</p>
            <h2 className="entry__title">この日の予定</h2>
          </div>
        </div>

        {loadError ? (
          <div className="state state--error" role="alert">
            <p className="state__message">予定を読み込めませんでした。再読み込みしてください。</p>
            <button type="button" className="button" onClick={() => { load(); }}>
              再試行
            </button>
          </div>
        ) : null}

        {events.length > 0 ? (
          <ul className="day-plans">
            {events.map((event) => (
              <li key={event.id} className="day-plan">
                <div className="day-plan__body">
                  <p className="day-plan__time">{startLabel(event)}</p>
                  <div>
                    <p className="day-plan__title">{event.title}</p>
                    {event.description ? <p className="day-plan__description">{event.description}</p> : null}
                  </div>
                </div>
                <Link to={entryPath(day, event.title, event.id)} className="button button--primary">
                  イベント内容の詳細を決める
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
        {events.length === 0 && !loadError ? (
          <p className="entry__description">この日にはまだ予定がありません。下から追加できます。</p>
        ) : null}
      </section>

      <form className="entry entry--dashboard" onSubmit={(event) => void handleSubmit(event)}>
        <div className="entry__heading">
          <span className="entry__heading-icon">
            <Icon name="plus" size={21} />
          </span>
          <div>
            <p className="entry__kicker">NEW EVENT</p>
            <h2 className="entry__title">予定を追加する</h2>
          </div>
        </div>

        <label className="entry__label" htmlFor="plan-title">
          件名
        </label>
        <input
          id="plan-title"
          className="entry__input"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="例: 郵便局での取り扱い開始"
        />

        <label className="entry__check">
          <input type="checkbox" checked={allDay} onChange={(event) => setAllDay(event.target.checked)} />
          終日
        </label>

        {allDay ? null : (
          <div className="entry__times">
            <label className="entry__label" htmlFor="plan-start">
              開始
              <input
                id="plan-start"
                className="entry__input"
                type="time"
                value={startTime}
                onChange={(event) => setStartTime(event.target.value)}
              />
            </label>
            <label className="entry__label" htmlFor="plan-end">
              終了
              <input
                id="plan-end"
                className="entry__input"
                type="time"
                value={endTime}
                onChange={(event) => setEndTime(event.target.value)}
              />
            </label>
          </div>
        )}

        <label className="entry__label" htmlFor="plan-description">
          詳細
        </label>
        <input
          id="plan-description"
          className="entry__input"
          type="text"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="例: 9月から窓口に置いてもらう"
        />

        {message ? (
          <p className="state state--error" role="alert">
            {message}
          </p>
        ) : null}

        <button
          type="submit"
          className="button button--primary button--wide entry__submit"
          disabled={pending || title.trim() === ""}
        >
          追加する
          <Icon name="plus" size={18} />
        </button>
      </form>

      <p className="entry__alt">
        <button type="button" className="entry__link" onClick={() => navigate("/entry")}>
          予定を使わずにPRネタを作る
        </button>
      </p>
    </section>
  );
}
