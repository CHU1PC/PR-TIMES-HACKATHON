import type { ApiFailure } from "@/api";

interface TurnStatusProps {
  pending: boolean;
  failure: ApiFailure | null;
  onRetry: () => void;
}

export function TurnStatus({ pending, failure, onRetry }: TurnStatusProps) {
  return (
    <>
      <p className="state" role="status" aria-live="polite">
        {pending ? "送信中です。返事を待っています…" : ""}
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
