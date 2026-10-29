/**
 * Topics (parents): check each topic (answers listed, or try it as a preview), approve the version for the
 * learners who should get it, and see how each learner got on, task by task, with what they typed.
 */
import { useQueryClient } from "@tanstack/react-query";
import { BarChart3, CheckCircle2, ClipboardCheck, Eye, GraduationCap, HeartHandshake, Play, Printer, Trophy } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, EmptyState, ErrorState, PageLoader } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  goalList,
  qk,
  ucApi,
  useOverview,
  useStudioMock,
  useStudioMocks,
  useStudioTopic,
  useStudioTopics,
  useTopicResults,
  type LearnerBrief,
  type ParentCard,
  type RunSummary,
  type Task,
  type Topic,
  type TopicResults,
} from "../learning/api";
import { formatDay } from "../learning/i18n";
import { LearnerAvatar, SubjectBubble } from "../learning/ui";
import { ApprovalBadge, gradeName, PageTitle, subjectName } from "./common";

export default function TopicsPage() {
  const list = useStudioTopics();
  const overview = useOverview();
  const [params, setParams] = useSearchParams();
  const topics = list.data?.topics ?? [];
  const selected = params.get("id") ?? topics[0]?.id ?? null;
  const select = (id: string) => setParams({ id }, { replace: true });

  return (
    <div className="space-y-5">
      <PageTitle title="Topics" sub={overview.data?.local_auto_assignment
        ? "Local classroom: assigned topics and mock tests appear automatically after refresh. Approval controls are for preparing publication."
        : "Study pages, practice and challenges. Kids see a topic after you approve its current version."} />
      {list.isError ? (
        <ErrorState error={list.error} onRetry={() => void list.refetch()} />
      ) : !list.data || !overview.data ? (
        <PageLoader />
      ) : !topics.length ? (
        <EmptyState icon={<GraduationCap />} title="No topics yet">
          Ask Claude to make one from photos of the textbook.
        </EmptyState>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
          <div className="space-y-1.5">
            {topics.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => select(c.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-2xl border-2 px-3 py-2.5 text-left transition-colors",
                  selected === c.id ? "border-primary bg-primary-soft" : "border-border bg-card hover:border-input",
                )}
              >
                <SubjectBubble subject={c.subject} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold leading-tight">{c.title}</span>
                  <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                    {subjectName(c.subject)} · {gradeName(c.grade, true)} · v{c.version}
                    {c.scope === "global" ? " · example" : ""} <ApprovalBadge card={c} />
                  </span>
                </span>
              </button>
            ))}
          </div>
          {selected && <TopicPanel key={selected} id={selected} learners={overview.data.learners} />}
        </div>
      )}
      {overview.data && <MockTests learners={overview.data.learners} />}
    </div>
  );
}

/** Mock tests: like a real test (timed, no hints). The kids see points; the grade estimate is for you. */
function MockTests({ learners }: { learners: LearnerBrief[] }) {
  const list = useStudioMocks();
  if (!list.data?.mocks.length) return null;
  return (
    <Card>
      <CardHeader title="Mock tests" icon={<ClipboardCheck />} />
      <div className="space-y-3 px-5 pb-5">
        <p className="text-sm text-muted-foreground">
          Written in the teacher's format (send Claude a photo of an old test to match it). Timed, no hints; the result feeds readiness, and a test's plan puts the mock on the second-to-last study day.
        </p>
        {list.data.mocks.map((m) => (
          <MockPanel key={m.id} id={m.id} learners={learners} />
        ))}
      </div>
    </Card>
  );
}

function MockPanel({ id, learners }: { id: string; learners: LearnerBrief[] }) {
  const q = useStudioMock(id);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [chosen, setChosen] = useState<number[] | null>(null);
  const [busy, setBusy] = useState(false);
  if (!q.data) return <PageLoader />;
  const m = q.data;
  const madeFor = new Set((m.for ?? []).map((n) => n.toLowerCase()));
  const current = [...m.learner_ids, ...m.outdated_ids];
  const picked = chosen ?? (current.length ? current : learners.filter((k) => madeFor.has(k.name.toLowerCase())).map((k) => k.id));
  const same = [...picked].sort().join() === [...m.learner_ids].sort().join() && !m.outdated_ids.length;
  const approve = async () => {
    setBusy(true);
    try {
      await ucApi.approveMock(id, m.version, picked);
      await qc.invalidateQueries({ queryKey: qk.all });
      setChosen(null);
      toast.success("Approved.");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-2 rounded-2xl border border-border bg-card-2 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <SubjectBubble subject={m.subject} size="sm" />
        <div className="min-w-0 flex-1">
          <div className="font-semibold leading-tight">{m.title}</div>
          <div className="text-xs text-muted-foreground">
            {m.tasks} tasks · {m.points} points · {m.minutes} min · v{m.version} <ApprovalBadge card={m} />
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={() => navigate(`/preview-mock/${id}`)}>
          <Play /> Preview
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {learners.map((k) => {
          const on = picked.includes(k.id);
          return (
            <button
              key={k.id}
              type="button"
              aria-pressed={on}
              onClick={() => setChosen(on ? picked.filter((x) => x !== k.id) : [...picked, k.id])}
              className={cn("inline-flex items-center gap-1.5 rounded-full border-2 px-2.5 py-1 text-xs font-medium", on ? "border-primary bg-primary-soft" : "border-border bg-card")}
            >
              <LearnerAvatar learner={k} size="xs" /> {k.name}
            </button>
          );
        })}
        {(!m.approved || !same) && (
          <Button variant="primary" size="sm" loading={busy} disabled={!picked.length} onClick={() => void approve()}>
            <CheckCircle2 /> Approve
          </Button>
        )}
      </div>
      {m.results.map((r) => (
        <div key={r.learner.id} className="text-sm">
          <b>{r.learner.name}</b> ({formatDay(r.date)}): {r.points} of {r.max} points ({r.pct} %) · grade estimate <b>{r.grade_estimate}</b>
          {r.minutes_used ? ` · ${r.minutes_used} min` : ""}
          {r.missed.length > 0 && <span className="text-muted-foreground"> · missed: {r.missed.map((x) => x.prompt.slice(0, 40)).join(" / ")}</span>}
        </div>
      ))}
    </div>
  );
}

function answerText(t: Task): string {
  if (t.kind === "choice") return t.options?.[Number(t.answer)] ?? "?";
  if (t.kind === "open") return "(the kid compares with the solution)";
  const extra = t.accept?.length ? ` (also: ${t.accept.join(", ")})` : "";
  return `${t.answer ?? ""}${t.unit ? ` ${t.unit}` : ""}${extra}`;
}

function TopicPanel({ id, learners }: { id: string; learners: LearnerBrief[] }) {
  const q = useStudioTopic(id);
  const results = useTopicResults(id);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [chosen, setChosen] = useState<number[] | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setChosen(null), [id]);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data) return <PageLoader />;
  const { topic, ...card } = q.data;
  // Not approved yet: start with the learners the topic was made for ("for" in the file).
  const madeFor = new Set((topic.for ?? []).map((n) => n.trim().toLowerCase()));
  const suggested = learners.filter((k) => madeFor.has(k.name.trim().toLowerCase())).map((k) => k.id);
  const current = [...card.learner_ids, ...card.outdated_ids];
  const picked = chosen ?? (current.length ? current : suggested);
  const same = [...picked].sort().join() === [...card.learner_ids].sort().join() && !card.outdated_ids.length;
  const pickedNames = learners.filter((k) => picked.includes(k.id)).map((k) => k.name);

  const approve = async () => {
    setBusy(true);
    try {
      await ucApi.approve(id, topic.version, picked);
      await qc.invalidateQueries({ queryKey: qk.all });
      setChosen(null);
      toast.success(`Approved. ${pickedNames.join(" and ")} can start it now.`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const unapprove = async () => {
    setBusy(true);
    try {
      await ucApi.unapprove(id);
      await qc.invalidateQueries({ queryKey: qk.all });
      toast.success("Approval removed. Nobody sees this topic now.");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <div className="space-y-3 p-4">
          <div className="flex flex-wrap items-start gap-3">
            <SubjectBubble subject={topic.subject} />
            <div className="min-w-0 flex-1">
              <div className="font-display text-2xl leading-tight">{topic.title}</div>
              <div className="mt-0.5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                {subjectName(topic.subject)} · {gradeName(topic.grade)} · version {topic.version} · {topic.tasks.length} tasks
                <ApprovalBadge card={card} />
              </div>
            </div>
            {topic.study && (
              <Button variant="secondary" size="sm" onClick={() => navigate(`/preview/${id}/learn`)}>
                📖 Study pages
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={() => navigate(`/preview/${id}`)}>
              <Play /> Preview
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">{topic.intro}</p>
          {topic.source && <p className="text-xs text-muted-foreground">Source: {topic.source}</p>}
          <div className="space-y-2 border-t border-border pt-3">
            <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Who gets it</div>
            {!learners.length ? (
              <p className="text-sm text-muted-foreground">No learners yet (add them on the Family page).</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {learners.map((k) => {
                  const on = picked.includes(k.id);
                  return (
                    <button
                      key={k.id}
                      type="button"
                      aria-pressed={on}
                      onClick={() => setChosen(on ? picked.filter((x) => x !== k.id) : [...picked, k.id])}
                      className={cn("inline-flex items-center gap-2 rounded-full border-2 px-3 py-1.5 text-sm font-medium", on ? "border-primary bg-primary-soft" : "border-border bg-card")}
                    >
                      <LearnerAvatar learner={k} size="xs" /> {k.name}
                      {on && <CheckCircle2 className="size-4 text-primary" />}
                    </button>
                  );
                })}
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2 pt-1">
              {(!card.approved || !same) && (
                <Button variant="primary" size={card.approved ? "sm" : "lg"} loading={busy} disabled={!picked.length} onClick={() => void approve()}>
                  <CheckCircle2 /> {!picked.length ? "Tap who gets it first" : card.approved ? "Save who gets it" : `Approve for ${pickedNames.join(" and ")}`}
                </Button>
              )}
              {card.approved && same && <span className="text-sm text-success">{pickedNames.join(" and ")} can use it now.</span>}
              {current.length > 0 && (
                <Button variant="ghost" size="sm" loading={busy} onClick={() => void unapprove()}>
                  Remove approval
                </Button>
              )}
            </div>
          </div>
        </div>
      </Card>

      {topic.parent && <ParentHelperCard title={topic.title} card={topic.parent} />}

      <LearnersResults topic={topic} results={results.data} />

      <Card>
        <CardHeader title="Tasks and answers" icon={<Eye />} />
        <TaskList tasks={topic.tasks} results={results.data} />
      </Card>

      {!!topic.challenge?.length && (
        <Card>
          <CardHeader
            title="Champions League level (Liga prvakov)"
            icon={<Trophy />}
            action={
              <Button variant="secondary" size="sm" onClick={() => navigate(`/preview/${id}?challenge=1`)}>
                <Play /> Preview
              </Button>
            }
          />
          <p className="-mt-1 px-5 pb-1 text-sm text-muted-foreground">
            Harder tasks that open after the practice is finished once: typing only, at most one hint. Finishing it wins a trophy.
          </p>
          <TaskList tasks={topic.challenge} results={results.data} />
        </Card>
      )}
    </div>
  );
}

/** How school teaches it, the typical mistakes and quick questions for the car. Printable. */
function ParentHelperCard({ title, card }: { title: string; card: ParentCard }) {
  return (
    <Card className="print:border-black/30">
      <CardHeader
        title="Helping at home"
        icon={<HeartHandshake />}
        action={
          <Button variant="ghost" size="sm" onClick={() => window.print()} className="print:hidden">
            <Printer /> Print
          </Button>
        }
      />
      <div className="space-y-3 px-5 pb-5 text-sm leading-relaxed">
        <div className="hidden font-semibold print:block">{title}</div>
        {card.school_method && <p>{card.school_method}</p>}
        {!!card.typical_mistakes?.length && (
          <div>
            <div className="font-semibold">Typical mistakes</div>
            <ul className="list-disc pl-5">
              {card.typical_mistakes.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        )}
        {!!card.car_questions?.length && (
          <div>
            <div className="font-semibold">Quick questions (car, dinner)</div>
            <ol className="list-decimal space-y-0.5 pl-5">
              {card.car_questions.map((q, i) => (
                <li key={i}>
                  {q.q} <span className="text-muted-foreground">→ {q.a}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
        {!!card.tips?.length && (
          <ul className="list-disc pl-5 text-muted-foreground">
            {card.tips.map((tip, i) => (
              <li key={i}>{tip}</li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

/** "How the kids did": each learner's latest run at a glance — right first time, and what they found hard (with what they typed). */
function LearnersResults({ topic, results }: { topic: Topic; results: TopicResults | undefined }) {
  const prompts = new Map([...topic.tasks, ...(topic.challenge ?? [])].map((t) => [t.id, t]));
  const goals = goalList(topic.study);
  const rows = results?.learners ?? [];
  return (
    <Card>
      <CardHeader title="How the kids did" icon={<BarChart3 />} />
      <div className="space-y-4 px-5 pb-5">
        {!rows.length ? (
          <p className="text-sm text-muted-foreground">Nobody has started this topic yet.</p>
        ) : (
          rows.map((p) => (
            <div key={p.learner.id} className="space-y-2 rounded-2xl border border-border bg-card-2 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <LearnerAvatar learner={p.learner} size="sm" />
                <span className="font-semibold">{p.learner.name}</span>
                <span className="text-sm text-muted-foreground">
                  {p.runs} run{p.runs === 1 ? "" : "s"} ({p.finished} finished){p.last ? ` · last ${formatDay(p.last)}` : ""}
                </span>
                {p.challenge && (
                  <span
                    className={cn(
                      "ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                      p.challenge.cleared ? "bg-warning/15 text-warning" : "bg-muted text-muted-foreground",
                    )}
                  >
                    <Trophy className="size-3.5" /> {p.challenge.cleared ? "Trophy won" : p.challenge.unlocked ? "Challenge open" : "Challenge locked"}
                  </span>
                )}
              </div>
              {p.study && (
                <div className="text-sm">
                  <b>Learn:</b> knows {p.study.known.length} of {p.study.cards} flashcards
                  {p.study.goals > 0 && (
                    <>
                      {" "}
                      · ticked {p.study.ticked.length} of {p.study.goals} "I can" goals
                      {p.study.ticked.length < p.study.goals && (
                        <span className="text-muted-foreground">
                          {" "}
                          (not yet:{" "}
                          {goals
                            .filter((g) => !p.study!.ticked.includes(g.id))
                            .map((g) => g.text)
                            .join(" / ")}
                          )
                        </span>
                      )}
                    </>
                  )}
                </div>
              )}
              <RunBox label="Practice" run={p.latest} prompts={prompts} />
              {p.challenge?.latest && <RunBox label="Champions League" run={p.challenge.latest} prompts={prompts} />}
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

function RunBox({ label, run, prompts }: { label: string; run: RunSummary | null; prompts: Map<string, Task> }) {
  if (!run) return null;
  return (
    <div className="space-y-1.5 text-sm">
      <div>
        <b>{label}</b> ({formatDay(run.date)}
        {run.finished ? "" : ", stopped half-way"}): right first time{" "}
        <b>
          {run.first} of {run.done}
        </b>
        {run.done < run.total ? ` (${run.total - run.done} not reached)` : ""}
      </div>
      {run.tricky.length > 0 && (
        <ul className="space-y-1">
          {run.tricky.map((x) => {
            const t = prompts.get(x.id);
            return (
              <li key={x.id} className="rounded-xl bg-card px-3 py-2">
                <div className="line-clamp-2">{t?.prompt ?? x.id}</div>
                <div className="text-xs text-muted-foreground">
                  {x.wrong.length > 0 && (
                    <>
                      Typed:{" "}
                      {x.wrong.map((w, i) => (
                        <span key={i} className="mr-1 rounded bg-danger/10 px-1 text-danger">
                          {w}
                        </span>
                      ))}
                    </>
                  )}
                  {t && t.kind !== "open" && (
                    <>
                      {" "}
                      → right: <b className="text-foreground">{t.kind === "choice" ? t.options?.[Number(t.answer)] : `${t.answer ?? ""}${t.unit ? ` ${t.unit}` : ""}`}</b>
                    </>
                  )}
                  {x.hints ? ` · ${x.hints} hint${x.hints > 1 ? "s" : ""}` : ""}
                  {x.shown ? " · needed the solution" : ""}
                  {t?.kind === "open" ? ' · said "not yet"' : ""}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function TaskList({ tasks, results }: { tasks: Task[]; results: TopicResults | undefined }) {
  return (
    <ol className="divide-y divide-border/60 px-5 pb-4">
      {tasks.map((t, i) => {
        const stats = results?.learners.map((p) => ({ name: p.learner.name, s: p.tasks[t.id] })).filter((x) => x.s?.seen);
        return (
          <li key={t.id} className="space-y-1 py-2.5 text-sm">
            <div className="flex gap-2">
              <span className="tabular w-6 shrink-0 text-muted-foreground">{i + 1}.</span>
              <div className="min-w-0 flex-1 space-y-1">
                <div>
                  <span className="mr-1.5 rounded bg-muted px-1.5 py-0.5 text-[11px] font-semibold uppercase text-muted-foreground">
                    {t.extra ? "bonus" : ["", "warm-up", "practice", "challenge"][t.level]} · {t.kind}
                    {t.say ? " · 🔊" : ""}
                  </span>
                  {t.prompt}
                </div>
                <div className="text-muted-foreground">
                  Answer: <b className="text-foreground">{answerText(t)}</b>
                  {t.hints?.length ? ` · ${t.hints.length} hint${t.hints.length > 1 ? "s" : ""}` : ""}
                  {t.traps?.length ? ` · ${t.traps.length} known trap${t.traps.length > 1 ? "s" : ""}` : ""}
                </div>
                {!!stats?.length && (
                  <div className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                    {stats.map((x) => (
                      <span key={x.name}>
                        {x.name}: right first time {x.s.first}/{x.s.seen}
                        {x.s.hints ? `, ${x.s.hints} hints` : ""}
                        {x.s.shown ? `, solution shown ${x.s.shown}×` : ""}
                        {x.s.not_yet ? `, "not yet" ${x.s.not_yet}×` : ""}
                        {x.s.wrong?.length ? `, typed: ${x.s.wrong.join(" / ")}` : ""}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
