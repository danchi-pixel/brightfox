import { ArrowRight, Lock, Play, RotateCcw, Trophy } from "lucide-react";
import { Link, useNavigate } from "react-router";
import { Feedback } from "@/components/kid";
import { todayISO } from "@/lib/dates";
import { cn } from "@/lib/utils";
import { useExam, useExams, useLearnerMocks, useMastery, type Exam, type MockCard, type ChallengeState, type LearnerTopicCard, type MasteryLabel } from "../learning/api";
import { formatDay, useT } from "../learning/i18n";
import { SUBJECT_META, SubjectBubble } from "../learning/ui";
import { daysLeftText, MasteryChip, ReadinessRing, StepRow } from "./progress";

function readinessLabel(v: number | null | undefined): MasteryLabel {
  if (v === null || v === undefined) return "not_started";
  return v >= 0.8 ? "know" : v >= 0.5 ? "almost" : "not_yet";
}

/** The next tests: countdown, about how ready, and today's steps for the nearest one. */
export function TestsCard({ lid, include = () => true }: { lid: number; include?: (exam: Exam) => boolean }) {
  const { t, lang } = useT();
  const exams = useExams(lid);
  const list = (exams.data ?? []).filter(include);
  const nearest = list[0];
  const detail = useExam(lid, nearest?.id ?? 0);
  if (!list.length) return null;
  const today = detail.data?.plan.days[0];
  const isToday = today && today.date === todayISO();
  return (
    <section className="space-y-3 rounded-3xl border-2 border-primary/30 bg-card p-4 sm:p-5">
      <h2 className="font-display text-2xl leading-tight">📅 {t("myTests")}</h2>
      {list.map((e) => (
        <Link key={e.id} to={`/l/${lid}/exam/${e.id}`} className="flex items-center gap-3 rounded-2xl bg-card-2 p-3 hover:opacity-90">
          <ReadinessRing value={e.readiness} size={64} />
          <span className="min-w-0 flex-1">
            <span className="block font-semibold leading-tight">{e.title}</span>
            <span className="block text-sm text-muted-foreground">
              {formatDay(e.exam_date, lang)} · <b className="text-foreground">{daysLeftText(t, e.days_left)}</b>
            </span>
          </span>
          <ArrowRight className="size-5 text-primary" />
        </Link>
      ))}
      {isToday && (
        <div className="space-y-2">
          <div className="text-sm font-semibold text-muted-foreground">
            {t("todayPlan")} · {nearest.title}
          </div>
          {today.steps.every((s) => s.done) ? (
            <Feedback>{t("planDone")}</Feedback>
          ) : (
            today.steps.map((s) => <StepRow key={s.key} lid={lid} step={s} />)
          )}
        </div>
      )}
    </section>
  );
}


/** Mock tests the parent approved: the last points, never a grade. */
export function MocksCard({ lid, include = () => true }: { lid: number; include?: (mock: MockCard) => boolean }) {
  const { t } = useT();
  const mocks = useLearnerMocks(lid);
  const navigate = useNavigate();
  const list = (mocks.data ?? []).filter(include);
  if (!list.length) return null;
  return (
    <section className="space-y-2 rounded-3xl border border-border bg-card p-4 sm:p-5">
      <h2 className="font-display text-2xl leading-tight">📝 {t("mocks")}</h2>
      {list.map((m) => (
        <button
          key={m.id}
          type="button"
          onClick={() => navigate(`/l/${lid}/mock/${m.id}`)}
          className="flex w-full items-center gap-3 rounded-2xl border-2 border-border bg-card-2 px-3 py-2.5 text-left transition hover:-translate-y-0.5"
        >
          <SubjectBubble subject={m.subject} size="sm" />
          <span className="min-w-0 flex-1">
            <span className="block font-semibold leading-tight">{m.title}</span>
            <span className="text-sm text-muted-foreground">
              {m.last ? t("mockLast", { p: m.last.points, max: m.last.max }) : t("mockIntro", { minutes: m.minutes, points: m.points })}
            </span>
          </span>
          <ArrowRight className="size-5 text-primary" />
        </button>
      ))}
    </section>
  );
}


export function TopicList({ lid, topics, preview, oralOk }: { lid: number; topics: LearnerTopicCard[]; preview: boolean; oralOk: boolean }) {
  const { t, lang } = useT();
  const navigate = useNavigate();
  const mastery = useMastery(lid);
  const mocks = useLearnerMocks(lid);
  const ready = new Map((mastery.data?.topics ?? []).map((m) => [m.topic_id, m.readiness]));
  return (
    <section className="space-y-3 rounded-3xl border border-border bg-card p-4 sm:p-5">
      <div>
        <h2 className="font-display text-2xl leading-tight">{t("topics")}</h2>
        <p className="text-sm text-muted-foreground">{t("topicsSub")}</p>
      </div>
      {!topics.length ? (
        <p className="rounded-2xl bg-card-2 px-4 py-3 text-muted-foreground">{t("noTopics")}</p>
      ) : (
        <div className="divide-y divide-border/60">
          {topics.map((s) => {
            const status = s.finished ? t("statusDone") : s.runs ? t("statusStarted") : t("statusNew");
            return (
              <div key={s.id} className="space-y-2 py-3">
                <div className="flex items-center gap-3">
                  <SubjectBubble subject={s.subject} />
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold leading-tight">{s.title}</div>
                    <div className="flex flex-wrap items-center gap-x-2 text-sm text-muted-foreground">
                      <span>{t(SUBJECT_META[s.subject].key)}</span>·<span>{t("tasksN", { n: s.tasks })}</span>·
                      <span className={s.runs ? undefined : "font-semibold text-primary"}>{status}</span>
                    </div>
                  </div>
                  {mastery.data && <MasteryChip label={readinessLabel(ready.get(s.id))} />}
                </div>
                {s.study_state && (
                  <PathRow
                    icon="📖"
                    title={t("learnTitle")}
                    sub={`${t("learnRow")}${s.study_state.cards ? ` · ${s.study_state.known.length}/${s.study_state.cards}` : ""}`}
                    tone="info"
                    onClick={() => navigate(`/l/${lid}/learn/${s.id}`)}
                  />
                )}
                <PathRow
                  icon="✏️"
                  title={t("practice")}
                  sub={s.finished ? t("doAgain") : t("start")}
                  tone="primary"
                  trailing={s.finished ? <RotateCcw className="size-5 text-muted-foreground" /> : <Play className="size-5 text-primary" />}
                  onClick={() => navigate(`/l/${lid}/practice/${s.id}`)}
                />
                {s.challenge_state && (
                  <ChallengeRow state={s.challenge_state} preview={preview} onPlay={() => navigate(`/l/${lid}/practice/${s.id}?challenge=1`)} />
                )}
                {s.oral > 0 && oralOk && (
                  <PathRow icon="🎤" title={t("oralTitle")} sub={t("oralRow")} tone="info" onClick={() => navigate(`/l/${lid}/oral/${s.id}`)} />
                )}
                {mocks.data?.filter((m) => m.topics.includes(s.id)).map((m) => (
                  <PathRow
                    key={m.id}
                    icon="📝"
                    title={m.title}
                    sub={m.last ? t("mockLast", { p: m.last.points, max: m.last.max }) : t("mockIntro", { minutes: m.minutes, points: m.points })}
                    tone="info"
                    onClick={() => navigate(`/l/${lid}/mock/${m.id}`)}
                  />
                ))}
                {s.last && <p className="ml-15 text-xs text-muted-foreground">{formatDay(s.last, lang)}</p>}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function PathRow({ icon, title, sub, tone, onClick, trailing }: { icon: string; title: string; sub: string; tone: "info" | "primary"; onClick: () => void; trailing?: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "ml-15 flex w-[calc(100%-3.75rem)] items-center gap-3 rounded-2xl border-2 px-3 py-2.5 text-left transition hover:-translate-y-0.5",
        tone === "info" ? "border-info/40 bg-info/10" : "border-primary/30 bg-primary-soft",
      )}
    >
      <span className="text-2xl" aria-hidden>
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-semibold leading-tight">{title}</span>
        <span className="text-sm text-muted-foreground">{sub}</span>
      </span>
      {trailing ?? <ArrowRight className={cn("size-5", tone === "info" ? "text-info" : "text-primary")} />}
    </button>
  );
}

/** The "Liga prvakov" level of a topic: locked until the practice is finished, then a trophy to win. */
function ChallengeRow({ state, preview, onPlay }: { state: ChallengeState; preview: boolean; onPlay: () => void }) {
  const { t } = useT();
  if (!state.unlocked)
    return (
      <button
        type="button"
        disabled={!preview}
        onClick={onPlay}
        className="ml-15 flex w-[calc(100%-3.75rem)] items-center gap-2 rounded-2xl bg-card-2 px-3 py-2 text-left text-sm text-muted-foreground enabled:hover:bg-muted"
      >
        <Lock className="size-4 shrink-0" /> {t("challengeTitle")}: {t("challengeLocked")}
        {preview && <span className="ml-auto shrink-0 font-medium text-primary">{t("previewWord")}</span>}
      </button>
    );
  return (
    <button
      type="button"
      onClick={onPlay}
      className={cn(
        "ml-15 flex w-[calc(100%-3.75rem)] items-center gap-3 rounded-2xl border-2 px-3 py-2.5 text-left transition hover:-translate-y-0.5",
        state.cleared ? "border-warning/40 bg-warning/10" : "border-warning bg-warning/15",
      )}
    >
      <Trophy className={cn("size-7 shrink-0 text-warning", !state.cleared && "animate-pulse")} />
      <span className="min-w-0 flex-1">
        <span className="block font-semibold leading-tight">{t("challengeTitle")}</span>
        <span className="text-sm text-muted-foreground">{state.cleared ? t("challengeWon") : t("challengeStart")}</span>
      </span>
      {state.cleared ? <RotateCcw className="size-5 text-muted-foreground" /> : <ArrowRight className="size-5 text-warning" />}
    </button>
  );
}

