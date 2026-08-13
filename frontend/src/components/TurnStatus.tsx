import type { ApiFailure } from "@/api";

const PENDING_TEXT = "送信中です。返事を待っています…";

interface TurnStatusProps {
  pending: boolean;
  failure: ApiFailure | null;
  /** 聞き終わったときに読み上げる文言。途中は null */
  completed: string | null;
  onRetry: () => void;
}

/** 画面が要約に入れ替わったことも伝える、常設の live region。 */
export function TurnStatus({ pending, failure, completed, onRetry }: TurnStatusProps) {
  return (
    <>
      <p className="state" role="status" aria-live="polite">
        {pending ? PENDING_TEXT : (completed ?? "")}
      </p>
      {failure ? (
        <div className="state state--error" role="alert">
          <p className="state__message">{failure.message}</p>
          <button type="button" className="button" onClick={onRetry} disabled={pending}>
            もう一度送る
          </button>
        </div>
      ) : null}
    </>
  );
}
