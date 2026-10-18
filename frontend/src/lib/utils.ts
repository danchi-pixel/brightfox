import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 75 -> "1:15", 3725 -> "1:02:05" */
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

/** Countdown display: rounds *up* so "0:01" shows until the very end. */
export function formatCountdown(ms: number): string {
  return formatClock(Math.ceil(Math.max(0, ms) / 1000));
}

/** 12.345 -> "0:12.3" (editor timestamps) */
export function formatTimestamp(seconds: number, decimals = 1): string {
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  const rest = s - m * 60;
  const fixed = rest.toFixed(decimals);
  const [whole, frac] = fixed.split(".");
  return `${m}:${whole.padStart(2, "0")}${frac ? "." + frac : ""}`;
}

/** Parses "1:02.5", "62.5", "1:02" into seconds. Returns null if invalid. */
export function parseTimestamp(text: string): number | null {
  const t = text.trim();
  if (!t) return null;
  const parts = t.split(":");
  if (parts.length > 3) return null;
  let total = 0;
  for (const p of parts) {
    const n = Number(p);
    if (!Number.isFinite(n) || n < 0) return null;
    total = total * 60 + n;
  }
  return total;
}

export function formatMinutes(seconds: number): string {
  const m = Math.round(seconds / 60);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  return `${h} h ${m % 60} min`;
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** i).toFixed(i >= 2 ? 1 : 0)} ${units[i]}`;
}

export function pluralize(n: number, word: string, plural?: string) {
  return `${n} ${n === 1 ? word : (plural ?? word + "s")}`;
}

export function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n));
}

export function uid(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
}

export const MODE_LABELS: Record<string, string> = {
  timed: "Timed",
  reps: "Sets & reps",
  target: "Skill target",
};

export const DIFFICULTY_LABELS: Record<number, string> = { 1: "Beginner", 2: "Intermediate", 3: "Advanced" };

export const TIERS = ["S", "A", "B", "C", "D"] as const;

/** S = most important for real matches … D = just for fun / a cool trick. */
export const TIER_INFO: Record<(typeof TIERS)[number], { color: string; label: string }> = {
  S: { color: "#f43f5e", label: "Essential — very important and useful in matches" },
  A: { color: "#f97316", label: "Very useful" },
  B: { color: "#eab308", label: "Useful" },
  C: { color: "#22c55e", label: "Nice to have" },
  D: { color: "#38bdf8", label: "Just for fun — a cool trick, little use in real matches" },
};

export function locationLabel(e: { indoor: boolean; outdoor: boolean }): string | null {
  if (e.indoor && e.outdoor) return "Indoor & outdoor";
  if (e.indoor) return "Indoor";
  if (e.outdoor) return "Outdoor";
  return null;
}
