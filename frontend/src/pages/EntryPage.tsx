import { useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { loadHearing, loadSparring } from "@/lib/session";
import { Link, navigate } from "@/router";

const steps = [
  {
    number: "01",
    icon: "plus" as const,
    title: "予定を1行で入力",
    description: "決まっている範囲だけで大丈夫です。まずはやることを教えてください。",
  },
  {
    number: "02",
    icon: "message" as const,
    title: "AIと詳細を整理",
    description: "質問に1つずつ答えながら、PRで伝わる取り組みの内容に整えます。",
  },
  {
    number: "03",
    icon: "check" as const,
    title: "PRネタが完成",
    description: "決まった内容を一覧で確認し、そのまま次の準備へ進めます。",
  },
];

export function EntryPage() {
  const [title, setTitle] = useState("");
  const [saved] = useState(() => ({ sparring: loadSparring(), hearing: loadHearing() }));

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    navigate(`/sparring?title=${encodeURIComponent(trimmed)}`);
  };

  return (
    <section className="page home-page">
      <header className="home-hero">
        <p className="home-hero__eyebrow">
          <Icon name="sparkles" size={17} />
          PRアイデアを形にする
        </p>
        <h1 className="home-hero__title">ホーム</h1>
        <p className="home-hero__lead">これからの予定を、届きやすいPRネタへ。AIと一緒に内容を整理しましょう。</p>
      </header>

      <div className="home-actions">
        <form id="new-plan" className="entry entry--dashboard" onSubmit={handleSubmit}>
          <div className="entry__heading">
            <span className="entry__heading-icon">
              <Icon name="sparkles" size={21} />
            </span>
            <div>
              <p className="entry__kicker">NEW PR IDEA</p>
              <h2 className="entry__title">新しいPRネタを作る</h2>
            </div>
          </div>

          <p className="entry__description">これからやることを1行で入力してください。詳しい中身は、このあと一緒に決めていきます。</p>

          <label className="entry__label" htmlFor="entry-title">
            これからやること
          </label>
          <input
            id="entry-title"
            className="entry__input"
            type="text"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="例：9月から郵便局の窓口で商品を取り扱ってもらう"
          />
          <button type="submit" className="button button--primary button--wide entry__submit" disabled={title.trim() === ""}>
            この予定で進む
            <Icon name="arrow-right" size={18} />
          </button>
        </form>

        <aside className="idea-search">
          <div className="idea-search__art" aria-hidden="true">
            <span className="idea-search__orb idea-search__orb--one" />
            <span className="idea-search__orb idea-search__orb--two" />
            <Icon name="lightbulb" size={42} />
          </div>
          <p className="idea-search__kicker">NO IDEA YET?</p>
          <h2 className="idea-search__title">予定がまだ決まっていなくても大丈夫</h2>
          <p className="idea-search__description">すでに取り組んでいることから、PRにできそうな予定をAIと探せます。</p>
          <Link to="/hearing" className="idea-search__link">
            予定を一緒に探す
            <Icon name="arrow-right" size={17} />
          </Link>
        </aside>
      </div>

      <section className="workflow" aria-labelledby="workflow-title">
        <div className="section-heading">
          <div>
            <p className="section-heading__kicker">HOW IT WORKS</p>
            <h2 id="workflow-title" className="section-heading__title">PRネタづくりの流れ</h2>
          </div>
          <p>入力から完成まで、質問に答えるだけで進みます。</p>
        </div>

        <ol className="workflow__list">
          {steps.map((step) => (
            <li key={step.number} className="workflow__item">
              <span className="workflow__number">{step.number}</span>
              <span className="workflow__icon">
                <Icon name={step.icon} size={22} />
              </span>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </li>
          ))}
        </ol>
      </section>

      {saved.sparring || saved.hearing ? (
        <section className="resume resume--dashboard">
          <div className="section-heading">
            <div>
              <p className="section-heading__kicker">RECENT</p>
              <h2 className="section-heading__title">続きから</h2>
            </div>
            <p>前回保存した内容から再開できます。</p>
          </div>
          <ul className="resume__list">
            {saved.sparring ? (
              <li>
                <Link to={`/sparring?title=${encodeURIComponent(saved.sparring.title)}`} className="resume__item">
                  <span className="resume__item-icon">
                    <Icon name="message" size={19} />
                  </span>
                  <span className="resume__item-copy">
                    <strong>{saved.sparring.title}</strong>
                    <small>PRネタの詳細を整理中</small>
                  </span>
                  <Icon name="arrow-right" size={18} />
                </Link>
              </li>
            ) : null}
            {saved.hearing ? (
              <li>
                <Link to="/hearing" className="resume__item">
                  <span className="resume__item-icon">
                    <Icon name="search" size={19} />
                  </span>
                  <span className="resume__item-copy">
                    <strong>予定を探すヒアリング</strong>
                    <small>前回の聞き取りの途中</small>
                  </span>
                  <Icon name="arrow-right" size={18} />
                </Link>
              </li>
            ) : null}
          </ul>
        </section>
      ) : null}

      <aside className="home-tip">
        <span className="home-tip__icon">
          <Icon name="lightbulb" size={24} />
        </span>
        <div className="home-tip__copy">
          <h2>届きやすいPRのコツ</h2>
          <p>市区町村名を1つ入れると、その地域の経済新聞や地方紙に内容が伝わりやすくなります。</p>
        </div>
        <span className="home-tip__badge">
          <Icon name="location" size={16} />
          場所を具体的に
        </span>
      </aside>
    </section>
  );
}
