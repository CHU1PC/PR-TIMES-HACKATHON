import { useEffect, useRef, useState } from "react";
import { calendarLoginUrl, calendarStatus } from "@/api";
import { Icon } from "@/components/Icon";
import { Link } from "@/router";
import type { CalendarStatus } from "@/types";

interface AppHeaderProps {
  currentPath: string;
}

export function AppHeader({ currentPath }: AppHeaderProps) {
  const isEntry = currentPath === "/entry";
  const [status, setStatus] = useState<CalendarStatus | null>(null);
  const [checked, setChecked] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;

    void calendarStatus(controller.signal).then((result) => {
      if (controller.signal.aborted) return;
      setChecked(true);
      setStatus(result.ok ? result.data : null);
    });

    return () => {
      controller.abort();
    };
  }, []);

  // 連携済みなら出さない。未設定と分かっているときも, 押しても 503 なので出さない
  const showLogin = checked && !status?.connected && status?.configured !== false;

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <Link to="/" className="app-header__brand" aria-label="PR Generator ホーム">
          <img src="/favicon.svg" alt="" />
          <span>PR Generator</span>
        </Link>

        <p className="app-header__status">
          <span aria-hidden="true" />
          AIと一緒にPRネタを整理
        </p>

        {showLogin ? (
          <a href={calendarLoginUrl()} className="app-header__action app-header__action--secondary">
            <Icon name="calendar" size={19} />
            <span>Googleでログイン</span>
          </a>
        ) : null}

        {isEntry ? (
          <Link to="/" className="app-header__action app-header__action--secondary">
            <Icon name="arrow-left" size={19} />
            <span>ホームへ戻る</span>
          </Link>
        ) : (
          <Link to="/entry" className="app-header__action">
            <Icon name="plus" size={19} />
            <span>新しいPRネタを作る</span>
          </Link>
        )}
      </div>
    </header>
  );
}
