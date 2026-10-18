/**
 * Tests and gaps (parents): enter a school test (date, what's on it, the grade aimed for); the kid then gets a
 * countdown, readiness and a daily plan. Below: what the kid still misses, worst first, with what they typed.
 */
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarPlus, Mic, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Field, Input, Select, Textarea } from "@/components/ui/input";
import { Card, CardHeader, EmptyState, ErrorState, PageLoader } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  qk,
  SUBJECTS,
  ucApi,
  useExams,
  useGaps,
  useLearnerHome,
  useOralSessions,
  useOverview,
  type Exam,
  type ExamIn,
  type Gap,
  type LearnerBrief,
} from "../learning/api";
import { formatDay } from "../learning/i18n";
import { LearnerAvatar } from "../learning/ui";
import { ReadinessRing } from "../learner/progress";
import { PageTitle, subjectName } from "./common";

export default function TestsPage() {
  const overview = useOverview();
  const [params, setParams] = useSearchParams();
  if (overview.isError) return <ErrorState error={overview.error} />;
  if (!overview.data) return <PageLoader />;
  const learners = overview.data.learners;
  if (!learners.length) return <EmptyState title="No learners yet" />;
  const lid = Number(params.get("learner")) || learners[0].id;
  const learner = learners.find((l) => l.id === lid) ?? learners[0];
  return (
    <div className="space-y-5">
      <PageTitle title="Tests and gaps" sub="Enter a test from school: the kid gets a countdown, about how ready they are, and a short plan for every day until then." />
      <div className="flex flex-wrap gap-2">
        {learners.map((k) => (
          <button
            key={k.id}
            type="button"
            aria-pressed={k.id === learner.id}
            onClick={() => setParams({ learner: String(k.id) }, { replace: true })}
            className={cn("inline-flex items-center gap-2 rounded-full border-2 px-3 py-1.5 text-sm font-medium", k.id === learner.id ? "border-primary bg-primary-soft" : "border-border bg-card")}
          >
            <LearnerAvatar learner={k} size="xs" /> {k.name}
          </button>
        ))}
      </div>
      <Tests key={learner.id} learner={learner} />
      <Gaps learner={learner} />
      <OralPractice learner={learner} />
    </div>
  );
}

function Tests({ learner }: { learner: LearnerBrief }) {
  const exams = useExams(learner.id);
  const qc = useQueryClient();
  const confirm = useConfirm();
  const [editing, setEditing] = useState<Exam | "new" | null>(null);
  const remove = async (e: Exam) => {
    if (!(await confirm({ title: `Delete "${e.title}"?`, confirmLabel: "Delete", danger: true }))) return;
    try {
      await ucApi.deleteExam(learner.id, e.id);
      await qc.invalidateQueries({ queryKey: qk.all });
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };
  return (
    <Card>
      <CardHeader
        title={`${learner.name}'s tests`}
        icon={<CalendarPlus />}
        action={
          <Button variant="primary" size="sm" onClick={() => setEditing("new")}>
            <CalendarPlus /> Add a test
          </Button>
        }
      />
      <div className="space-y-3 px-5 pb-5">
        {editing && <ExamForm learner={learner} exam={editing === "new" ? null : editing} onDone={() => setEditing(null)} />}
        {exams.isError ? (
          <ErrorState error={exams.error} />
        ) : !exams.data ? (
          <PageLoader />
        ) : !exams.data.length ? (
          !editing && <p className="text-sm text-muted-foreground">No upcoming tests.</p>
        ) : (
          exams.data.map((e) => (
            <div key={e.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-card-2 p-3">
              <ReadinessRing value={e.readiness} size={60} />
              <div className="min-w-0 flex-1">
                <div className="font-semibold">{e.title}</div>
                <div className="text-sm text-muted-foreground">
                  {formatDay(e.exam_date)} · in {e.days_left} day{e.days_left === 1 ? "" : "s"} · {subjectName(e.subject)}
                  {e.target_grade ? ` · aiming for a ${e.target_grade}` : ""}
                </div>
                <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
                  {e.skills.map((s) => (
                    <span key={`${s.topic_id}-${s.skill_id}`} className="rounded-full bg-card px-2 py-0.5">
                      {s.skill_id === "_topic" ? s.topic_title : s.title}: {s.mastery === null ? "not started" : `${Math.round(s.mastery * 100)} %`}
                    </span>
                  ))}
                </div>
              </div>
              <Button variant="ghost" size="icon-sm" aria-label="Edit test" onClick={() => setEditing(e)}>
                <Pencil />
              </Button>
              <Button variant="danger-ghost" size="icon-sm" aria-label="Delete test" onClick={() => void remove(e)}>
                <Trash2 />
              </Button>
            </div>
          ))
        )}
        <p className="text-xs text-muted-foreground">
          Readiness is an estimate from the practice (right first time), the Champions League, flashcards and "I can" goals of the topics on the test. Topics must be approved for {learner.name} first.
        </p>
      </div>
    </Card>
  );
}

function ExamForm({ learner, exam, onDone }: { learner: LearnerBrief; exam: Exam | null; onDone: () => void }) {
  const home = useLearnerHome(learner.id);
  const qc = useQueryClient();
  const [v, setV] = useState<ExamIn>(() => ({
    subject: exam?.subject ?? "math",
    title: exam?.title ?? "",
    exam_date: exam?.exam_date ?? "",
    kind: exam?.kind ?? "written",
    target_grade: exam?.target_grade ?? null,
    notes: exam?.notes ?? "",
    scope: exam?.scope.map((s) => ({ topic_id: s.topic_id, skill_id: s.skill_id })) ?? [],
  }));
  const [busy, setBusy] = useState(false);
  const topics = home.data?.topics ?? [];
  const picked = new Set(v.scope.map((s) => s.topic_id));
  const save = async () => {
    setBusy(true);
    try {
      if (exam) await ucApi.updateExam(learner.id, exam.id, v);
      else await ucApi.addExam(learner.id, v);
      await qc.invalidateQueries({ queryKey: qk.all });
      toast.success("Saved. The plan is ready on the kid's page.");
      onDone();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-3 rounded-2xl border-2 border-primary/30 p-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Test">
          <Input value={v.title} maxLength={80} placeholder="e.g. Ulomki, 1. test" onChange={(e) => setV({ ...v, title: e.target.value })} />
        </Field>
        <Field label="Date">
          <Input type="date" value={v.exam_date} onChange={(e) => setV({ ...v, exam_date: e.target.value })} />
        </Field>
        <Field label="Subject">
          <Select value={v.subject} onChange={(e) => setV({ ...v, subject: e.target.value as ExamIn["subject"] })}>
            {SUBJECTS.map((s) => (
              <option key={s} value={s}>
                {subjectName(s)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Aiming for">
          <Select value={v.target_grade ?? ""} onChange={(e) => setV({ ...v, target_grade: e.target.value ? Number(e.target.value) : null })}>
            <option value="">–</option>
            {[5, 4, 3, 2].map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="What's on it (approved topics)">
        {!topics.length ? (
          <p className="text-sm text-muted-foreground">Approve a topic for {learner.name} first (Topics page).</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {topics.map((t) => {
              const on = picked.has(t.id);
              return (
                <button
                  key={t.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setV({ ...v, scope: on ? v.scope.filter((s) => s.topic_id !== t.id) : [...v.scope, { topic_id: t.id }] })}
                  className={cn("rounded-full border-2 px-3 py-1.5 text-sm font-medium", on ? "border-primary bg-primary-soft" : "border-border bg-card")}
                >
                  {t.title}
                </button>
              );
            })}
          </div>
        )}
      </Field>
      <Field label="Notes (what the teacher said is on it)">
        <Textarea value={v.notes ?? ""} maxLength={1000} onChange={(e) => setV({ ...v, notes: e.target.value })} placeholder="e.g. Pages 34–40, word problems" />
      </Field>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={onDone}>
          Cancel
        </Button>
        <Button variant="primary" size="sm" loading={busy} disabled={!v.title.trim() || !v.exam_date || !v.scope.length} onClick={() => void save()}>
          {exam ? "Save" : "Add test"}
        </Button>
      </div>
    </div>
  );
}

const VERDICT_TEXT = { right: "✅ right", partly: "🙂 almost", not_yet: "❌ not yet" } as const;

/** Oral exam practice: what Foxy asked, what the kid typed, and his verdict. */
function OralPractice({ learner }: { learner: LearnerBrief }) {
  const sessions = useOralSessions(learner.id);
  if (!sessions.data?.length) return null;
  return (
    <Card>
      <CardHeader title={`${learner.name}'s oral exam practice`} icon={<Mic />} />
      <div className="space-y-3 px-5 pb-5">
        {sessions.data.slice(0, 5).map((s) => (
          <div key={s.id} className="space-y-1 rounded-2xl border border-border bg-card-2 p-3 text-sm">
            <div className="font-semibold">
              {s.topic_title} · {formatDay(s.date)}
            </div>
            {s.turns.map((tn, i) => (
              <div key={i}>
                <span className="text-muted-foreground">{tn.question}</span> → “{tn.answer}” <b>{VERDICT_TEXT[tn.verdict]}</b>
              </div>
            ))}
          </div>
        ))}
      </div>
    </Card>
  );
}

const SEVERITY_STYLE: Record<Gap["severity"], string> = {
  critical: "border-danger/40 bg-danger/5",
  attention: "border-warning/40 bg-warning/5",
  minor: "border-border bg-card-2",
};

function Gaps({ learner }: { learner: LearnerBrief }) {
  const gaps = useGaps(learner.id);
  const list = gaps.data?.gaps ?? [];
  return (
    <Card>
      <CardHeader title={`What ${learner.name} still misses`} icon={<AlertTriangle />} />
      <div className="space-y-2 px-5 pb-5">
        {gaps.isError ? (
          <ErrorState error={gaps.error} />
        ) : !gaps.data ? (
          <PageLoader />
        ) : !list.length ? (
          <p className="text-sm text-muted-foreground">No gaps found. 🎉</p>
        ) : (
          list.map((g, i) => (
            <div key={i} className={cn("rounded-2xl border px-3 py-2 text-sm", SEVERITY_STYLE[g.severity])}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wide">{g.severity === "critical" ? "🚨 critical" : g.severity === "attention" ? "⚠️ attention" : "💡 minor"}</span>
                <span className="font-medium">{g.title}</span>
                {g.topic_title && g.topic_title !== g.title && <span className="text-muted-foreground">· {g.topic_title}</span>}
              </div>
              <div className="text-muted-foreground">{g.reasons.join(" · ")}</div>
              {g.wrong.length > 0 && (
                <div className="mt-1 text-xs">
                  Typed:{" "}
                  {g.wrong.map((w, j) => (
                    <span key={j} className="mr-1 rounded bg-danger/10 px-1 text-danger">
                      {w}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
