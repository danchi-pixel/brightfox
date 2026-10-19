/**
 * A learner's classroom: their topics (📖 Uči se → ✏️ Vaja → 🏆 Liga prvakov), Foxy, and their chats.
 * Nothing is scored; a topic shows "new", "started" or "done", flashcards known and the trophy.
 */
import { ArrowRight, Eye, Lock, MessageCircle, Play, RotateCcw, Trophy } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router";
import { Feedback } from "@/components/kid";
import { Button } from "@/components/ui/button";
import { ErrorState, PageLoader } from "@/components/ui/misc";
import { useAuth } from "@/lib/auth";
import { todayISO } from "@/lib/dates";
import { cn } from "@/lib/utils";
import {
  SUBJECTS,
  useExam,
  useExams,
  useLearnerHome,
  useLearnerMocks,
  useMastery,
  useReview,
  useWeek,
  type ChallengeState,
  type LearnerHome as Home,
  type LearnerTopicCard,
  type MasteryLabel,
  type Subject,
} from "../learning/api";
import { formatDay, gradeText, LangContext, useT } from "../learning/i18n";
import { LearnerAvatar, FoxAvatar, SUBJECT_META, SubjectBubble } from "../learning/ui";
import { daysLeftText, MasteryChip, ReadinessRing, StepRow, WeekDots } from "./progress";

export default function LearnerHome() {
  const { lid: lidParam = "" } = useParams();
  const lid = Number(lidParam) || 0;
  const home = useLearnerHome(lid);
  const { isAdmin } = useAuth();

  if (home.isError) return <ErrorState error={home.error} onRetry={() => void home.refetch()} />;
  if (!home.data) return <PageLoader />;
  const h = home.data;

  return (
    <LangContext.Provider value={h.owner ? null : h.lang}>
      <div className="mx-auto max-w-3xl space-y-6">
        {isAdmin && (
          <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-info/30 bg-info/10 px-4 py-3 text-sm">
            <Eye className="size-5 shrink-0 text-info" />
            <span className="min-w-0 flex-1">
              This is <b>{h.learner.name}</b>'s classroom, as {h.learner.name} sees it. Anything you try here is a preview and isn't saved.
            </span>
            <Link to="/" className="font-medium text-primary underline">
              Back to the overview
            </Link>
          </div>
        )}
        <Heading home={h} />
        <TestsCard lid={lid} />
        <ReviewCard lid={lid} />
        <TopicList lid={lid} topics={h.topics} preview={!h.owner} oralOk={h.owner && h.tutor.configured && h.tutor.enabled} />
        <MocksCard lid={lid} />
        <TutorCard lid={lid} home={h} />
        <WeekCard lid={lid} />
        {h.chats.length > 0 && <ChatList lid={lid} home={h} />}
      </div>
    </LangContext.Provider>
  );
}

function Heading({ home }: { home: Home }) {
  const { t } = useT();
  return (
    <div className="flex items-center gap-4">
      <LearnerAvatar learner={home.learner} size="lg" />
      <div>
        <h1 className="font-display text-4xl leading-none">{t("appName")}</h1>
        <p className="mt-1.5 text-muted-foreground">
          {t("tagline")}
          {home.learner.grade ? ` · ${gradeText(t, home.learner.grade)}` : ""}
        </p>
      </div>
    </div>
  );
}

function readinessLabel(v: number | null | undefined): MasteryLabel {
  if (v === null || v === undefined) return "not_started";
  return v >= 0.8 ? "know" : v >= 0.5 ? "almost" : "not_yet";
}

/** The next tests: countdown, about how ready, and today's steps for the nearest one. */
function TestsCard({ lid }: { lid: number }) {
  const { t, lang } = useT();
  const exams = useExams(lid);
  const list = exams.data ?? [];
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

function ReviewCard({ lid }: { lid: number }) {
  const { t } = useT();
  const review = useReview(lid);
  const navigate = useNavigate();
  const r = review.data;
  if (!r || (!r.open && !r.cleared)) return null;
  return (
    <section className="flex flex-wrap items-center gap-3 rounded-3xl border border-border bg-card p-4 sm:p-5">
      <span className="text-3xl" aria-hidden>
        🔁
      </span>
      <div className="min-w-0 flex-1">
        <h2 className="font-display text-xl leading-tight">{t("reviewTitle")}</h2>
        <p className="text-sm text-muted-foreground">
          {r.items.length ? t("reviewDue", { n: r.items.length }) : t("reviewNone")} · {t("corrected", { n: r.cleared })}
        </p>
      </div>
      {r.items.length > 0 && (
        <Button variant="primary" onClick={() => navigate(`/l/${lid}/review`)}>
          {t("reviewStart")} <ArrowRight />
        </Button>
      )}
    </section>
  );
}

/** Mock tests the parent approved: the last points, never a grade. */
function MocksCard({ lid }: { lid: number }) {
  const { t } = useT();
  const mocks = useLearnerMocks(lid);
  const navigate = useNavigate();
  if (!mocks.data?.length) return null;
  return (
    <section className="space-y-2 rounded-3xl border border-border bg-card p-4 sm:p-5">
      <h2 className="font-display text-2xl leading-tight">📝 {t("mocks")}</h2>
      {mocks.data.map((m) => (
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

function WeekCard({ lid }: { lid: number }) {
  const { t } = useT();
  const week = useWeek(lid);
  if (!week.data) return null;
  return (
    <section className="space-y-3 rounded-3xl border border-border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-xl">{t("thisWeek")}</h2>
        <span className="text-sm text-muted-foreground">{t("trophies", { cups: week.data.trophies.cups, fixed: week.data.trophies.corrected })}</span>
      </div>
      <WeekDots week={week.data} />
    </section>
  );
}

function TopicList({ lid, topics, preview, oralOk }: { lid: number; topics: LearnerTopicCard[]; preview: boolean; oralOk: boolean }) {
  const { t, lang } = useT();
  const navigate = useNavigate();
  const mastery = useMastery(lid);
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
                {s.video > 0 && (
                  <PathRow icon="🎬" title={t("videoTitle")} sub={t("videoRow")} tone="info" onClick={() => navigate(`/l/${lid}/video/${s.id}`)} />
                )}
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

function TutorCard({ lid, home }: { lid: number; home: Home }) {
  const { t } = useT();
  const navigate = useNavigate();
  const { configured, enabled, left_today } = home.tutor;
  const off = !configured || (home.owner && !enabled);
  const none = home.owner && left_today === 0;
  return (
    <section className="space-y-4 rounded-3xl border-2 border-primary/30 bg-card p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <FoxAvatar size="lg" />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-2xl leading-tight">{t("askFoxy")}</h2>
          <p className="text-muted-foreground">{t("askFoxyText")}</p>
        </div>
      </div>
      {off ? (
        <Feedback tone="soft">{configured ? t("switchedOff") : t("notReady")}</Feedback>
      ) : none ? (
        <Feedback tone="soft">{t("noneLeft")}</Feedback>
      ) : (
        <>
          <div className="text-sm font-semibold text-muted-foreground">{t("pickSubject")}</div>
          <SubjectPicker onPick={(s) => navigate(`/l/${lid}/chat/new?subject=${s}`)} />
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>{t("parentsCanRead")}</span>
            {home.owner && <span>{t("leftToday", { n: left_today })}</span>}
          </div>
        </>
      )}
    </section>
  );
}

export function SubjectPicker({ onPick, disabled }: { onPick: (s: Subject) => void; disabled?: boolean }) {
  const { t } = useT();
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {SUBJECTS.map((s) => (
        <button
          key={s}
          type="button"
          disabled={disabled}
          onClick={() => onPick(s)}
          className="flex flex-col items-center gap-1.5 rounded-2xl border-2 border-border bg-card px-2 py-3 text-center text-[15px] font-semibold transition hover:-translate-y-0.5 hover:border-input disabled:pointer-events-none disabled:opacity-50 sm:flex-row sm:gap-2.5 sm:px-3 sm:py-2.5 sm:text-left sm:text-base"
        >
          <SubjectBubble subject={s} size="sm" />
          <span className="min-w-0 break-words">{t(SUBJECT_META[s].key)}</span>
        </button>
      ))}
    </div>
  );
}

function ChatList({ lid, home }: { lid: number; home: Home }) {
  const { t, lang } = useT();
  return (
    <section className="space-y-2 rounded-3xl border border-border bg-card p-4 sm:p-5">
      <h2 className="flex items-center gap-2 font-display text-xl">
        <MessageCircle className="size-5 text-primary" /> {t("myChats")}
      </h2>
      <div className="divide-y divide-border/60">
        {home.chats.slice(0, 12).map((c) => (
          <Link key={c.id} to={`/l/${lid}/chat/${c.id}`} className="flex items-center gap-3 py-2.5 hover:opacity-80">
            <SubjectBubble subject={c.subject} size="sm" />
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium">{c.title || t(SUBJECT_META[c.subject].key)}</div>
              <div className="text-xs text-muted-foreground">
                {formatDay(c.updated_at, lang)}
                {c.parent_test ? ` · ${t("parentTest")}` : ""}
              </div>
            </div>
            <ArrowRight className="size-4 text-muted-foreground" />
          </Link>
        ))}
      </div>
    </section>
  );
}
