/** Readiness, mastery and this week, drawn the same way for kids and parents. Nothing here can be "lost". */
import { Check } from "lucide-react";
import { Link } from "react-router";
import { cn } from "@/lib/utils";
import type { MasteryLabel, PlanStep, WeekView } from "../learning/api";
import { useT, type Key } from "../learning/i18n";

const LABEL_STYLE: Record<MasteryLabel, string> = {
  know: "bg-success/12 text-success",
  almost: "bg-warning/15 text-warning",
  not_yet: "bg-danger/10 text-danger",
  not_started: "bg-muted text-muted-foreground",
};

export function MasteryChip({ label, className }: { label: MasteryLabel; className?: string }) {
  const { t } = useT();
  return <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold", LABEL_STYLE[label], className)}>{t(`m_${label}` as Key)}</span>;
}

/** A ring with "about N %": readiness is an estimate, so it's rounded and shown as "about". */
export function ReadinessRing({ value, size = 76 }: { value: number | null; size?: number }) {
  const pct = value === null ? 0 : Math.round(value * 100);
  const r = size / 2 - 7;
  const c = 2 * Math.PI * r;
  const color = value === null ? "var(--muted-foreground)" : value >= 0.8 ? "var(--success)" : value >= 0.5 ? "var(--warning)" : "var(--primary)";
  return (
    <span className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--muted)" strokeWidth={7} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={7} strokeLinecap="round" strokeDasharray={`${(pct / 100) * c} ${c}`} />
      </svg>
      <span className="absolute font-display text-lg">{value === null ? "–" : `${pct}%`}</span>
    </span>
  );
}

export function daysLeftText(t: (k: Key, v?: Record<string, string | number>) => string, n: number): string {
  return n <= 0 ? t("todayWord") : n === 1 ? t("tomorrow") : t("inDays", { n });
}

/** Where a plan step leads. */
export function stepHref(lid: number, s: PlanStep): string {
  switch (s.kind) {
    case "learn":
    case "cards":
      return `/l/${lid}/learn/${s.topic_id}${s.kind === "cards" ? "?tab=cards" : ""}`;
    case "practice":
      return `/l/${lid}/practice/${s.topic_id}${s.skill_id && s.skill_id !== "_topic" ? `?skill=${s.skill_id}` : ""}`;
    case "challenge":
      return `/l/${lid}/practice/${s.topic_id}?challenge=1`;
    case "review":
      return `/l/${lid}/review`;
    case "mock":
      return `/l/${lid}/mock/${s.topic_id}`;
    default:
      return `/l/${lid}`;
  }
}

export function StepRow({ lid, step, showTitle = true }: { lid: number; step: PlanStep; showTitle?: boolean }) {
  const { t } = useT();
  return (
    <Link
      to={stepHref(lid, step)}
      className={cn(
        "flex items-center gap-3 rounded-2xl border-2 px-3 py-2.5 transition hover:-translate-y-0.5",
        step.done ? "border-success/40 bg-success/10" : "border-border bg-card hover:border-input",
      )}
    >
      <span className={cn("grid size-7 shrink-0 place-items-center rounded-lg border-2", step.done ? "border-success bg-success text-white" : "border-input")}>
        {step.done && <Check className="size-4" />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold leading-tight">{t(`step_${step.kind}` as Key)}</span>
        {showTitle && step.title && step.kind !== "review" && <span className="block truncate text-sm text-muted-foreground">{step.title}</span>}
      </span>
      <span className="shrink-0 text-xs text-muted-foreground">{t("minutesN", { n: step.minutes })}</span>
    </Link>
  );
}

/** This week, Monday to Sunday: a dot for every day with learning. It starts fresh every Monday. */
export function WeekDots({ week }: { week: WeekView }) {
  const { t } = useT();
  const letters = t("dayShort").split(",");
  return (
    <div className="flex items-center gap-1.5" aria-label={t("thisWeek")}>
      {week.days.map((d, i) => (
        <span key={d.date} className="flex flex-col items-center gap-1">
          <span
            className={cn(
              "grid size-8 place-items-center rounded-full border-2 text-xs font-semibold",
              d.active ? "border-success bg-success text-white" : d.usual ? "border-primary/40 text-muted-foreground" : "border-border text-muted-foreground/60",
              d.today && !d.active && "ring-2 ring-primary/40",
            )}
          >
            {d.active ? <Check className="size-4" /> : letters[i]}
          </span>
        </span>
      ))}
    </div>
  );
}
