const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"] as const;

/** "YYYY-MM-DD" を「2026年9月1日（火）」にする。読めない値はそのまま返す。 */
export function formatDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  // 時差でずれないようローカル正午で解釈する
  const date = new Date(year, month - 1, day, 12, 0, 0);
  if (Number.isNaN(date.getTime())) return value;
  const weekday = WEEKDAYS[date.getDay()] ?? "";
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日（${weekday}）`;
}
