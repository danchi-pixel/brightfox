import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, Image, Layers, MessageCircle, Play, RotateCcw, Sparkles } from "lucide-react";
import { Link, useParams } from "react-router";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { useLearnerHome, type Topic } from "../learning/api";
import { StudyHubHeader, StudyHubHero, StudyHubNav } from "../learning/StudyHub";
import { Exercise } from "./Exercise";
import { SourcePicture } from "./SourcePicture";
import { makeSession, resumable } from "./session";
import { SourceLessons, groupNames } from "./SourceLessons";
import { labels, modes, type Availability, type SourceGroup, type Bank, type Mode, type Progress, type Rating, type Session } from "./types";
import "./science.css";

const icons = { oral: MessageCircle, mock: Sparkles, quiz: Play, images: Image, cards: Layers };
const descriptions = { oral: "Odgovori na glas, odkrij namig in preveri pomembne točke.", mock: "Mali nastop: od 5 do 10 vprašanj iz različnih tem.", quiz: "Izberi, poveži, razvrsti in uredi korake.", images: "Raziskuj fotografije in diagrame iz svojega gradiva.", cards: "Prikliči znanje. Najprej pridejo na vrsto šibkejše kartice." };

export default function SciencePage() {
  const { lid = "", tid = "" } = useParams();
  return <ScienceLoader key={`${lid}:${tid}`} lid={Number(lid)} tid={tid} />;
}
function ScienceLoader({ lid, tid }: { lid: number; tid: string }) {
  const home = useLearnerHome(lid);
  const topic = useQuery({ queryKey: ["science-topic", lid, tid], queryFn: () => api.get<Topic & { lab?: Bank }>(`/api/learners/${lid}/topics/${tid}`), retry: false });
  const progress = useQuery({ queryKey: ["science-progress", lid, tid], queryFn: () => api.get<Progress>(`/api/learners/${lid}/topics/${tid}/lab/progress`), enabled: !!topic.data?.lab, retry: false });
  const availability = useQuery({ queryKey: ["science-availability", lid, tid], queryFn: () => api.get<Availability>(`/api/learners/${lid}/topics/${tid}/lab/availability`), enabled: !!topic.data?.lab, retry: false, refetchInterval: 15000 });
  const error = home.error || topic.error || progress.error || availability.error;
  if (error) return <main className="science-shell" lang="sl"><h1>Učenja trenutno ni mogoče odpreti.</h1><p>Preveri povezavo in dostop do teme.</p><Button onClick={() => { void home.refetch(); void topic.refetch(); void progress.refetch(); void availability.refetch(); }}>Poskusi znova</Button><Link to={`/l/${lid}`}>Nazaj v učilnico</Link></main>;
  if (topic.data && !topic.data.lab) return <main className="science-shell" lang="sl"><p>Ta tema nima učne zbirke.</p><Link to={`/l/${lid}`}>Nazaj v učilnico</Link></main>;
  if (!home.data || !topic.data?.lab || !progress.data || !availability.data) return <main className="science-shell" role="status" lang="sl">Pripravljam raziskovanje …</main>;
  return <ScienceHub lid={lid} topic={topic.data as Topic & { lab: Bank }} initial={progress.data} scope={availability.data} owner={home.data.owner} name={home.data.learner.name} />;
}
function ScienceHub({ lid, topic, initial, scope, owner, name }: { lid: number; topic: Topic & { lab: Bank }; initial: Progress; scope: Availability; owner: boolean; name: string }) {
  const catalog = topic.lab;
  const [group, setGroup] = useState<SourceGroup>("notebook");
  const questions = catalog.questions.filter(q => scope.question_groups[q.id] === group);
  const bank = { ...catalog, questions, lessons: catalog.lessons.filter(l => questions.some(q => q.topic === l.id)) };
  const allowed = new Set(scope.active_questions);
  const practice = { ...bank, questions: bank.questions.filter(q => allowed.has(q.id)) };
  const canPractice = practice.questions.length > 0;
  const client = useQueryClient();
  const base = `/api/learners/${lid}/topics/${topic.id}/lab`;
  const [progress, setProgress] = useState(initial);
  const [active, setActive] = useState<Session | null>(null);
  const [view, setView] = useState<"home" | "study" | "progress" | "sources">("home");
  const [lesson, setLesson] = useState("all");
  const [count, setCount] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [notice, setNotice] = useState("");
  const [generation, setGeneration] = useState(0);
  const answers = progress.answers;
  const allAnswers = practice.questions.map(q => answers[`practice:${q.id}`] ?? answers[`cards:${q.id}`]).filter(Boolean);
  const known = allAnswers.filter(a => a.rating === "know").length;
  const current = active && catalog.questions.find(q => q.id === active.queue[active.index]);
  const due = practice.questions.filter(q => q.card && (!answers[`cards:${q.id}`] || Date.parse(answers[`cards:${q.id}`].due) <= Date.now())).length;

  useEffect(() => { setProgress(initial); }, [initial]);
  useEffect(() => {
    if (active && active.queue.some(id => !scope.active_questions.includes(id))) {
      setActive(null); setNotice("Izbor snovi se je spremenil. Neaktivne vaje so shranjene za kasneje.");
    }
  }, [scope, active]);
  async function activate(id: string, enabled: boolean) {
    setBusy(true); setError("");
    try {
      const result = await api.put<Availability>(`${base}/availability/${id}`, { version: topic.version, enabled });
      client.setQueryData(["science-availability", lid, topic.id], result);
      await client.invalidateQueries({ queryKey: ["uc"] });
      setNotice(enabled ? "Tema je zdaj na voljo za vajo." : "Tema je shranjena za kasneje. Prejšnji napredek ostane shranjen.");
    } catch { setError("Izbora ni mogoče shraniti. Osveži stran in poskusi znova."); }
    finally { setBusy(false); }
  }
  async function save(session: Session, question?: string, rating?: Rating) {
    if (busy || conflict || session.queue.some(id => !allowed.has(id))) return false;
    setError(""); setBusy(true);
    try {
      if (owner) {
        const result = await api.put<Progress>(`${base}/progress`, { revision: progress.revision, version: topic.version, session, question, rating });
        setProgress(result); client.setQueryData(["science-progress", lid, topic.id], result);
      } else setProgress(p => ({ ...p, session }));
      return true;
    } catch (e) {
      const stale = e instanceof ApiError && e.status === 409;
      setConflict(stale);
      setError(stale ? "Napredek ali snov se je spremenila v drugem oknu. Osveži stran za nadaljevanje." : "Napredka ni mogoče shraniti. Preveri povezavo in poskusi znova; odgovor je še tukaj.");
      return false;
    } finally { setBusy(false); }
  }
  async function start(mode: Mode, weak = false, selectedLesson = lesson) {
    const session = makeSession(practice, mode, progress, selectedLesson, count, weak, scope.enabled_lessons);
    if (!session.queue.length) { setNotice("Za ta izbor ni vprašanj za ponovitev. Izberi drugo temo ali drug način."); return; }
    if (await save(session)) { setActive(session); setGeneration(x => x + 1); setNotice(""); }
  }
  async function rate(rating: Rating) {
    if (!active || !current) return;
    const next = { ...active, index: active.index + 1, ratings: { ...active.ratings, [current.id]: rating } };
    if (await save(next, current.id, rating)) setActive(next);
  }
  function navigate(next: typeof view) { setView(next); setActive(null); setNotice(""); }
  const resume = resumable(progress.session, new Set(practice.questions.map(q => q.id)));

  return <main className="science-shell" lang="sl" aria-busy={busy}>
    <StudyHubHeader lid={lid} />
    {!owner && <p className="science-preview">Starševski predogled. Poskusi se ne shranijo v otrokov napredek.</p>}
    <section className="science-source-groups" aria-label="Izvor gradiva">{(["notebook", "textbook", "review"] as SourceGroup[]).map(g => <button key={g} aria-pressed={g === group} onClick={() => { setGroup(g); setLesson("all"); setActive(null); setView("home"); setNotice(""); }}><b>{g === "notebook" ? "📓" : g === "textbook" ? "📚" : "⚑"} {groupNames[g]}</b><span>{g === "notebook" ? "Na voljo zdaj" : g === "textbook" ? "Za kasneje · aktivirajo starši" : "Mešani ali neznani viri"}</span><small>{catalog.questions.filter(q => scope.question_groups[q.id] === g).length} vprašanj</small></button>)}</section>
    <p className="science-hint">{group === "notebook" ? "Vadi snov iz zvezka. Učbenik je ločen in čaka na aktivacijo staršev." : group === "textbook" ? "Učbenik: gradivo lahko prebereš. V vajo in napredek štejejo samo aktivne teme." : "Ta vprašanja čakajo na pregled izvora in se ne vključijo v vaje."}</p>
    <StudyHubNav label="Naravoslovje" items={[["home","Raziskuj"],["study","Učenje po temah"],["progress","Moj napredek"],["sources","Viri in opombe"]]} current={active ? null : view} onSelect={v => navigate(v as typeof view)} />
    {error && <div role="alert" className="science-error">{error}{conflict && <Button onClick={() => window.location.reload()}>Osveži stran</Button>}</div>}
    {notice && <p role="status" className="science-hint">{notice}</p>}
    {busy && <p role="status" className="text-sm text-muted-foreground">Shranjujem napredek …</p>}
    {active ? <>
      <div className="science-sessionbar"><Button variant="ghost" onClick={() => setActive(null)}><ArrowLeft />Nazaj na pregled</Button><span>{modes[active.mode]} · {Math.min(active.index + 1, active.queue.length)}/{active.queue.length}</span></div>
      <progress aria-label="Potek vaje" value={active.index} max={active.queue.length} />
      {current ? <Exercise key={`${generation}:${active.mode}:${active.index}:${current.id}`} question={current} mode={active.mode} bank={catalog} base={base} busy={busy || conflict} onRate={r => void rate(r)} /> : <section className="science-complete">
        <span className="text-5xl" aria-hidden>🌟</span><h1>Lep korak naprej, {name}!</h1><p>Vaja je zaključena. Tvoje razlage in samoocene pokažejo, kaj gre dobro in kaj še ponovi.</p><p className="text-sm text-muted-foreground">To je vaja, ne uradna šolska ocena.</p>
        {bank.lessons.filter(l => active.queue.some(id => bank.questions.find(q => q.id === id)?.topic === l.id)).map(l => {
          const qs = bank.questions.filter(q => q.topic === l.id && active.queue.includes(q.id));
          const ok = qs.every(q => active.ratings[q.id] === "know");
          return <div key={l.id} className="science-summary-row"><span>{l.icon} {l.title}</span><b>{ok ? "Dobro gre!" : "Še malo ponovi"}</b></div>;
        })}
        <div className="flex flex-wrap gap-3"><Button size="lg" variant="primary" onClick={() => { setActive(null); setView("progress"); }}>Poglej moj napredek</Button><Button size="lg" variant="outline" disabled={busy || !canPractice} onClick={() => void start(active.mode, true, "all")}><RotateCcw />Ponovi, kar še ne znam</Button></div>
      </section>}
    </> : view === "home" ? <>
      <StudyHubHero title={groupNames[group]} eyebrow={bank.title} greeting={`Živjo, ${name}! Pripraviva se na naravoslovje!`} description={group === "notebook" ? "Snov iz zvezka je pripravljena za vajo." : "Vse obstoječe razlage, slike in odgovori ostanejo na voljo za ogled."}><Button size="lg" variant="primary" disabled={busy || conflict || !canPractice} onClick={() => void start("oral")}><MessageCircle />Vadim ustno</Button>{resume && <Button size="lg" variant="outline" onClick={() => { void save(resume).then(ok => { if (ok) { setActive(resume); setGeneration(x => x + 1); } }); }}>Nadaljuj učenje <ArrowRight /></Button>}</StudyHubHero>
      <div className="science-stats"><span><b>{bank.lessons.length}</b> tem za raziskovanje</span><span><b>{allAnswers.length}</b> vprašanj v vaji</span><span><b>{known}</b> odgovorov znam</span></div>
      <div className="science-filters"><label>Tema<select value={lesson} onChange={e => setLesson(e.target.value)}><option value="all">Vse teme</option>{bank.lessons.map(l => <option value={l.id} key={l.id}>{l.title}</option>)}</select></label><label>Vprašanj v poskusnem ustnem<select value={count} onChange={e => setCount(Number(e.target.value))}>{[5,6,7,8,9,10].map(n => <option key={n}>{n}</option>)}</select></label></div>
      <section aria-label="Načini učenja" className="science-modes">{(Object.keys(modes) as Mode[]).map((mode, i) => { const Icon = icons[mode]; return <button className={`science-mode tone-${i}`} key={mode} disabled={busy || conflict || !canPractice} onClick={() => void start(mode)}><span className="science-mode-icon"><Icon /></span><span><b>{modes[mode]}</b><small>{descriptions[mode]}{mode === "cards" ? ` Za ponavljanje: ${due}.` : ""}</small></span><ArrowRight size={20} /></button>; })}</section>
      <div className="science-section-heading"><h2>Kam te vleče radovednost?</h2><span>Izberi temo v tej skupini.</span></div>
      <section className="science-topics">{bank.lessons.map((l, i) => <button key={l.id} onClick={() => { setLesson(l.id); setView("study"); }}><span className="science-topic-icon" aria-hidden>{l.icon}</span><small>{String(i + 1).padStart(2, "0")}</small><h3>{l.title}</h3><p>{l.summary}</p><p className="science-source-status">{group === "review" ? "Za pregled" : bank.questions.some(q => q.topic === l.id && allowed.has(q.id)) ? "Na voljo za vajo" : "Za kasneje · Še ni obravnavano"}</p><span className="science-topic-link">Razišči temo <ArrowRight size={16} /></span></button>)}</section>
    </> : view === "study" ? <SourceLessons bank={bank} catalog={catalog} group={group} lesson={lesson} setLesson={setLesson} scope={scope} base={base} busy={busy || conflict} start={(mode, weak, id) => void start(mode, weak, id)} activate={(id, enabled) => void activate(id, enabled)} /> : view === "progress" ? <section className="science-study"><h1>Moj napredek</h1><p>Vsaka razlaga je korak naprej. Tu so samoocene aktivnih vaj v izbrani skupini. Prejšnji napredek neaktivnih vaj ostane shranjen in se vrne ob aktivaciji.</p><div className="science-stats"><span><b>{allAnswers.length}</b> različnih vprašanj</span><span><b>{known}</b> znam</span><span><b>{allAnswers.length - known}</b> še ponavljam</span></div><Button size="lg" variant="primary" disabled={busy || !canPractice} onClick={() => void start("oral", true, "all")}>Ponovi, kar še ne znam</Button>
      {bank.lessons.map(l => { const qs = practice.questions.filter(q => q.topic === l.id); if (!qs.length) return null; const tried = qs.filter(q => answers[`practice:${q.id}`] || answers[`cards:${q.id}`]); const ok = tried.filter(q => (answers[`practice:${q.id}`] ?? answers[`cards:${q.id}`]).rating === "know"); return <article className="science-progress-topic" key={l.id}><h2>{l.icon} {l.title}</h2><p>{tried.length}/{qs.length} vprašanj v vaji · {ok.length} znam</p><progress aria-label={`Znam: ${l.title}`} value={ok.length} max={qs.length} /><details><summary>Poglej vprašanja za ponovitev</summary>{tried.filter(q => !ok.includes(q)).map(q => <p key={q.id}><b>{labels[(answers[`practice:${q.id}`] ?? answers[`cards:${q.id}`]).rating]}:</b> {q.prompt}</p>)}{tried.length === ok.length && <p>Tu trenutno ni šibkejših odgovorov. Razišči še druga vprašanja.</p>}</details><button onClick={() => { setLesson(l.id); setView("study"); }} className="science-text-button">Odpri razlago <ArrowRight size={16} /></button></article>; })}
    </section> : <section className="science-study"><h1>Viri in opombe</h1><p>Učna zbirka iz {bank.sources.length} fotografij. Razlage so napisane na novo, slike pa ostanejo povezane z izvirnim gradivom.</p>{bank.review_notes.map(n => <p key={n} className="science-hint">{n}</p>)}<h2>Pokritost snovi</h2><div className="overflow-x-auto"><table className="science-coverage"><thead><tr><th>Tema</th><th>Ustno</th><th>Kviz</th><th>Slike</th><th>Kartice</th></tr></thead><tbody>{bank.lessons.map(l => { const qs = bank.questions.filter(q => q.topic === l.id); return <tr key={l.id}><th>{l.title}</th><td>{qs.filter(q => q.kind === "oral").length}</td><td>{qs.filter(q => q.kind !== "oral").length}</td><td>{qs.filter(q => q.image).length}</td><td>{qs.filter(q => q.card).length}</td></tr>; })}</tbody></table></div>
      {bank.sources.filter(s => group === "review" ? bank.questions.some(q => q.sources.includes(s.id)) : s.group === group).map(s => <details key={s.id} className="science-details"><summary>{s.review ? "⚑ " : "✓ "}{s.label} · {s.id}</summary>{s.review && <p className="science-hint">Za pregled: {s.review}</p>}<p className="text-sm">{bank.lessons.filter(l => l.sources.includes(s.id)).map(l => l.title).join(" · ")}</p><p className="text-sm">Vprašanja: {bank.questions.filter(q => q.sources.includes(s.id)).map(q => q.id).join(", ") || "Uvod ali ponovitev; vsebina je vključena prek povezanih razlag."}</p><SourcePicture picture={{source:s.id,box:[0,0,s.rotate?s.height:s.width,s.rotate?s.width:s.height],alt:s.label}} sources={bank.sources} base={base} /></details>)}
    </section>}
    <footer className="science-footer"><Check size={16} />{owner ? "Napredek se shrani v tvojo učilnico." : "Predogled za starše."} Brez hitenja. Po tvoje.</footer>
  </main>;
}
