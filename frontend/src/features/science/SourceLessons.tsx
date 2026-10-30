import { Button } from "@/components/ui/button";
import { SourcePicture } from "./SourcePicture";
import { sourceGroup } from "./session";
import type { Availability, Bank, Mode, SourceGroup } from "./types";

export const groupNames: Record<SourceGroup, string> = { notebook: "Zvezek", textbook: "Učbenik", review: "Za pregled" };
export function SourceLessons({ bank, catalog, group, lesson, setLesson, scope, base, busy, start, activate }: {
  bank: Bank; catalog: Bank; group: SourceGroup; lesson: string; setLesson: (id: string) => void;
  scope: Availability; base: string; busy: boolean; start: (mode: Mode, weak: boolean, lesson: string) => void;
  activate: (id: string, enabled: boolean) => void;
}) {
  const selected = bank.lessons.find(l => l.id === lesson);
  return <section className="science-study"><h1>{groupNames[group]} · Učenje po temah</h1>
    <label>Izberi temo<select value={lesson} onChange={e => setLesson(e.target.value)}><option value="all">Vse teme po vrsti</option>{bank.lessons.map(l => <option key={l.id} value={l.id}>{l.title}</option>)}</select></label>
    {(selected ? [selected] : bank.lessons).map(l => {
      const questions = bank.questions.filter(q => q.topic === l.id);
      const enabled = questions.some(q => scope.active_questions.includes(q.id));
      const notesMatch = sourceGroup(catalog, l.sources) === group;
      return <article className="science-lesson" key={l.id}>
        <div className="science-eyebrow">{groupNames[group]} · {enabled ? "Na voljo za vajo" : group === "review" ? "Vir potrebuje pregled" : "Za kasneje · Še ni obravnavano"}</div>
        <h2>{l.icon} {l.title}</h2><p>{l.summary}</p>
        {group === "textbook" && scope.can_manage && <Button variant={enabled ? "outline" : "primary"} disabled={busy} onClick={() => activate(l.id, !enabled)}>{enabled ? "Prestavi za kasneje" : "Aktiviraj temo"}</Button>}
        {!enabled && <p className="science-hint">{group === "review" ? "Vprašanje navaja različne ali neznane vrste virov. Do pregleda ni vključeno v vaje ali napredek." : "Gradivo lahko prebereš. Vaje in napredek se vključijo, ko temo aktivirajo starši."}</p>}
        {notesMatch ? <><div>{l.notes.map((n, i) => <p className="my-4" key={i}>{n}</p>)}</div><dl>{Object.entries(l.vocabulary).map(([term, meaning]) => <div key={term}><dt>{term}</dt><dd>{meaning}</dd></div>)}</dl></> : <details className="science-details"><summary>Skupna razlaga teme (zvezek in učbenik)</summary><p>Ta razlaga združuje oba vira. Spodnja vprašanja so ločena po izvoru.</p>{l.notes.map((n, i) => <p className="my-4" key={i}>{n}</p>)}<dl>{Object.entries(l.vocabulary).map(([term, meaning]) => <div key={term}><dt>{term}</dt><dd>{meaning}</dd></div>)}</dl></details>}
        <div className="flex flex-wrap gap-3 my-4"><Button variant="primary" disabled={busy || !enabled} onClick={() => start("oral", false, l.id)}>Razložim na glas</Button><Button variant="outline" disabled={busy || !enabled || !questions.some(q => q.kind !== "oral")} onClick={() => start("quiz", false, l.id)}>Preverim s kvizom</Button></div>
        <h3>Obstoječa vprašanja · {questions.length}</h3>
        {questions.map(q => <details className="science-details" key={q.id}><summary>{q.prompt}</summary>
          {q.image && <SourcePicture picture={q.image} sources={catalog.sources} base={base} />}
          {!!q.items?.length && <p>{q.items.join(" · ")}</p>}{!!q.options?.length && <p>{q.options.join(" · ")}</p>}
          <p>{q.answer}</p><ul>{q.points.map(p => <li key={p}>{p}</li>)}</ul>
          {!!q.correct?.length && <p>{q.correct.join(" → ")}</p>}
          <details><summary>Namigi</summary>{q.hints.map(h => <p key={h}>{h}</p>)}</details>
          {q.followup && <p>{q.followup} {q.followup_answer}</p>}
          <p className="text-sm text-muted-foreground">Vir: {q.sources.map(id => catalog.sources.find(s => s.id === id)?.label ?? id).join(" · ")}</p>
        </details>)}
      </article>;
    })}
  </section>;
}
