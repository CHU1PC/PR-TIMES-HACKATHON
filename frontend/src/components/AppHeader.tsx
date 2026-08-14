import { useEffect, useRef, useState, type FormEvent } from "react";
import { calendarDisconnect, calendarLoginUrl, calendarStatus, demoLogin, logout } from "@/api";
import { Icon } from "@/components/Icon";
import { Link } from "@/router";
import type { CalendarStatus } from "@/types";

interface AppHeaderProps {
  currentPath: string;
}

export function AppHeader({ currentPath }: AppHeaderProps) {
  const isHome = currentPath === "/" || currentPath === "";
  const [status, setStatus] = useState<CalendarStatus | null>(null);
  const [checked, setChecked] = useState(false);
  const [name, setName] = useState("");
  const [pending, setPending] = useState(false);
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

  const handleDemoLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    const result = await demoLogin(name);
    setPending(false);
    // 予定はページ全体で読み直す必要があるので, 素直に入れ直す
    if (result.ok) window.location.assign("/");
  };

  const handleLogout = async () => {
    if (pending) return;
    setPending(true);
    await logout();
    setPending(false);
    // 予定を持ったままの画面が残らないよう, 入口から読み直す
    window.location.assign("/");
  };

  const handleDisconnect = async () => {
    if (pending) return;
    setPending(true);
    await calendarDisconnect();
    setPending(false);
    window.location.assign("/");
  };

  const signedIn = status?.signed_in === true;
  // 未設定と分かっているときは出さない。押しても 503 になる
  const showGoogleLogin = checked && !signedIn && status?.configured !== false;
  const showDemoLogin = checked && !signedIn && status?.demo === true;

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

        {showDemoLogin ? (
          <form className="demo-login" onSubmit={handleDemoLogin}>
            <label className="sr-only" htmlFor="demo-name">
              デモで使う名前
            </label>
            <input
              id="demo-name"
              className="demo-login__input"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="デモユーザー"
              disabled={pending}
            />
            <button type="submit" className="button button--small" disabled={pending}>
              デモで入る
            </button>
          </form>
        ) : null}

        {showGoogleLogin ? (
          <a href={calendarLoginUrl()} className="app-header__action app-header__action--secondary">
            <Icon name="calendar" size={19} />
            <span>Googleでログイン</span>
          </a>
        ) : null}

        {status?.connected === true ? (
          <button
            type="button"
            className="app-header__action app-header__action--secondary"
            onClick={() => void handleDisconnect()}
            disabled={pending}
          >
            <Icon name="calendar" size={19} />
            <span>Google連携を解除</span>
          </button>
        ) : null}

        {signedIn ? (
          <button
            type="button"
            className="app-header__action app-header__action--secondary"
            onClick={() => void handleLogout()}
            disabled={pending}
          >
            <Icon name="arrow-right" size={19} />
            <span>ログアウト</span>
          </button>
        ) : null}

        {isHome ? (
          <Link to="/day" className="app-header__action">
            <Icon name="plus" size={19} />
            <span>新しいイベントをカレンダーに追加する</span>
          </Link>
        ) : (
          <Link to="/" className="app-header__action app-header__action--secondary">
            <Icon name="arrow-left" size={19} />
            <span>ホームへ戻る</span>
          </Link>
        )}
      </div>
    </header>
  );
}
