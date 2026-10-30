/**
 * A learner's classroom: their topics (📖 Uči se → ✏️ Vaja → 🏆 Liga prvakov), Foxy, and their chats.
 * Nothing is scored; a topic shows "new", "started" or "done", flashcards known and the trophy.
 */
import { ArrowRight, Eye, MessageCircle } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router";
import { Feedback } from "@/components/kid";
import { Button } from "@/components/ui/button";
import { ErrorState, PageLoader } from "@/components/ui/misc";
import { useAuth } from "@/lib/auth";
import {
  SUBJECTS,
  useExams,
  useLearnerHome,
  useLearnerMocks,
  useReview,
  useWeek,
  type LearnerHome as Home,
  type Subject,
} from "../learning/api";
import { formatDay, gradeText, LangContext, useT } from "../learning/i18n";
import { LearnerAvatar, FoxAvatar, SUBJECT_META, SubjectBubble } from "../learning/ui";
import { WeekDots } from "./progress";
import { TestsCard, MocksCard, TopicList } from "./ClassroomContent";
import { StudyHubEntry } from "../learning/StudyHub";
import { englishPath, englishMock, englishExam } from "../learning/english";

export default function LearnerHome() {
  const { lid: lidParam = "" } = useParams();
  const lid = Number(lidParam) || 0;
  const home = useLearnerHome(lid);
  const mocks = useLearnerMocks(lid);
  const exams = useExams(lid);
  const { isAdmin } = useAuth();

  if (home.isError) return <ErrorState error={home.error} onRetry={() => void home.refetch()} />;
  if (!home.data) return <PageLoader />;
  const h = home.data;
  const englishIds = new Set(h.topics.filter(t => t.subject === "english").map(t => t.id));
  const hasEnglish = englishIds.size > 0 || mocks.data?.some(m => englishMock(m, englishIds)) || exams.data?.some(e => englishExam(e, englishIds));

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
        {h.topics.filter(topic => topic.has_lab && topic.subject !== "english").map(topic => <StudyHubEntry key={topic.id} to={`/l/${lid}/science/${topic.id}`} title={topic.title} description="Raziskuj teme, vadi ustno in se uči s slikami." icon="🌿" />)}
        {hasEnglish && <StudyHubEntry to={englishPath(lid)} title="Angleščina" description="Vse učne teme, kartice, vaje in testi na enem mestu." icon="💬" />}
        <TestsCard lid={lid} include={e => !englishExam(e, englishIds)} />
        <ReviewCard lid={lid} />
        <TopicList lid={lid} topics={h.topics.filter(t => t.subject !== "english" && !t.has_lab)} preview={!h.owner} oralOk={h.owner && h.tutor.configured && h.tutor.enabled} />
        <MocksCard lid={lid} include={m => !englishMock(m, englishIds)} />
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
