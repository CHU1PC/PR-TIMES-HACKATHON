import { Icon } from "@/components/Icon";
import { Link } from "@/router";

interface AppHeaderProps {
  currentPath: string;
}

export function AppHeader({ currentPath }: AppHeaderProps) {
  const isEntry = currentPath === "/entry";

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
