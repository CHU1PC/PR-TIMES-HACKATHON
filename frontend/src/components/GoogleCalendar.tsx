import { useCallback, useEffect, useRef, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";

import type { EventClickArg } from "@fullcalendar/core";

import { calendarEvents, calendarLoginUrl, calendarStatus, type ApiFailure } from "@/api";
import type { CalendarEvent, CalendarRange } from "@/types";

/** 先月頭から3ヶ月先の頭まで引く */
function currentRange(): CalendarRange {
  const now = new Date();
  return {
    timeMin: new Date(now.getFullYear(), now.getMonth() - 1, 1).toISOString(),
    timeMax: new Date(now.getFullYear(), now.getMonth() + 3, 1).toISOString(),
  };
}

export function GoogleCalendar() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [failure, setFailure] = useState<ApiFailure | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const startedRef = useRef(false);

  const load = useCallback(async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setFailure(null);

    const status = await calendarStatus(controller.signal);
    if (controller.signal.aborted) return;
    if (!status.ok) {
      if (status.kind !== "cancelled") setFailure(status);
      return;
    }
    setConnected(status.data.connected);
    if (!status.data.connected) return;

    const result = await calendarEvents(currentRange(), controller.signal);
    if (controller.signal.aborted) return;
    if (!result.ok) {
      if (result.kind !== "cancelled") setFailure(result);
      return;
    }
    setConnected(result.data.connected);
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

  if (connected === null) {
    return (
      <section className="calendar">
        <p className="state" role="status" aria-live="polite">
          Googleカレンダーを確認しています…
        </p>
      </section>
    );
  }

  if (!connected) {
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
      <h2 className="calendar__title">Googleカレンダー</h2>

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
              {" ～ "}
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
