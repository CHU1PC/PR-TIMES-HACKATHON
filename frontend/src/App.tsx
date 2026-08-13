import type { ReactNode } from "react";
import { AppHeader } from "@/components/AppHeader";
import { EntryPage } from "@/pages/EntryPage";
import { HearingPage } from "@/pages/HearingPage";
import { ProposalPage } from "@/pages/ProposalPage";
import { SparringPage } from "@/pages/SparringPage";
import { Link, useRouteLocation } from "@/router";

function NotFound() {
  return (
    <section className="page">
      <h1 className="page__title">この画面はありません</h1>
      <p className="page__lead">
        <Link to="/" className="entry__link">
          入口にもどる
        </Link>
      </p>
    </section>
  );
}

export default function App() {
  const { path } = useRouteLocation();

  let page: ReactNode = <NotFound />;
  if (path === "/" || path === "") page = <EntryPage />;
  else if (path === "/sparring") page = <SparringPage />;
  else if (path === "/hearing") page = <HearingPage />;
  else if (path === "/proposal") page = <ProposalPage />;

  return (
    <div className="app">
      <AppHeader />
      <main className="app-main">{page}</main>
    </div>
  );
}
