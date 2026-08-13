import { useState, type FormEvent } from "react";
import { loadHearing, loadSparring } from "@/lib/session";
import { Link, navigate } from "@/router";
import { GoogleCalendar } from "@/components/GoogleCalendar";

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
    <section className="page">
      <GoogleCalendar />
      <h1 className="page__title">これからやることを1行で入れてください</h1>
      <p>これからやることを1行で入れてください</p>
      <p className="page__lead">中身はこのあと一緒に決めていきます。決まっているところまでで構いません。</p>

      <form className="entry" onSubmit={handleSubmit}>
        <label className="entry__label" htmlFor="entry-title">
          これからやること
        </label>
        <input
          id="entry-title"
          className="entry__input"
          type="text"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="例: 9月から郵便局の窓口で商品を取り扱ってもらう"
        />
        <button type="submit" className="button button--primary button--wide" disabled={title.trim() === ""}>
          この予定で進む
        </button>
      </form>

      <p className="entry__alt">
        <Link to="/hearing" className="entry__link">
          思いつかない
        </Link>
      </p>

      {saved.sparring || saved.hearing ? (
        <section className="resume">
          <h2 className="resume__title">続きから</h2>
          <ul className="resume__list">
            {saved.sparring ? (
              <li>
                <Link to={`/sparring?title=${encodeURIComponent(saved.sparring.title)}`} className="resume__item">
                  {saved.sparring.title}
                </Link>
              </li>
            ) : null}
            {saved.hearing ? (
              <li>
                <Link to="/hearing" className="resume__item">
                  聞き取りの途中
                </Link>
              </li>
            ) : null}
          </ul>
        </section>
      ) : null}
    </section>
  );
}
