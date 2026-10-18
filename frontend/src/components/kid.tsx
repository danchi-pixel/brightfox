/** Big, friendly building blocks for the kids' screens. */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function ChoiceTile({
  selected,
  onClick,
  children,
  className,
  disabled,
}: {
  selected?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={!!selected}
      className={cn(
        "w-full rounded-2xl border-2 px-4 py-3.5 text-left text-base font-medium transition-colors disabled:opacity-60",
        selected ? "border-primary bg-primary-soft" : "border-border bg-card hover:border-input hover:bg-card-2",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Feedback({ children, tone = "info", className }: { children: ReactNode; tone?: "info" | "soft" | "warn"; className?: string }) {
  return (
    <div
      role="status"
      className={cn(
        "rounded-2xl border px-4 py-3 text-[15px] leading-relaxed",
        tone === "info" ? "border-info/30 bg-info/10" : tone === "warn" ? "border-warning/40 bg-warning/10" : "border-border bg-card-2",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function Prompt({ children }: { children: ReactNode }) {
  return <h2 className="text-xl font-semibold leading-snug sm:text-2xl">{children}</h2>;
}
