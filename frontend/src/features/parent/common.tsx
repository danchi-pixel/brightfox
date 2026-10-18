/** Small helpers for the parent screens (English for now). */
import { ShieldAlert, ShieldCheck } from "lucide-react";
import type { StudioTopicCard, Subject } from "../learning/api";
import { translate } from "../learning/i18n";
import { SUBJECT_META } from "../learning/ui";

export const subjectName = (s: Subject) => translate("en", SUBJECT_META[s].key);

export function gradeName(g: number | null | undefined, short = false): string {
  if (!g) return "Grade not set";
  if (short) return g <= 9 ? `${g}. razred` : `${g - 9}. letnik`;
  return g <= 9 ? `${g}. razred (grade ${g})` : `${g - 9}. letnik (secondary year ${g - 9})`;
}

export function usd(v: number | null | undefined): string {
  if (v === null || v === undefined) return "–";
  return v < 0.01 && v > 0 ? "< $0.01" : `$${v.toFixed(2)}`;
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

export function PageTitle({ title, sub, children }: { title: string; sub?: string; children?: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <h1 className="font-display text-4xl leading-none">{title}</h1>
      {sub && <p className="max-w-3xl text-muted-foreground">{sub}</p>}
      {children}
    </div>
  );
}

export function ApprovalBadge({ card }: { card: Pick<StudioTopicCard, "approved" | "learner_ids" | "outdated_ids"> }) {
  if (card.approved)
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
        <ShieldCheck className="size-3.5" /> Approved
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning">
      <ShieldAlert className="size-3.5" /> {card.outdated_ids.length ? "Changed: check again" : "Needs your check"}
    </span>
  );
}
