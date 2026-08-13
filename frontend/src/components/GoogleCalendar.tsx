import { useEffect, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";

import type { EventClickArg } from "@fullcalendar/core";

type CalendarEvent = {
  id: string;
  title: string;
  description: string;
  location: string;
  start: string;
  end: string;
  htmlLink: string | null;
};

export function GoogleCalendar() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [selectedEvent, setSelectedEvent] =
    useState<CalendarEvent | null>(null);

  useEffect(() => {
    checkConnection();
  }, []);

  const checkConnection = async () => {
    const response = await fetch(
      "http://localhost:8000/api/calendar/status"
    );

    const data = await response.json();

    setConnected(data.connected);

    if (data.connected) {
      loadEvents();
    }
  };

  const loadEvents = async () => {
    const now = new Date();

    const timeMin = new Date(
      now.getFullYear(),
      now.getMonth() - 1,
      1
    ).toISOString();

    const timeMax = new Date(
      now.getFullYear(),
      now.getMonth() + 3,
      1
    ).toISOString();

    const response = await fetch(
      "http://localhost:8000/api/calendar/events",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          timeMin,
          timeMax,
        }),
      }
    );

    const data = await response.json();

    setEvents(data.events ?? []);
  };

  const handleEventClick = (
    info: EventClickArg
  ) => {
    const event = events.find(
      (event) => event.id === info.event.id
    );

    if (event) {
      setSelectedEvent(event);
    }
  };

  if (connected === null) {
    return (
      <section className="calendar">
        <p>Googleカレンダーを確認しています...</p>
      </section>
    );
  }

  if (!connected) {
    return (
      <section className="calendar">
        <h2>Googleカレンダー</h2>

        <p>
          Googleカレンダーと連携すると、
          予定からPRネタを探せます。
        </p>

        <a
          href="http://localhost:8000/api/calendar/login"
          className="button button--primary"
        >
          Googleカレンダーと連携する
        </a>
      </section>
    );
  }

  return (
    <section className="calendar">
      <h2 className="calendar__title">
        Googleカレンダー
      </h2>

      <div className="calendar__body">
        <FullCalendar
          plugins={[
            dayGridPlugin,
            interactionPlugin,
          ]}
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

      {selectedEvent && (
        <div className="calendar-detail">
          <div className="calendar-detail__header">
            <h3>{selectedEvent.title}</h3>

            <button
              type="button"
              onClick={() => setSelectedEvent(null)}
              className="calendar-detail__close"
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

            {selectedEvent.location && (
              <p>
                <strong>場所</strong>
                <br />
                {selectedEvent.location}
              </p>
            )}

            {selectedEvent.description && (
              <p>
                <strong>説明</strong>
                <br />
                {selectedEvent.description}
              </p>
            )}

            {selectedEvent.htmlLink && (
              <a
                href={selectedEvent.htmlLink}
                target="_blank"
                rel="noopener noreferrer"
                className="button button--primary"
              >
                Googleカレンダーで開く
              </a>
            )}
          </div>
        </div>
      )}
    </section>
  );
}


function formatDate(value: string) {
  const date = new Date(value);

  return new Intl.DateTimeFormat(
    "ja-JP",
    {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
    }
  ).format(date);
}