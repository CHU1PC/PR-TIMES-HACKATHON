const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"] as const;

interface DateParts {
  year: number;
  month: number;
  day: number;
  date: Date;
}

function parseDate(value: string): DateParts | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day, 12, 0, 0);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
  return { year, month, day, date };
}

export function isValidDate(value: string | null | undefined): value is string {
  return typeof value === "string" && parseDate(value) !== null;
}

/** その日1日ぶんの取得範囲。地域時間の 0時から 23:59 まで。 */
export function dayRange(day: string): { timeMin: string; timeMax: string } {
  const [year, month, date] = day.split("-").map(Number);
  const start = new Date(year ?? 0, (month ?? 1) - 1, date ?? 1, 0, 0, 0);
  const end = new Date(year ?? 0, (month ?? 1) - 1, date ?? 1, 23, 59, 0);
  return { timeMin: start.toISOString(), timeMax: end.toISOString() };
}

/** "YYYY-MM-DD" を「2026年9月1日(火)」にする。読めない値はそのまま返す。 */
export function formatDate(value: string): string {
  const parsed = parseDate(value);
  if (!parsed) return value;
  const weekday = WEEKDAYS[parsed.date.getDay()] ?? "";
  return `${parsed.year}年${parsed.month}月${parsed.day}日(${weekday})`;
}
