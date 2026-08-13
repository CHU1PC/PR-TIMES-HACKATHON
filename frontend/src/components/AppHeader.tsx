import { Icon } from "@/components/Icon";
import { Link } from "@/router";

interface AppHeaderProps {
  currentPath: string;
}

export function AppHeader({ currentPath }: AppHeaderProps) {
  const isHome = currentPath === "/" || currentPath === "";

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

        {isHome ? (
          <a href="#new-plan" className="app-header__action">
            <Icon name="plus" size={19} />
            <span>予定を追加</span>
          </a>
        ) : (
          <Link to="/" className="app-header__action">
            <Icon name="plus" size={19} />
            <span>新しい予定</span>
          </Link>
        )}
      </div>
    </header>
  );
}
