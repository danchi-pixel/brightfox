import type { ReactNode } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Link } from "react-router";
import { FoxAvatar } from "./ui";
import "../science/science.css";

/** Shared presentation for subject collections and source-based learning banks. */
export function StudyHubHeader({ lid }: { lid: number }) {
  return <header className="science-topbar"><Link to={`/l/${lid}`} className="inline-flex items-center gap-2"><ArrowLeft size={18} />Moja učilnica</Link><span className="font-display font-bold">BrightFox <span aria-hidden>🦊</span></span></header>;
}
export function StudyHubNav({ label, items, current, onSelect }: { label: string; items: readonly (readonly [string, string])[]; current: string | null; onSelect: (id: string) => void }) {
  return <nav className="science-nav" aria-label={label}>{items.map(([id, title]) => <button key={id} onClick={() => onSelect(id)} aria-current={current === id ? "page" : undefined}>{title}</button>)}</nav>;
}
export function StudyHubHero({ title, eyebrow, greeting, description, children, symbols = ["🪐", "🌿", "💧"] }: { title: string; eyebrow: string; greeting: string; description: string; children?: ReactNode; symbols?: string[] }) {
  return <section className="science-hero"><div><div className="science-eyebrow">{eyebrow}</div><h1>{title}</h1><p>{greeting}</p><p className="science-hero-sub">{description}</p><div className="flex flex-wrap gap-3 mt-6">{children}</div></div><div className="science-hero-art" aria-hidden><span>{symbols[0]}</span><FoxAvatar size="lg" /><span>{symbols[1]}</span><span>{symbols[2]}</span></div></section>;
}
export function StudyHubEntry({ to, title, description, icon }: { to: string; title: string; description: string; icon: string }) {
  return <Link to={to} className="flex items-center gap-4 rounded-3xl border-2 border-primary/30 bg-primary-soft p-6"><span className="text-4xl" aria-hidden>{icon}</span><span className="min-w-0 flex-1"><span className="block font-display text-2xl font-bold">{title}</span><span className="text-sm text-muted-foreground">{description}</span></span><ArrowRight className="shrink-0" /></Link>;
}
