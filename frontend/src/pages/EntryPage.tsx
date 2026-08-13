import { useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { formatDate, isValidDate } from "@/lib/date";
import { loadHearing, loadSparring } from "@/lib/session";
import { GoogleCalendar } from "@/components/GoogleCalendar";
import { Link, navigate, useQueryParam } from "@/router";

function sparringPath(title: string, startDate: string | null): string {
  const params = new URLSearchParams({ title });
  if (startDate) params.set("date", startDate);
  return `/sparring?${params.toString()}`;
}

export function EntryPage() {
  const dateParam = useQueryParam("date");
  const titleParam = useQueryParam("title");
  const selectedDate = isValidDate(dateParam) ? dateParam : null;
  const [title, setTitle] = useState(() => titleParam?.trim() ?? "");
  const [saved] = useState(() => ({ sparring: loadSparring(), hearing: loadHearing() }));

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    navigate(sparringPath(trimmed, selectedDate));
  };

  const hearingPath = selectedDate ? `/hearing?date=${encodeURIComponent(selectedDate)}` : "/hearing";

  return (
    <section className="page home-page creation-page">
      <header className="home-hero creation-hero">
        <Link to="/" className="creation-hero__back">
          <Icon name="arrow-left" size={16} />
          ホームに戻る
        </Link>
        <p className="home-hero__eyebrow">
          <Icon name="sparkles" size={17} />
          PRアイデアを形にする
        </p>
        <h1 className="home-hero__title">{selectedDate ? `${formatDate(selectedDate)}のPRネタを作る` : "新しいPRネタを作る"}</h1>
        <p className="home-hero__lead">これからの予定を、届きやすいPRネタへ。AIと一緒に内容を整理しましょう。</p>
        {selectedDate ? (
          <p className="creation-hero__date">
            <Icon name="calendar" size={16} />
            選択日：{formatDate(selectedDate)}
          </p>
        ) : null}
      </header>

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
      <GoogleCalendar />

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
                <Link to={sparringPath(saved.sparring.title, saved.sparring.draft.start_date)} className="resume__item">
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
                <Link to={hearingPath} className="resume__item">
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

    </section>
  );
}
