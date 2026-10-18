/** One test: the countdown, about how ready, what's on it (per skill) and the plan up to it, day by day. */
import { CalendarDays } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { Feedback } from "@/components/kid";
import { ErrorState, PageLoader } from "@/components/ui/misc";
import { useExam, useLearnerHome } from "../learning/api";
import { formatDay, LangContext, useT } from "../learning/i18n";
import { FullScreen, SubjectBubble } from "../learning/ui";
import { daysLeftText, MasteryChip, ReadinessRing, StepRow } from "./progress";

export default function ExamPage() {
  const { lid: lidParam = "" } = useParams();
  const home = useLearnerHome(Number(lidParam) || 0);
  return (
    <LangContext.Provider value={home.data && !home.data.owner ? home.data.lang : null}>
      <Exam />
    </LangContext.Provider>
  );
}

function Exam() {
  const { lid: lidParam = "", eid: eidParam = "" } = useParams();
  const lid = Number(lidParam) || 0;
  const exam = useExam(lid, Number(eidParam) || 0);
  const { t, lang } = useT();
  const navigate = useNavigate();
  const e = exam.data;
  return (
    <FullScreen title={`📅 ${e?.title ?? t("myTests")}`} onClose={() => navigate(`/l/${lid}`)} closeLabel={t("back")}>
      {exam.isError ? (
        <ErrorState error={exam.error} />
      ) : !e ? (
        <PageLoader />
      ) : (
        <>
          <div className="flex items-center gap-4">
            <ReadinessRing value={e.readiness} size={92} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <SubjectBubble subject={e.subject} size="sm" />
                <h1 className="font-display text-3xl leading-tight">{e.title}</h1>
              </div>
              <p className="mt-1 flex items-center gap-1.5 text-muted-foreground">
                <CalendarDays className="size-4" /> {formatDay(e.exam_date, lang)} · {daysLeftText(t, e.days_left)}
              </p>
              <p className="text-sm text-muted-foreground">{e.readiness === null ? t("readyUnknown") : t("ready", { n: Math.round(e.readiness * 100) })}</p>
            </div>
          </div>

          <section className="space-y-2">
            <h2 className="font-display text-xl">{t("skillsTitle")}</h2>
            {e.skills.map((s) => (
              <div key={`${s.topic_id}-${s.skill_id}`} className="flex items-center gap-3 rounded-2xl border border-border bg-card px-3 py-2.5">
                <span className="min-w-0 flex-1">
                  <span className="block font-medium leading-tight">{s.skill_id === "_topic" ? s.topic_title : s.title}</span>
                  {s.skill_id !== "_topic" && <span className="text-xs text-muted-foreground">{s.topic_title}</span>}
                </span>
                <MasteryChip label={s.label} />
              </div>
            ))}
          </section>

          <section className="space-y-3">
            <h2 className="font-display text-xl">{t("planTitle")}</h2>
            {e.plan.too_little_time && <Feedback tone="warn">{t("tooLittleTime")}</Feedback>}
            {e.plan.days.map((d, i) => (
              <div key={d.date} className="space-y-2">
                <div className="text-sm font-semibold text-muted-foreground">
                  {i === 0 ? t("todayPlan") : formatDay(d.date, lang)} · {t("minutesN", { n: d.minutes })}
                </div>
                {d.steps.map((s) => (
                  <StepRow key={s.key + d.date} lid={lid} step={i === 0 ? s : { ...s, done: false }} />
                ))}
              </div>
            ))}
          </section>
        </>
      )}
    </FullScreen>
  );
}
