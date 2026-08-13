import { useCallback, useEffect, useRef, useState } from "react";
import { fetchProposal, type ApiFailure } from "@/api";
import { TurnStatus } from "@/components/TurnStatus";
import { loadSparring, type SparringSession } from "@/lib/session";
import { Link, navigate } from "@/router";
import type { ProposalCase, ProposalResponse } from "@/types";

function placeOf(item: ProposalCase): string {
  return `${item.prefecture ?? ""}${item.city ?? ""}` || "地域の記載なし";
}

function CaseCard({ item }: { item: ProposalCase }) {
  return (
    <li className="evidence">
      <p className="evidence__title">{item.title}</p>
      <p className="evidence__meta">
        {item.company_name ?? "企業名なし"} / {placeOf(item)} / {item.published_on}
      </p>
      {item.media.length > 0 ? <p className="evidence__media">拾った媒体: {item.media.join("、")}</p> : null}
    </li>
  );
}

export function ProposalPage() {
  const [session, setSession] = useState<SparringSession | null>(null);
  const [result, setResult] = useState<ProposalResponse | null>(null);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<ApiFailure | null>(null);

  const controllerRef = useRef<AbortController | null>(null);
  const startedRef = useRef(false);

  const load = useCallback(async (target: SparringSession) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setPending(true);
    setFailure(null);

    const response = await fetchProposal({ draft: target.draft }, controller.signal);
    if (controller.signal.aborted) {
      if (controllerRef.current === controller) setPending(false);
      return;
    }
    setPending(false);
    if (!response.ok) {
      if (response.kind !== "cancelled") setFailure(response);
      return;
    }
    setResult(response.data);
  }, []);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    const saved = loadSparring();
    // 壁打ちを終えていない状態で直接開かれたら入口へ戻す
    if (!saved || !saved.ready) {
      navigate("/", { replace: true });
      return;
    }
    setSession(saved);
    void load(saved);

    return () => {
      controllerRef.current?.abort();
      startedRef.current = false;
    };
  }, [load]);

  if (!session) {
    return (
      <p className="state" role="status" aria-live="polite">
        読み込んでいます…
      </p>
    );
  }

  return (
    <section className="page proposal">
      <h1 className="page__title">{session.title}</h1>
      <p className="page__lead">同じような取り組みで実際に配信された事例から, 足せることを挙げました。</p>

      <TurnStatus pending={pending} failure={failure} completed={null} onRetry={() => void load(session)} />

      {result ? (
        <>
          {result.media.length > 0 ? (
            <p className="proposal__media">
              こうした取り組みを拾っていたのは <strong>{result.media.join("、")}</strong> などです。
            </p>
          ) : null}

          <ol className="proposal__list">
            {result.suggestions.map((suggestion) => (
              <li key={suggestion.action} className="suggestion">
                <h2 className="suggestion__action">{suggestion.action}</h2>
                <p className="suggestion__reason">{suggestion.reason}</p>
                {suggestion.cited.length > 0 ? (
                  <details className="suggestion__evidence">
                    <summary>もとにした事例</summary>
                    <ul className="evidence__list">
                      {suggestion.cited
                        .map((index) => result.cases[index])
                        .filter((item) => item !== undefined)
                        .map((item) => (
                          <CaseCard key={`${item.company_id}-${item.release_id}`} item={item} />
                        ))}
                    </ul>
                  </details>
                ) : null}
              </li>
            ))}
          </ol>

          {result.suggestions.length === 0 && !pending ? (
            <p className="state">近い事例が見つかりませんでした。</p>
          ) : null}
        </>
      ) : null}

      <p className="proposal__back">
        <Link to="/" className="entry__link">
          別の予定を入れる
        </Link>
      </p>
    </section>
  );
}
