import { Icon, type IconName } from "@/components/Icon";
import { Link } from "@/router";

interface AppSidebarProps {
  currentPath: string;
  currentHash: string;
}

interface NavigationItem {
  label: string;
  path: string;
  icon: IconName;
  isActive: (path: string, hash: string) => boolean;
}

const navigationItems: NavigationItem[] = [
  {
    label: "ホーム",
    path: "/",
    icon: "home",
    isActive: (path, hash) => (path === "/" || path === "") && hash !== "#calendar" && hash !== "#ranking",
  },
  {
    label: "カレンダー",
    path: "/#calendar",
    icon: "calendar",
    isActive: (path, hash) => (path === "/" || path === "") && hash === "#calendar",
  },
  {
    label: "ランキング",
    path: "/#ranking",
    icon: "ranking",
    isActive: (path, hash) => (path === "/" || path === "") && hash === "#ranking",
  },
  {
    label: "予定を探す",
    path: "/hearing",
    icon: "search",
    isActive: (path) => path === "/hearing",
  },
];

export function AppSidebar({ currentPath, currentHash }: AppSidebarProps) {
  return (
    <aside className="app-sidebar" aria-label="アプリナビゲーション">
      <Link to="/" className="app-sidebar__brand" aria-label="PR Generator ホーム">
        <img src="/favicon.svg" alt="" className="app-sidebar__logo" />
        <span>PR Generator</span>
      </Link>

      <nav className="app-sidebar__nav" aria-label="メインメニュー">
        <p className="app-sidebar__nav-label">メニュー</p>
        <ul className="app-sidebar__nav-list">
          {navigationItems.map((item) => {
            const active = item.isActive(currentPath, currentHash);
            const ariaCurrent = active ? (item.path.includes("#") ? "location" : "page") : undefined;
            return (
              <li key={item.path}>
                <Link to={item.path} className={`app-sidebar__nav-item${active ? " is-active" : ""}`} aria-current={ariaCurrent}>
                  <Icon name={item.icon} size={19} />
                  <span>{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="app-sidebar__spacer" />

      <p className="app-sidebar__footer">PR TIMES HACKATHON 2026</p>
    </aside>
  );
}
