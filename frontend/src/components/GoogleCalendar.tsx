import { useCallback, useEffect, useRef, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";

import type { EventClickArg } from "@fullcalendar/core";

import { calendarDisconnect, calendarEvents, calendarLoginUrl, calendarStatus, type ApiFailure } from "@/api";
import type { CalendarEvent, CalendarRange, CalendarStatus } from "@/types";

/** 先月頭から3ヶ月先の頭まで引く */
function currentRange(): CalendarRange {
  const now = new Date();
  return {
    timeMin: new Date(now.getFullYear(), now.getMonth() - 1, 1).toISOString(),
    timeMax: new Date(now.getFullYear(), now.getMonth() + 3, 1).toISOString(),
  };
}

export function GoogleCalendar() {
  const [status, setStatus] = useState<CalendarStatus | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [failure, setFailure] = useState<ApiFailure | null>(null);
  const [disconnecting, setDisconnecting] = useState(false);

  const controllerRef = useRef<AbortController | null>(null);
  const startedRef = useRef(false);

  const load = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setFailure(null);

    const current = await calendarStatus(controller.signal);
    if (controller.signal.aborted) return;
    if (!current.ok) {
      if (current.kind !== "cancelled") setFailure(current);
      return;
    }
    setStatus(current.data);
    if (!current.data.configured || !current.data.connected) return;

    const result = await calendarEvents(currentRange(), controller.signal);
    if (controller.signal.aborted) return;
    if (!result.ok) {
      // セッション切れは異常ではなく未連携。赤く出さずに連携ボタンへ戻す
      if (result.kind === "unauthorized") setStatus({ ...current.data, connected: false });
      else if (result.kind !== "cancelled") setFailure(result);
      return;
    }
    setStatus({ ...current.data, connected: result.data.connected });
    setEvents(result.data.events);
  }, []);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void load();

    return () => {
      controllerRef.current?.abort();
      startedRef.current = false;
    };
  }, [load]);

  const handleEventClick = (info: EventClickArg) => {
    const event = events.find((event) => event.id === info.event.id);
    if (event) setSelectedEvent(event);
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    const result = await calendarDisconnect();
    setDisconnecting(false);
    // 401 はセッションが既に切れているだけ。解除済みとして扱う
    if (!result.ok && result.kind !== "unauthorized" && result.kind !== "cancelled") {
      setFailure(result);
      return;
    }
    setSelectedEvent(null);
    setEvents([]);
    void load();
  };

  if (failure) {
    return (
      <section className="calendar">
        <h2 className="calendar__title">Googleカレンダー</h2>
        <div className="state state--error" role="alert">
          <p className="state__message">{failure.message}</p>
          <button type="button" className="button" onClick={() => void load()}>
            もう一度試す
          </button>
        </div>
      </section>
    );
  }

  // 確認中と未設定は何も描かない。未設定は本番の既定なので, 出すと入口に説明の要る枠が居座る
  if (status === null || !status.configured) return null;

  if (!status.connected) {
    return (
      <section className="calendar">
        <h2 className="calendar__title">Googleカレンダー</h2>
        <p>Googleカレンダーと連携すると、予定からPRネタを探せます。</p>
        <a href={calendarLoginUrl()} className="button button--primary">
          Googleカレンダーと連携する
        </a>
      </section>
    );
  }

  return (
    <section className="calendar">
      <div className="calendar__head">
        <h2 className="calendar__title">Googleカレンダー</h2>
        <button type="button" className="button button--small" onClick={handleDisconnect} disabled={disconnecting}>
          連携を解除
        </button>
      </div>

      <div className="calendar__body">
        <FullCalendar
          plugins={[dayGridPlugin, interactionPlugin]}
          initialView="dayGridMonth"
          locale="ja"
          events={events.map((event) => ({
            id: event.id,
            title: event.title,
            start: event.start,
            end: event.end,
          }))}
          eventClick={handleEventClick}
          height="auto"
        />
      </div>

      {selectedEvent ? (
        <div className="calendar-detail">
          <div className="calendar-detail__header">
            <h3>{selectedEvent.title}</h3>
            <button
              type="button"
              onClick={() => setSelectedEvent(null)}
              className="calendar-detail__close"
              aria-label="閉じる"
            >
              ×
            </button>
          </div>

          <div className="calendar-detail__content">
            <p>
              <strong>日時</strong>
              <br />
              {formatDate(selectedEvent.start)}
              {" ~ "}
              {formatDate(selectedEvent.end)}
            </p>

            {selectedEvent.location ? (
              <p>
                <strong>場所</strong>
                <br />
                {selectedEvent.location}
              </p>
            ) : null}

            {selectedEvent.description ? (
              <p>
                <strong>説明</strong>
                <br />
                {selectedEvent.description}
              </p>
            ) : null}

            {selectedEvent.htmlLink ? (
              <a
                href={selectedEvent.htmlLink}
                target="_blank"
                rel="noopener noreferrer"
                className="button button--primary"
              >
                Googleカレンダーで開く
              </a>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("ja-JP", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
