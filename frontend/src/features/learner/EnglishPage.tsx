import { ArrowRight, BookOpen, Check, ClipboardList, MessageCircle, Trophy } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router";
import { Button } from "@/components/ui/button";
import { ErrorState, PageLoader } from "@/components/ui/misc";
import { useExams, useLearnerHome, useLearnerMocks, useMastery } from "../learning/api";
import { englishExam, englishMock } from "../learning/english";
import { LangContext } from "../learning/i18n";
import { StudyHubHeader, StudyHubHero, StudyHubNav } from "../learning/StudyHub";
import { MocksCard, TestsCard, TopicList } from "./ClassroomContent";
import { ReadinessRing } from "./progress";

const views = [["home", "Raziskuj"], ["study", "Učenje po temah"], ["tests", "Testi in priprava"], ["progress", "Moj napredek"]] as const;

/** A view over existing learner content. No copied questions or separate progress store. */
export default function EnglishPage() {
  const { lid: param = "" } = useParams();
  const lid = Number(param) || 0;
  const home = useLearnerHome(lid);
  const mocks = useLearnerMocks(lid);
  const exams = useExams(lid);
  const mastery = useMastery(lid);
  const [params, setParams] = useSearchParams();
  const view = views.some(([id]) => id === params.get("view")) ? params.get("view")! : "home";
  const selected = params.get("topic") ?? "all";
  function navigate(next: string, topic = "all") {
    setParams({ view: next, ...(topic !== "all" ? { topic } : {}) });
    window.scrollTo(0, 0);
  }
  if (home.isError) return <ErrorState error={home.error} onRetry={() => void home.refetch()} />;
  if (!home.data) return <PageLoader />;
  const h = home.data;
  const topics = h.topics.filter(t => t.subject === "english");
  const ids = new Set(topics.map(t => t.id));
  const englishMocks = (mocks.data ?? []).filter(m => englishMock(m, ids));
  const englishExams = (exams.data ?? []).filter(e => englishExam(e, ids));
  const known = topics.reduce((n, t) => n + (t.study_state?.known.length ?? 0), 0);
  const cards = topics.reduce((n, t) => n + (t.study_state?.cards ?? 0), 0);
  const filtered = selected === "all" || !ids.has(selected) ? topics : topics.filter(t => t.id === selected);
  const contentError = mocks.error || exams.error;
  const topicList = <TopicList lid={lid} topics={filtered} preview={!h.owner} oralOk={h.owner && h.tutor.configured && h.tutor.enabled} />;

  return <LangContext.Provider value="sl"><main className="science-shell" lang="sl">
    <StudyHubHeader lid={lid} />
    {!h.owner && <p className="science-preview">Starševski predogled. Poskusi se ne shranijo v otrokov napredek.</p>}
    <StudyHubNav label="Angleščina" items={views} current={view} onSelect={navigate} />
    {contentError && <ErrorState error={contentError} onRetry={() => { void mocks.refetch(); void exams.refetch(); }} />}
    {view === "home" ? <>
      <StudyHubHero title="Angleščina" eyebrow="Besede · zgodbe · pogovori" greeting={`Živjo, ${h.learner.name}! Raziščiva angleščino!`} description="Učne teme, kartice, vaje in testi so zdaj skupaj. Izberi temo in nadaljuj svojo učno pot." symbols={["💬", "📖", "✨"]}>
        <Button size="lg" variant="primary" onClick={() => navigate("study")}><BookOpen />Uči se in vadi</Button>
        <Button size="lg" variant="outline" onClick={() => navigate("tests")}>Odpri teste <ArrowRight /></Button>
      </StudyHubHero>
      <div className="science-stats"><span><b>{topics.length}</b>učnih tem</span><span><b>{known}/{cards}</b>kartic znam</span><span><b>{englishMocks.length + englishExams.length}</b>testov in priprav</span></div>
      <section className="science-modes" aria-label="Načini učenja">
        <button className="science-mode" onClick={() => navigate("study")}><span className="science-mode-icon"><BookOpen /></span><span><b>Učenje po temah</b><small>Razlage, kartice, vaje in Liga prvakov.</small></span><ArrowRight /></button>
        <button className="science-mode tone-1" onClick={() => navigate("tests")}><span className="science-mode-icon"><ClipboardList /></span><span><b>Testi in priprava</b><small>Poskusni testi, datumi in tvoj načrt učenja.</small></span><ArrowRight /></button>
        <button className="science-mode" onClick={() => navigate("progress")}><span className="science-mode-icon"><Trophy /></span><span><b>Moj napredek</b><small>Kartice, opravljene vaje in osvojeni pokali.</small></span><ArrowRight /></button>
      </section>
      <div className="science-section-heading"><h2>Izberi svojo temo</h2><span>Vsaka tema ima svojo učno pot.</span></div>
      <section className="science-topics">{topics.map((t, i) => <button key={t.id} onClick={() => navigate("study", t.id)}><span className="science-topic-icon" aria-hidden>📖</span><small>{String(i + 1).padStart(2, "0")}</small><h3>{t.title}</h3><p>{t.intro}</p><span className="science-topic-link">Odpri temo <ArrowRight size={16} /></span></button>)}</section>
      {!topics.length && <p className="science-hint">Tu se prikažejo tvoje teme iz angleščine.</p>}
      <div className="mt-6 space-y-4"><MocksCard lid={lid} include={m => englishMock(m, ids)} /><TestsCard lid={lid} include={e => englishExam(e, ids)} /></div>
    </> : view === "study" ? <section className="science-study">
      <h1>Učenje po temah</h1><p>Izberi razlago, kartice, vajo ali izziv v svoji temi.</p>
      <label className="block my-5">Izberi temo<select value={ids.has(selected) ? selected : "all"} onChange={e => navigate("study", e.target.value)}><option value="all">Vse teme po vrsti</option>{topics.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}</select></label>
      {topicList}
    </section> : view === "tests" ? <section className="science-study space-y-5"><h1>Testi in priprava</h1><p>Vsak test odpri posebej. Tvoji dosedanji rezultati ostanejo shranjeni.</p>
      {(mocks.isPending || exams.isPending) && <p role="status">Nalagam teste …</p>}
      <MocksCard lid={lid} include={m => englishMock(m, ids)} /><TestsCard lid={lid} include={e => englishExam(e, ids)} />
      {!contentError && mocks.data && exams.data && !englishMocks.length && !englishExams.length && <p className="science-hint">Trenutno ni testov iz angleščine. Znanje lahko preveriš v vajah po temah.</p>}
    </section> : <section className="science-study"><h1>Moj napredek</h1><p>Tvoj napredek iz obstoječih vaj, kartic in izzivov.</p>
      {mastery.isError && <ErrorState error={mastery.error} onRetry={() => void mastery.refetch()} />}
      {topics.map(t => <article className="science-progress-topic" key={t.id}><h2>{t.title}</h2><div className="flex flex-wrap items-center gap-5"><ReadinessRing value={mastery.data?.topics.find(m => m.topic_id === t.id)?.readiness ?? null} /><div><p>Kartice: {t.study_state?.known.length ?? 0}/{t.study_state?.cards ?? 0}</p><p>Zaključene vaje: {t.finished} · Vsi poskusi: {t.runs}</p>{t.challenge_state?.cleared && <p>🏆 Pokal Lige prvakov</p>}</div></div><button className="science-text-button" onClick={() => navigate("study", t.id)}>Nadaljuj učenje <ArrowRight size={16} /></button></article>)}
      <MocksCard lid={lid} include={m => englishMock(m, ids)} />
      <Link className="science-text-button" to={`/l/${lid}/review`}>Moje napake iz vseh predmetov <ArrowRight size={16} /></Link>
    </section>}
    {h.owner && h.tutor.configured && h.tutor.enabled && <Link className="science-text-button mt-6" to={`/l/${lid}/chat/new?subject=english`}><MessageCircle size={18} />Vprašaj Foxyja o angleščini</Link>}
    <footer className="science-footer"><Check size={16} />Brez hitenja. Po tvoje.</footer>
  </main></LangContext.Provider>;
}
