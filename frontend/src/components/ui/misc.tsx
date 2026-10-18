import { Switch as RSwitch, Tooltip as RTooltip } from "radix-ui";
import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({ children, className, ...rest }: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("rounded-2xl border border-border bg-card", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, action, icon, className }: { title: ReactNode; action?: ReactNode; icon?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center justify-between gap-3 px-5 pt-4 pb-3", className)}>
      <h2 className="flex items-center gap-2 font-display text-lg font-semibold uppercase tracking-wide">
        {icon && <span className="text-primary [&_svg]:size-5">{icon}</span>}
        {title}
      </h2>
      {action}
    </div>
  );
}

export function Badge({ children, className, color }: { children: ReactNode; className?: string; color?: string | null }) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground", className)}
      style={color ? { borderColor: `${color}55`, color, background: `${color}14` } : undefined}
    >
      {children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-xl bg-muted", className)} />;
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-5 animate-spin text-muted-foreground", className)} />;
}

export function PageLoader() {
  return (
    <div className="flex h-64 items-center justify-center">
      <Spinner className="size-7" />
    </div>
  );
}

export function EmptyState({ icon, title, children, action, className }: { icon?: ReactNode; title: ReactNode; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-2xl border border-dashed border-input px-6 py-12 text-center", className)}>
      {icon && <div className="mb-3 rounded-2xl bg-primary-soft p-3 text-primary [&_svg]:size-7">{icon}</div>}
      <h3 className="font-display text-xl font-semibold uppercase tracking-wide">{title}</h3>
      {children && <div className="mt-1 max-w-md text-sm text-muted-foreground">{children}</div>}
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="rounded-2xl border border-danger/40 bg-danger/10 p-5 text-sm">
      <p className="font-medium text-danger">Something went wrong</p>
      <p className="mt-1 text-muted-foreground">{error instanceof Error ? error.message : String(error)}</p>
      {onRetry && (
        <button className="mt-3 text-sm font-medium text-primary underline" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Progress({ value, className, indeterminate }: { value: number; className?: string; indeterminate?: boolean }) {
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}>
      {indeterminate ? (
        <div className="h-full w-1/3 rounded-full bg-primary" style={{ animation: "uc-indeterminate 1.2s ease-in-out infinite" }} />
      ) : (
        <div className="h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%` }} />
      )}
      <style>{`@keyframes uc-indeterminate{0%{transform:translateX(-100%)}100%{transform:translateX(300%)}}`}</style>
    </div>
  );
}

export function Switch({ checked, onCheckedChange, label, description, disabled, id }: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  label?: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
  id?: string;
}) {
  const control = (
    <RSwitch.Root
      id={id}
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      className="relative h-6 w-11 shrink-0 rounded-full bg-input transition-colors data-[state=checked]:bg-primary disabled:opacity-50"
    >
      <RSwitch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[22px]" />
    </RSwitch.Root>
  );
  if (!label) return control;
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 py-1">
      <span className="min-w-0">
        <span className="block text-sm font-medium">{label}</span>
        {description && <span className="block text-xs text-muted-foreground">{description}</span>}
      </span>
      {control}
    </label>
  );
}

export function Tooltip({ content, children, side = "top" }: { content: ReactNode; children: ReactNode; side?: "top" | "bottom" | "left" | "right" }) {
  return (
    <RTooltip.Root delayDuration={300}>
      <RTooltip.Trigger asChild>{children}</RTooltip.Trigger>
      <RTooltip.Portal>
        <RTooltip.Content side={side} sideOffset={6} className="z-[60] rounded-lg border border-border bg-card-2 px-2.5 py-1.5 text-xs text-foreground shadow-card">
          {content}
        </RTooltip.Content>
      </RTooltip.Portal>
    </RTooltip.Root>
  );
}

/** Segmented control (radio group with buttons). */
export function Segmented<T extends string | number>({
  value,
  onChange,
  options,
  className,
  size = "md",
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode; icon?: ReactNode; title?: string }[];
  className?: string;
  size?: "sm" | "md";
}) {
  return (
    <div role="radiogroup" className={cn("inline-flex flex-wrap gap-1 rounded-xl bg-muted p-1", className)}>
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          title={o.title}
          onClick={() => onChange(o.value)}
          className={cn(
            "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors [&_svg]:size-4",
            size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-sm",
            value === o.value ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {o.icon}
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function StatTile({ label, value, sub, icon }: { label: string; value: ReactNode; sub?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="flex items-center justify-between text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
        {icon && <span className="text-primary [&_svg]:size-4">{icon}</span>}
      </div>
      <div className="mt-1 font-display text-3xl font-semibold tabular">{value}</div>
      {sub && <div className="text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

export function PlayerAvatar({ player, size = "md", className }: { player?: { avatar: string; color: string; name: string } | null; size?: "xs" | "sm" | "md" | "lg" | "xl"; className?: string }) {
  const sizes = { xs: "size-5 text-[11px]", sm: "size-7 text-sm", md: "size-9 text-base", lg: "size-14 text-2xl", xl: "size-20 text-4xl" };
  if (!player) return <span className={cn("inline-flex items-center justify-center rounded-full bg-muted", sizes[size], className)}>👪</span>;
  return (
    <span
      title={player.name}
      className={cn("inline-flex shrink-0 items-center justify-center rounded-full ring-2", sizes[size], className)}
      style={{ background: `${player.color}22`, boxShadow: `0 0 0 2px ${player.color}` }}
    >
      {player.avatar || player.name.slice(0, 1)}
    </span>
  );
}
