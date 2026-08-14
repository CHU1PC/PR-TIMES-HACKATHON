import { useEffect, useRef } from "react";

interface AskPanelProps {
  question: string;
  hint: string | null;
}

/** 質問と例示。差し替わるたびに読み上げさせ、フォーカスも移す。 */
export function AskPanel({ question, hint }: AskPanelProps) {
  const questionRef = useRef<HTMLParagraphElement | null>(null);

  useEffect(() => {
    questionRef.current?.focus();
  }, [question]);

  return (
    <section className="ask" aria-live="polite">
      <p className="ask__question" ref={questionRef} tabIndex={-1}>
        {question}
      </p>
      {hint ? <p className="ask__hint">{hint}</p> : null}
    </section>
  );
}
