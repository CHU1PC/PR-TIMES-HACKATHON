import { useState, type FormEvent } from "react";

// 答えられないときの常設の逃げ道。回答としてそのまま送る
const UNSURE_REPLY = "わからない";

interface ReplyFormProps {
  /** 送信中は入力欄とボタンの両方を止める */
  pending: boolean;
  onSend: (text: string) => void;
}

export function ReplyForm({ pending, onSend }: ReplyFormProps) {
  const [text, setText] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = text.trim();
    if (pending || !trimmed) return;
    setText("");
    onSend(trimmed);
  };

  const handleUnsure = () => {
    if (pending) return;
    setText("");
    onSend(UNSURE_REPLY);
  };

  return (
    <form className="reply" onSubmit={handleSubmit}>
      <label className="reply__label" htmlFor="reply-text">
        返答
      </label>
      <textarea
        id="reply-text"
        className="reply__input"
        rows={3}
        value={text}
        disabled={pending}
        onChange={(event) => setText(event.target.value)}
        placeholder="思いつくままで構いません"
      />
      <div className="reply__actions">
        <button type="submit" className="button button--primary" disabled={pending || text.trim() === ""}>
          {pending ? "送信中…" : "送る"}
        </button>
        <button type="button" className="button" disabled={pending} onClick={handleUnsure}>
          わからない・あとで
        </button>
      </div>
    </form>
  );
}
