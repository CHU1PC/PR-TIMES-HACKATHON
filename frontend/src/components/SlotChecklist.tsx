import type { SlotState } from "@/types";

type SlotStatus = "filled" | "skipped" | "waiting";

const STATUS_TEXT = {
  filled: "入りました",
  skipped: "該当なし",
  waiting: "これから伺います",
} as const satisfies Record<SlotStatus, string>;

// 色だけで区別しないための記号
const STATUS_MARK = {
  filled: "✓",
  skipped: "—",
  waiting: "・",
} as const satisfies Record<SlotStatus, string>;

/** filled と skipped の両方が false のときだけ未回答。 */
function statusOf(slot: SlotState): SlotStatus {
  if (slot.filled) return "filled";
  if (slot.skipped) return "skipped";
  return "waiting";
}

interface SlotChecklistProps {
  slots: SlotState[];
}

export function SlotChecklist({ slots }: SlotChecklistProps) {
  return (
    <section className="checklist" aria-label="聞いていること">
      <h2 className="checklist__title">聞いていること</h2>
      <ul className="checklist__list">
        {slots.map((slot) => {
          const status = statusOf(slot);
          return (
            <li key={slot.code} className="slot" data-code={slot.code} data-state={status} data-tone={slot.tone}>
              <p className="slot__head">
                <span className="slot__mark" aria-hidden="true">
                  {STATUS_MARK[status]}
                </span>
                <span className="slot__label">{slot.label}</span>
              </p>
              <p className="slot__status">{STATUS_TEXT[status]}</p>
              {/* effect はサーバーの文字列をそのまま出す。フロントで因果を足さない */}
              <p className="slot__effect">{slot.effect}</p>
              {slot.tone === "causal" ? <p className="slot__tone">実測で確かめた項目</p> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
