/**
 * Checking a child's typed answer in a practice task. Kind to the many ways children type numbers:
 * "2,5" and "2.5", "3/4", "1 3/4", "1 500", "1.500" (Slovenian thousands), "12 cm". When a typing could
 * mean two things ("1.500" = 1,5 or 1500), it counts if either is right.
 */
import type { Task } from "./api";

const EPS = 1e-9;

/** Every value a typed number could mean (empty when it isn't a number). */
export function numberCandidates(input: string): number[] {
  let s = input.trim().replace(/[−–]/g, "-").replace(/[  ]/g, " ");
  // Drop a unit or a word after the number: "12 cm", "12cm", "6 €".
  const m = s.match(/^([-+]?\s*\d[\d\s.,/]*?)\s*[^\d\s.,/-]*$/);
  if (!m) return [];
  s = m[1].replace(/\s+/g, " ").trim();
  const sign = s.startsWith("-") ? -1 : 1;
  s = s.replace(/^[-+]\s*/, "");

  let mm = s.match(/^(\d+) (\d+)\/(\d+)$/);
  if (mm) return Number(mm[3]) ? [sign * (Number(mm[1]) + Number(mm[2]) / Number(mm[3]))] : [];
  mm = s.match(/^(\d+)\/(\d+)$/);
  if (mm) return Number(mm[2]) ? [(sign * Number(mm[1])) / Number(mm[2])] : [];
  if (s.includes("/")) return [];

  // Thousands written with spaces: "1 500", "12 000,5".
  if (/^\d{1,3}( \d{3})+([.,]\d+)?$/.test(s)) s = s.replace(/ /g, "");
  if (s.includes(" ")) return [];

  const out = new Set<number>();
  const hasDot = s.includes(".");
  const hasComma = s.includes(",");
  if (hasDot && hasComma) {
    // The separator that comes last is the decimal one: "1.234,5" or "1,234.5".
    const dec = s.lastIndexOf(",") > s.lastIndexOf(".") ? "," : ".";
    const thousands = dec === "," ? "." : ",";
    const v = Number(s.split(thousands).join("").replace(dec, "."));
    if (Number.isFinite(v)) out.add(v);
  } else if (hasDot || hasComma) {
    const sep = hasDot ? "." : ",";
    const parts = s.split(sep);
    if (parts.length === 2 && /^\d+$/.test(parts[0]) && /^\d+$/.test(parts[1])) out.add(Number(`${parts[0]}.${parts[1]}`));
    // Thousands groups: "1.500", "1,500", "1.000.000".
    if (/^\d{1,3}$/.test(parts[0]) && parts.length >= 2 && parts.slice(1).every((p) => /^\d{3}$/.test(p))) out.add(Number(parts.join("")));
  } else if (/^\d+$/.test(s)) {
    out.add(Number(s));
  }
  return [...out].filter(Number.isFinite).map((v) => sign * v);
}

function same(a: number, b: number): boolean {
  return Math.abs(a - b) <= EPS * Math.max(1, Math.abs(b));
}

export function numberIsRight(input: string, answer: number | string): boolean {
  const target = typeof answer === "number" ? [answer] : numberCandidates(answer);
  if (target.length !== 1) return false;
  return numberCandidates(input).some((v) => same(v, target[0]));
}

/**
 * Lower case, single spaces, no commas, no full stop at the end, phone apostrophes (’) as ', and
 * without ``exact`` also č→c, š→s, ž→z, é→e.
 */
export function normalizeText(s: string, exact = false): string {
  let out = s
    .normalize("NFC")
    .replace(/[’‘`´]/g, "'")
    .replace(/,/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/\s*[.!?]+$/, "")
    .trim();
  if (!exact) out = out.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d");
  return out;
}

export function textIsRight(input: string, task: Pick<Task, "answer" | "accept" | "exact">): boolean {
  const given = normalizeText(input, task.exact);
  if (!given) return false;
  return [String(task.answer ?? ""), ...(task.accept ?? [])].some((a) => normalizeText(a, task.exact) === given);
}
