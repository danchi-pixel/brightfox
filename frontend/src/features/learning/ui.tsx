/** Small building blocks shared by the learning screens. */
import { BookOpen, Calculator, FlaskConical, Globe2, Languages, MessageCircleQuestion, type LucideIcon } from "lucide-react";
import { Fragment, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Subject } from "./api";
import type { Key } from "./i18n";

export const SUBJECT_META: Record<Subject, { icon: LucideIcon; color: string; key: Key }> = {
  math: { icon: Calculator, color: "#0ea5e9", key: "subj_math" },
  slovene: { icon: BookOpen, color: "#ec4899", key: "subj_slovene" },
  english: { icon: Languages, color: "#8b5cf6", key: "subj_english" },
  science: { icon: FlaskConical, color: "#16a34a", key: "subj_science" },
  society: { icon: Globe2, color: "#f59e0b", key: "subj_society" },
  other: { icon: MessageCircleQuestion, color: "#64748b", key: "subj_other" },
};

export function SubjectBubble({ subject, size = "md", className }: { subject: Subject; size?: "sm" | "md" | "lg"; className?: string }) {
  const meta = SUBJECT_META[subject] ?? SUBJECT_META.other;
  const sizes = { sm: "size-9 [&_svg]:size-4", md: "size-12 [&_svg]:size-6", lg: "size-16 [&_svg]:size-8" };
  return (
    <span
      className={cn("inline-flex shrink-0 items-center justify-center rounded-2xl", sizes[size], className)}
      style={{ background: `color-mix(in srgb, ${meta.color} 15%, transparent)`, color: meta.color }}
    >
      <meta.icon aria-hidden />
    </span>
  );
}

/** Foxy's face: a fox in a soft circle. */
export function FoxAvatar({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const sizes = { sm: "size-8 text-lg", md: "size-10 text-2xl", lg: "size-16 text-4xl" };
  return (
    <span className={cn("inline-flex shrink-0 items-center justify-center rounded-full bg-primary-soft", sizes[size])} aria-hidden>
      🦊
    </span>
  );
}

export function LearnerAvatar({ learner, size = "md", className }: { learner?: { avatar: string; color: string; name: string } | null; size?: "xs" | "sm" | "md" | "lg"; className?: string }) {
  const sizes = { xs: "size-5 text-[11px]", sm: "size-7 text-sm", md: "size-9 text-base", lg: "size-14 text-2xl" };
  if (!learner) return <span className={cn("inline-flex items-center justify-center rounded-full bg-muted", sizes[size], className)}>👪</span>;
  return (
    <span
      title={learner.name}
      className={cn("inline-flex shrink-0 items-center justify-center rounded-full", sizes[size], className)}
      style={{ background: `${learner.color}22`, boxShadow: `0 0 0 2px ${learner.color}` }}
    >
      {learner.avatar || learner.name.slice(0, 1)}
    </span>
  );
}

/** **bold** inside a line of text (nothing else is interpreted). */
function inline(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) => (p.startsWith("**") && p.endsWith("**") && p.length > 4 ? <strong key={i}>{p.slice(2, -2)}</strong> : <Fragment key={i}>{p}</Fragment>));
}

/** Foxy's plain text: paragraphs, "- " lists, line breaks and **bold**. Never HTML. */
export function RichText({ text, className }: { text: string; className?: string }) {
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/);
  return (
    <div className={cn("space-y-2 break-words", className)}>
      {blocks.map((block, bi) => {
        const lines = block.split("\n");
        if (lines.every((l) => /^\s*[-•*]\s+/.test(l))) {
          return (
            <ul key={bi} className="list-disc space-y-0.5 pl-5">
              {lines.map((l, li) => (
                <li key={li}>{inline(l.replace(/^\s*[-•*]\s+/, ""))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={bi}>
            {lines.map((l, li) => (
              <Fragment key={li}>
                {li > 0 && <br />}
                {inline(l)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}

/** A full-screen page with a close button (practice, learning, chat). */
export function FullScreen({ title, onClose, closeLabel, children, right }: { title: ReactNode; onClose: () => void; closeLabel: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="sticky top-0 z-10 border-b border-border bg-background/90 backdrop-blur print:hidden">
        <div className="mx-auto flex h-14 max-w-2xl items-center gap-3 px-4">
          <button onClick={onClose} className="-ml-2 rounded-xl p-2 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label={closeLabel}>
            <span aria-hidden className="text-xl leading-none">✕</span>
          </button>
          <div className="min-w-0 flex-1 truncate text-sm font-medium text-muted-foreground">{title}</div>
          {right}
        </div>
      </header>
      <main className="mx-auto w-full max-w-2xl flex-1 space-y-5 px-4 py-5 print:max-w-none print:p-0">{children}</main>
    </div>
  );
}
