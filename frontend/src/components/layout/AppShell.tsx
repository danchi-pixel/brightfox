/**
 * The frame around the pages: parents get a navigation (Overview, Topics, Foxy, Family, Guide); a learner gets their
 * classroom with a small top bar (name, sign out). Phones get a bottom bar for parents.
 */
import { BookOpenCheck, Bot, House, LifeBuoy, LogOut, Users } from "lucide-react";
import { NavLink, Outlet } from "react-router";
import { useAuth } from "@/lib/auth";
import { APP_NAME } from "@/lib/brand";
import { cn } from "@/lib/utils";
import { translate } from "@/features/learning/i18n";

const PARENT_NAV = [
  { to: "/", label: "Overview", icon: House, end: true },
  { to: "/topics", label: "Topics", icon: BookOpenCheck, end: false },
  { to: "/foxy", label: "Foxy", icon: Bot, end: false },
  { to: "/family", label: "Family", icon: Users, end: false },
  { to: "/guide", label: "Guide", icon: LifeBuoy, end: false },
];

export function AppShell() {
  const { isAdmin, me, signOut, language } = useAuth();
  return (
    <div className="soft-gradient flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 border-b border-border bg-background/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
          <NavLink to="/" className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="size-8" />
            <span className="font-display text-xl text-primary">{APP_NAME}</span>
          </NavLink>
          {isAdmin && (
            <nav className="hidden items-center gap-1 sm:flex">
              {PARENT_NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.end}
                  className={({ isActive }) =>
                    cn("inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-medium", isActive ? "bg-primary-soft text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")
                  }
                >
                  <n.icon className="size-4" /> {n.label}
                </NavLink>
              ))}
            </nav>
          )}
          <div className="flex-1" />
          <span className="hidden text-sm text-muted-foreground sm:inline">{isAdmin ? me.family?.name : me.learner_name}</span>
          {!isAdmin && (
            <button onClick={() => void signOut()} className="inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-sm text-muted-foreground hover:bg-muted" title={translate(language, "signOut")}>
              <LogOut className="size-4" />
              <span className="hidden sm:inline">{translate(language, "signOut")}</span>
            </button>
          )}
        </div>
      </header>
      <main className={cn("mx-auto w-full max-w-6xl flex-1 px-4 py-6", isAdmin && "pb-24 sm:pb-6")}>
        <Outlet />
      </main>
      {isAdmin && (
        <nav className="pb-safe fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-border bg-card/95 backdrop-blur sm:hidden">
          {PARENT_NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => cn("flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium", isActive ? "text-primary" : "text-muted-foreground")}
            >
              <n.icon className="size-5" />
              {n.label}
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  );
}
