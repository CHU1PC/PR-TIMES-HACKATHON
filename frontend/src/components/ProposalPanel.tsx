import type { ApiFailure } from "@/api";
import { Icon } from "@/components/Icon";
import { TurnStatus } from "@/components/TurnStatus";
import type { ProposalCase, ProposalResponse } from "@/types";

function placeOf(item: ProposalCase): string {
  return `${item.prefecture ?? ""}${item.city ?? ""}` || "地域の記載なし";
}

// 他社を名指ししない。出すのは取り組みの素性だけで, やり方そのものは提案文が持つ
function CaseCard({ item }: { item: ProposalCase }) {
  return (
    <li className="evidence">
      <p className="evidence__title">
        {item.business_category ?? "業種の記載なし"} / {item.release_type ?? "種別の記載なし"}
      </p>
      <p className="evidence__meta">
        {placeOf(item)} / {item.published_on}
      </p>
      {item.media.length > 0 ? <p className="evidence__media">拾った媒体: {item.media.join("、")}</p> : null}
    </li>
  );
}

interface ProposalPanelProps {
  result: ProposalResponse | null;
  pending: boolean;
  failure: ApiFailure | null;
  /** 決めた内容が変わって, いまの提案が古くなっているか */
  stale: boolean;
  onReload: () => void;
}

/** 似た事例から足せることを, 同じ画面に出す。 */
export function ProposalPanel({ result, pending, failure, stale, onReload }: ProposalPanelProps) {
  return (
    <section className="entry entry--dashboard proposal-panel">
      <div className="entry__heading">
        <span className="entry__heading-icon">
          <Icon name="sparkles" size={21} />
        </span>
        <div>
          <p className="entry__kicker">ADVICE</p>
          <h2 className="entry__title">似た事例から, 足せること</h2>
        </div>
      </div>

      <p className="entry__description">同じような取り組みで実際に配信された事例から挙げました。</p>

      <TurnStatus pending={pending} failure={failure} completed={null} onRetry={onReload} />

      {stale ? (
        <p className="resume-note">
          決めた内容が変わりました。
          <button type="button" className="button button--small" onClick={onReload} disabled={pending}>
            提案を作り直す
          </button>
        </p>
      ) : null}

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
                <h3 className="suggestion__action">{suggestion.action}</h3>
                <p className="suggestion__reason">{suggestion.reason}</p>
                {suggestion.cited.length > 0 ? (
                  <details className="suggestion__evidence">
                    <summary>もとにした事例</summary>
                    <ul className="evidence__list">
                      {suggestion.cited.map((index) => {
                        const item = result.cases[index];
                        return item ? <CaseCard key={index} item={item} /> : null;
                      })}
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

      {!result && !pending && !failure ? <p className="state">提案を作っています…</p> : null}
    </section>
  );
}
