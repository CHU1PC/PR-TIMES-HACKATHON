import { useMemo, useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { formatDate } from "@/lib/date";
import { Link } from "@/router";

type EventTone = "blue" | "green" | "orange" | "purple";

interface CalendarEvent {
  id: string;
  date: string;
  title: string;
  description: string;
  tone: EventTone;
  icon: IconName;
}

interface CalendarDay {
  date: Date;
  key: string;
  isCurrentMonth: boolean;
  isToday: boolean;
}

const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"] as const;

const events: CalendarEvent[] = [
  {
    id: "conference",
    date: "2026-08-20",
    title: "カンファレンス開催",
    description: "最新テクノロジーをテーマにしたカンファレンスを開催。業界の注目が集まる企画です。",
    tone: "purple",
    icon: "message",
  },
  {
    id: "product",
    date: "2026-08-05",
    title: "新商品発表会",
    description: "新商品の特徴と利用シーンを発表し、ユーザーへ魅力を分かりやすく伝えます。",
    tone: "purple",
    icon: "sparkles",
  },
  {
    id: "exhibition",
    date: "2026-08-10",
    title: "展示会出展",
    description: "主要展示会へ出展し、幅広い業界関係者との新しい接点を作ります。",
    tone: "green",
    icon: "ranking",
  },
  {
    id: "campaign",
    date: "2026-08-25",
    title: "キャンペーン開始",
    description: "期間限定キャンペーンの開始を知らせ、内容と期間を明確に伝えます。",
    tone: "orange",
    icon: "sparkles",
  },
  {
    id: "release",
    date: "2026-08-15",
    title: "プレスリリース配信",
    description: "新たな取り組みや実績について、プレスリリースを配信します。",
    tone: "blue",
    icon: "message",
  },
];

const eventsByDate = new Map(events.map((event) => [event.date, event]));

function toDateKey(date: Date): string {
  const year = String(date.getFullYear());
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
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

function entryPath(eventDate: string, title?: string): string {
  const params = new URLSearchParams({ date: eventDate });
  if (title) params.set("title", title);
  return `/entry?${params.toString()}`;
}

export function HomePage() {
  const now = new Date();
  const [visibleMonth, setVisibleMonth] = useState(() => ({ year: now.getFullYear(), month: now.getMonth() }));
  const calendarDays = useMemo(
    () => buildCalendarDays(visibleMonth.year, visibleMonth.month),
    [visibleMonth.year, visibleMonth.month],
  );
  const weeks = useMemo(
    () => Array.from({ length: 6 }, (_, index) => calendarDays.slice(index * 7, index * 7 + 7)),
    [calendarDays],
  );
  const monthLabel = `${String(visibleMonth.year)}年${String(visibleMonth.month + 1)}月`;
  const monthlyRankedEvents = useMemo(() => {
    const monthPrefix = `${String(visibleMonth.year)}-${String(visibleMonth.month + 1).padStart(2, "0")}-`;
    return events
      .filter((event) => event.date.startsWith(monthPrefix));
  }, [visibleMonth.year, visibleMonth.month]);

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
                    const event = eventsByDate.get(day.key);
                    const dayContent = (
                      <>
                        <span className={`calendar-day__number${weekdayIndex === 0 ? " is-sunday" : weekdayIndex === 6 ? " is-saturday" : ""}`}>
                          {day.date.getDate()}
                        </span>
                        {event ? (
                          <span className={`calendar-event calendar-event--${event.tone}`}>
                            <span aria-hidden="true" />
                            <span className="calendar-event__title">{event.title}</span>
                            <span className="calendar-event__compact" aria-hidden="true">予定</span>
                          </span>
                        ) : null}
                      </>
                    );
                    return (
                      <td key={day.key} className={!day.isCurrentMonth ? "is-outside" : undefined}>
                        {event ? (
                          <Link
                            to={entryPath(day.key, event.title)}
                            className={`calendar-day has-event${day.isToday ? " is-today" : ""}`}
                            aria-label={`${formatDate(day.key)}、${event.title}を選択`}
                            aria-current={day.isToday ? "date" : undefined}
                          >
                            {dayContent}
                          </Link>
                        ) : (
                          <div className={`calendar-day calendar-day--empty${day.isToday ? " is-today" : ""}`} aria-current={day.isToday ? "date" : undefined}>
                            {dayContent}
                          </div>
                        )}
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
                <span className={`ranking-item__visual ranking-item__visual--${event.tone}`}>
                  <Icon name={event.icon} size={27} />
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
