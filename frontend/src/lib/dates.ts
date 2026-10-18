import { addDays, format, parseISO, startOfWeek } from "date-fns";

/** Local calendar date as YYYY-MM-DD (never via toISOString, which is UTC). */
export function toISODate(d: Date): string {
  return format(d, "yyyy-MM-dd");
}

export function fromISODate(s: string): Date {
  return parseISO(s);
}

export function todayISO(): string {
  return toISODate(new Date());
}

export function weekStart(d: Date, weekStartsOn: 0 | 1 = 1): Date {
  return startOfWeek(d, { weekStartsOn });
}

export function weekDays(start: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => addDays(start, i));
}

export function prettyDate(iso: string): string {
  return format(parseISO(iso), "EEE d MMM");
}

export function relativeDay(iso: string): string {
  const today = todayISO();
  if (iso === today) return "Today";
  if (iso === toISODate(addDays(new Date(), 1))) return "Tomorrow";
  if (iso === toISODate(addDays(new Date(), -1))) return "Yesterday";
  return format(parseISO(iso), "EEEE d MMM");
}

export const WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
