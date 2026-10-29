import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, Lightbulb, MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { isCorrect, shuffle } from "./session";
import { labels, type Bank, type Mode, type Question, type Rating } from "./types";
import { SourcePicture } from "./SourcePicture";

export function Exercise({ question: q, mode, bank, base, busy, onRate }: {
  question: Question; mode: Mode; bank: Bank; base: string; busy: boolean; onRate: (rating: Rating) => void;
}) {
  const [hints, setHints] = useState(0);
  const [attempted, setAttempted] = useState(false);
  const [shown, setShown] = useState(false);
  const [text, setText] = useState("");
  const [values, setValues] = useState<string[]>([]);
  const [options] = useState(() => shuffle(q.options ?? []));
  const [order, setOrder] = useState(() => shuffle(q.items ?? []));
  const [checked, setChecked] = useState<boolean | null>(null);
  const [followup, setFollowup] = useState(false);
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => { title.current?.focus(); }, []);
  const oral = q.kind === "oral" || mode === "cards";
  const supplied = q.kind === "sequence" ? order : values;
  const complete = q.kind === "sequence" || (q.kind === "fill" ? !!values[0]?.trim() : (q.kind === "choice" || q.kind === "boolean") ? !!values[0] : (q.items ?? []).every((_, i) => !!values[i]));
  function choose(i: number, value: string) { setValues(v => { const next = [...v]; next[i] = value; return next; }); }
  function move(i: number, step: number) { setOrder(v => { const next = [...v]; [next[i], next[i + step]] = [next[i + step], next[i]]; return next; }); }
  return <article className="science-exercise">
    <div className="science-eyebrow">{bank.lessons.find(l => l.id === q.topic)?.title} · {q.difficulty === 1 ? "Za ogrevanje" : q.difficulty === 2 ? "Poveži in razloži" : "Razmisli globlje"}</div>
    <h2 ref={title} tabIndex={-1}>{q.prompt}</h2>
    {q.image && <SourcePicture picture={q.image} sources={bank.sources} base={base} />}
    {oral ? <>
      <p className="text-muted-foreground">{mode === "cards" ? "Najprej prikliči odgovor iz spomina. Nato obrni kartico." : "Vzemi si čas. Odgovori na glas ali zapiši misel. Poslušanje in snemanje nista vključena."}</p>
      {mode !== "cards" && <details className="science-details"><summary>Raje zapišem odgovor</summary><label className="block mt-3">Moj odgovor<textarea value={text} onChange={e => setText(e.target.value)} rows={4} maxLength={2000} placeholder="Razloži s svojimi besedami …" /></label><p className="text-sm text-muted-foreground">Zapis ostane samo v tej vaji; shranimo le tvojo samooceno.</p></details>}
      {!attempted && <Button size="lg" variant="primary" onClick={() => { setAttempted(true); if (mode === "cards") setShown(true); }}><MessageCircle />{mode === "cards" ? "Obrni kartico" : "Moj odgovor je končan"}</Button>}
    </> : <fieldset disabled={checked !== null || busy} className="space-y-3">
      <legend className="sr-only">Odgovor</legend>
      {(q.kind === "choice" || q.kind === "boolean") && options.map(o => <label className={`science-option ${values[0] === o ? "selected" : ""}`} key={o}><input type="radio" name={q.id} value={o} checked={values[0] === o} onChange={() => choose(0, o)} /><span>{o}</span></label>)}
      {q.kind === "fill" && <label className="block">Manjkajoča beseda<input className="science-input" value={values[0] ?? ""} onChange={e => choose(0, e.target.value)} autoComplete="off" /></label>}
      {["match", "sort", "label"].includes(q.kind) && (q.items ?? []).map((item, i) => <label key={item} className="science-match"><span>{item}</span><select value={values[i] ?? ""} onChange={e => choose(i, e.target.value)}><option value="">Izberi …</option>{options.map(o => <option key={o}>{o}</option>)}</select></label>)}
      {q.kind === "sequence" && <><p className="text-sm text-muted-foreground">Premakni korake s puščicama. Gumba delujeta tudi s tipkovnico.</p><ol className="space-y-2">{order.map((item, i) => <li className="science-order" key={item}><b>{i + 1}.</b><span>{item}</span><button type="button" disabled={i === 0} onClick={() => move(i, -1)} aria-label={`Premakni gor: ${item}`}><ArrowUp /></button><button type="button" disabled={i === order.length - 1} onClick={() => move(i, 1)} aria-label={`Premakni dol: ${item}`}><ArrowDown /></button></li>)}</ol></>}
      <Button size="lg" variant="primary" disabled={!complete} onClick={() => { setChecked(isCorrect(q, supplied)); setAttempted(true); setShown(true); }}>Preveri odgovor</Button>
    </fieldset>}
    {!shown && <div className="flex flex-wrap gap-3">
      {hints < q.hints.length && <Button size="lg" variant="outline" onClick={() => setHints(n => n + 1)}><Lightbulb />Pokaži namig {hints + 1}</Button>}
      {oral && attempted && <Button size="lg" variant="primary" onClick={() => setShown(true)}>{mode === "cards" ? "Pokaži drugo stran" : "Pokaži pravilen odgovor"}</Button>}
    </div>}
    {hints > 0 && <aside className="science-hint" aria-live="polite">{q.hints.slice(0, hints).map((h, i) => <p key={i}>{h}</p>)}</aside>}
    {mode === "cards" && attempted && !shown && <p className="text-sm">Primerjaj svojo razlago z drugo stranjo kartice.</p>}
    {shown && <section className="science-answer" aria-live="polite">
      <h3>{checked === null ? "Primer odgovora" : checked ? "Tako je! ✨" : "Dober poskus. Poglej razlago in poskusi povezati pojme."}</h3>
      <p>{q.answer}</p>
      <h4>Pomembne točke</h4>
      <div className="space-y-2">{q.points.map(point => <label key={point} className="flex gap-3 items-start"><input type="checkbox" className="mt-1 size-5 shrink-0" /><span>{point}</span></label>)}</div>
      {q.followup && <details className="science-details"><summary>Dodatno vprašanje: {q.followup}</summary><p className="mt-3">Najprej odgovori s svojimi besedami.</p><Button size="lg" variant="outline" onClick={() => setFollowup(true)}>Pokaži razlago dodatnega vprašanja</Button>{followup && <p className="mt-3">{q.followup_answer}</p>}</details>}
      <p className="font-semibold">{oral ? "Kako gre? Izberi svojo samooceno." : "Nadaljuj – tudi napake pomagajo pri učenju."}</p>
      <div className="science-rating">{oral ? (Object.keys(labels) as Rating[]).map(r => <Button key={r} size="lg" variant={r === "know" ? "primary" : "outline"} disabled={busy} onClick={() => onRate(r)}>{labels[r]}</Button>) : <Button size="lg" variant="primary" disabled={busy} onClick={() => onRate(checked ? "know" : "practice")}>Naslednje vprašanje</Button>}</div>
    </section>}
    <p className="text-xs text-muted-foreground">Vir: {q.sources.map(id => bank.sources.find(s => s.id === id)?.label).join(" · ")}</p>
  </article>;
}
