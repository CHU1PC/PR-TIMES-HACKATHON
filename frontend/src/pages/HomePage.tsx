import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { calendarEvents, calendarStatus } from "@/api";
import { Icon } from "@/components/Icon";
import { formatDate } from "@/lib/date";
import { Link } from "@/router";
import type { CalendarEvent } from "@/types";

/** 日セルとランキングに出す1件。Google の予定を画面用に均したもの */
interface DayEvent {
  id: string;
  /** YYYY-MM-DD */
  date: string;
  title: string;
  description: string;
}

interface CalendarDay {
  date: Date;
  key: string;
  isCurrentMonth: boolean;
  isToday: boolean;
}

const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"] as const;

// 1日に何件も入りうる。セルに出すのはここまでで, 残りは件数だけ添える
const EVENTS_PER_DAY = 2;

function toDateKey(date: Date): string {
  const year = String(date.getFullYear());
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** 終日の予定は YYYY-MM-DD で来る。時刻付きだけ地域時間の日付に直す */
function startDateKey(start: string): string {
  if (start.length === 10) return start;
  return toDateKey(new Date(start));
}

function toDayEvent(event: CalendarEvent): DayEvent {
  return {
    id: event.id,
    date: startDateKey(event.start),
    title: event.title,
    description: event.description,
  };
}

function buildCalendarDays(year: number, month: number): CalendarDay[] {
  const firstDay = new Date(year, month, 1, 12, 0, 0);
  const start = new Date(year, month, 1 - firstDay.getDay(), 12, 0, 0);
  const todayKey = toDateKey(new Date());

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(start);
    date.setDate(start.getDate() + index);
    const key = toDateKey(date);
    return {
      date,
      key,
      isCurrentMonth: date.getMonth() === month,
      isToday: key === todayKey,
    };
  });
}

/** 日付を押したらその日の画面へ。予定を選ぶのも足すのもそこでやる */
function dayPath(eventDate: string): string {
  return `/day?date=${encodeURIComponent(eventDate)}`;
}

function entryPath(eventDate: string, title: string): string {
  return `/entry?date=${encodeURIComponent(eventDate)}&title=${encodeURIComponent(title)}`;
}

export function HomePage() {
  const now = new Date();
  const [visibleMonth, setVisibleMonth] = useState(() => ({ year: now.getFullYear(), month: now.getMonth() }));
  const [events, setEvents] = useState<DayEvent[]>([]);

  const controllerRef = useRef<AbortController | null>(null);

  const calendarDays = useMemo(
    () => buildCalendarDays(visibleMonth.year, visibleMonth.month),
    [visibleMonth.year, visibleMonth.month],
  );
  const weeks = useMemo(
    () => Array.from({ length: 6 }, (_, index) => calendarDays.slice(index * 7, index * 7 + 7)),
    [calendarDays],
  );
  const monthLabel = `${String(visibleMonth.year)}年${String(visibleMonth.month + 1)}月`;

  const load = useCallback(async (year: number, month: number) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    const current = await calendarStatus(controller.signal);
    if (controller.signal.aborted) return;
    if (!current.ok) {
      setEvents([]);
      return;
    }

    // 未ログインは予定を出さない。空のカレンダーだけ残す
    if (!current.data.signed_in) {
      setEvents([]);
      return;
    }

    // 前後の月にはみ出す日も枠に出るので, 見えている42日ぶんを引く
    const gridStart = new Date(year, month, 1, 12, 0, 0);
    gridStart.setDate(gridStart.getDate() - gridStart.getDay());
    const gridEnd = new Date(gridStart);
    gridEnd.setDate(gridStart.getDate() + 42);

    const result = await calendarEvents(
      { timeMin: gridStart.toISOString(), timeMax: gridEnd.toISOString() },
      controller.signal,
    );
    if (controller.signal.aborted) return;
    // 401 はセッション切れ。未連携と同じく予定を出さない
    if (!result.ok) {
      setEvents([]);
      return;
    }
    setEvents(result.data.events.map(toDayEvent));
  }, []);

  useEffect(() => {
    void load(visibleMonth.year, visibleMonth.month);

    return () => {
      controllerRef.current?.abort();
    };
  }, [load, visibleMonth.year, visibleMonth.month]);

  const eventsByDate = useMemo(() => {
    const grouped = new Map<string, DayEvent[]>();
    for (const event of events) {
      const sameDay = grouped.get(event.date);
      if (sameDay) sameDay.push(event);
      else grouped.set(event.date, [event]);
    }
    return grouped;
  }, [events]);

  const monthlyRankedEvents = useMemo(() => {
    const monthPrefix = `${String(visibleMonth.year)}-${String(visibleMonth.month + 1).padStart(2, "0")}-`;
    return events.filter((event) => event.date.startsWith(monthPrefix));
  }, [events, visibleMonth.year, visibleMonth.month]);

  const moveMonth = (amount: number) => {
    setVisibleMonth((current) => {
      const next = new Date(current.year, current.month + amount, 1, 12, 0, 0);
      return { year: next.getFullYear(), month: next.getMonth() };
    });
  };

  const returnToToday = () => {
    const today = new Date();
    setVisibleMonth({ year: today.getFullYear(), month: today.getMonth() });
  };

  return (
    <section className="page home-page">
      <header className="home-hero home-hero--dashboard">
        <p className="home-hero__eyebrow">
          <Icon name="sparkles" size={17} />
          PRアイデアを計画する
        </p>
        <h1 className="home-hero__title">ホーム</h1>
        <p className="home-hero__lead">イベントの予定を設定して、反響につながるPRネタを作りましょう。</p>
      </header>

      <div className="home-dashboard-grid">
      <section id="calendar" className="calendar-card" aria-labelledby="calendar-title">
        <div className="calendar-card__header">
          <div>
            <p className="section-heading__kicker">SCHEDULE</p>
            <h2 id="calendar-title" className="calendar-card__title">カレンダー</h2>
          </div>
          <p>日付を選択すると、PRネタの作成を始められます。</p>
        </div>

        <div className="calendar-toolbar">
          <div className="calendar-toolbar__navigation">
            <button type="button" className="calendar-toolbar__icon-button" onClick={() => moveMonth(-1)} aria-label="前の月">
              <Icon name="chevron-left" size={19} />
            </button>
            <button type="button" className="calendar-toolbar__today" onClick={returnToToday}>
              今日
            </button>
            <button type="button" className="calendar-toolbar__icon-button" onClick={() => moveMonth(1)} aria-label="次の月">
              <Icon name="chevron-right" size={19} />
            </button>
          </div>

          <h3 className="calendar-toolbar__month" aria-live="polite">{monthLabel}</h3>

          <div className="calendar-toolbar__view">
            <Icon name="calendar" size={15} />
            月表示
          </div>
        </div>

        <div className="calendar-table-wrap">
          <table className="calendar-table">
            <caption className="sr-only">{monthLabel}のイベントカレンダー</caption>
            <thead>
              <tr>
                {WEEKDAYS.map((weekday, index) => (
                  <th key={weekday} scope="col" className={index === 0 ? "is-sunday" : index === 6 ? "is-saturday" : undefined}>
                    {weekday}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {weeks.map((week, weekIndex) => (
                <tr key={`week-${String(weekIndex)}`}>
                  {week.map((day, weekdayIndex) => {
                    const dayEvents = eventsByDate.get(day.key) ?? [];
                    const shown = dayEvents.slice(0, EVENTS_PER_DAY);
                    const hidden = dayEvents.length - shown.length;
                    const weekendClass = weekdayIndex === 0 ? " is-sunday" : weekdayIndex === 6 ? " is-saturday" : "";
                    return (
                      <td key={day.key} className={!day.isCurrentMonth ? "is-outside" : undefined}>
                        {/* 日付だけ渡す。その日に何件あってもどれを扱うかは入口の画面で選ぶ */}
                        <Link
                          to={dayPath(day.key)}
                          className={`calendar-day${dayEvents.length > 0 ? " has-event" : ""}${day.isToday ? " is-today" : ""}`}
                          aria-label={`${formatDate(day.key)}を選択`}
                          aria-current={day.isToday ? "date" : undefined}
                        >
                          <span className={`calendar-day__number${weekendClass}`}>{day.date.getDate()}</span>
                          {shown.map((event) => (
                            <span key={event.id} className="calendar-event calendar-event--blue">
                              <span aria-hidden="true" />
                              <span className="calendar-event__title">{event.title}</span>
                              <span className="calendar-event__compact" aria-hidden="true">予定</span>
                            </span>
                          ))}
                          {hidden > 0 ? <span className="calendar-event__more">ほか{hidden}件</span> : null}
                        </Link>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section id="ranking" className="ranking-card" aria-labelledby="ranking-title">
        <div className="ranking-card__header">
          <div>
            <p className="section-heading__kicker">PR RANKING</p>
            <h2 id="ranking-title" className="ranking-card__title">{monthLabel}のPRネタランキング</h2>
          </div>
          <span className="ranking-card__sample">おすすめ順</span>
        </div>

        <ol className="ranking-list">
          {monthlyRankedEvents.map((event, index) => (
            <li key={event.id} className="ranking-list__row">
              <Link to={entryPath(event.date, event.title)} className="ranking-item" aria-label={`${event.title}でPRネタを作る`}>
                <span className={`ranking-item__rank ranking-item__rank--${String(index + 1)}`}>{index + 1}</span>
                <span className="ranking-item__visual ranking-item__visual--blue">
                  <Icon name="calendar" size={27} />
                </span>
                <div className="ranking-item__content">
                  <div className="ranking-item__title-line">
                    <h3>{event.title}</h3>
                    <span>{formatDate(event.date).replace(/^\d{4}年/, "")}</span>
                  </div>
                  <p>{event.description}</p>
                </div>
              </Link>
            </li>
          ))}
          {monthlyRankedEvents.length === 0 ? (
            <li className="ranking-list__empty">この月にはランキング対象の予定がありません。</li>
          ) : null}
        </ol>
      </section>
      </div>

    </section>
  );
}
