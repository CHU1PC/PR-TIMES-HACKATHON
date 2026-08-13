import type { ReactNode } from "react";
import { AppHeader } from "@/components/AppHeader";
import { AppSidebar } from "@/components/AppSidebar";
import { DayPage } from "@/pages/DayPage";
import { EntryPage } from "@/pages/EntryPage";
import { HearingPage } from "@/pages/HearingPage";
import { ProposalPage } from "@/pages/ProposalPage";
import { HomePage } from "@/pages/HomePage";
import { SparringPage } from "@/pages/SparringPage";
import { Link, useRouteLocation } from "@/router";

function NotFound() {
  return (
    <section className="page">
      <h1 className="page__title">この画面はありません</h1>
      <p className="page__lead">
        <Link to="/" className="entry__link">
          ホームに戻る
        </Link>
      </p>
    </section>
  );
}

export default function App() {
  const { path, search } = useRouteLocation();

  let page: ReactNode = <NotFound />;
  if (path === "/" || path === "") page = <HomePage />;
  else if (path === "/day") page = <DayPage key={search} />;
  else if (path === "/entry") page = <EntryPage key={search} />;
  else if (path === "/sparring") page = <SparringPage />;
  else if (path === "/hearing") page = <HearingPage />;
  else if (path === "/proposal") page = <ProposalPage />;

  return (
    <div className="app">
      <AppSidebar currentPath={path} />
      <div className="app__body">
        <AppHeader currentPath={path} />
        <main className="app-main">{page}</main>
      </div>
    </div>
  );
}
