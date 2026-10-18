import { Dialog as D } from "radix-ui";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  size = "md",
  className,
  hideClose,
  headerAction,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl" | "full";
  className?: string;
  hideClose?: boolean;
  /** Shown in the header next to the close button. */
  headerAction?: ReactNode;
}) {
  const widths = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl", full: "max-w-6xl" };
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-50 bg-[var(--overlay)] backdrop-blur-[2px] data-[state=open]:animate-in" />
        <D.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 flex max-h-[92dvh] w-[calc(100vw-1.5rem)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-2xl border border-border bg-card shadow-card",
            widths[size],
            className,
          )}
          onOpenAutoFocus={(e) => {
            // Avoid popping the keyboard open on touch devices.
            if (window.matchMedia("(pointer: coarse)").matches) e.preventDefault();
          }}
        >
          <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
            <div className="min-w-0">
              <D.Title className="font-display text-xl font-semibold uppercase tracking-wide">{title}</D.Title>
              {description ? (
                <D.Description className="mt-0.5 text-sm text-muted-foreground">{description}</D.Description>
              ) : (
                <D.Description className="sr-only">{typeof title === "string" ? title : "Dialog"}</D.Description>
              )}
            </div>
            {headerAction && <div className="ml-auto flex shrink-0 items-center gap-2">{headerAction}</div>}
            {!hideClose && (
              <D.Close className="-mr-2 rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="Close">
                <X className="size-5" />
              </D.Close>
            )}
          </div>
          <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
          {footer && <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border px-5 py-3">{footer}</div>}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}
