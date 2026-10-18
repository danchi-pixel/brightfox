/**
 * Full-screen practice. The learner's own account saves how each task went (also when leaving half-way);
 * a parent gets a preview (from the studio, any topic; or looking at a learner's space) that is never saved.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Feedback } from "@/components/kid";
import { ErrorState, PageLoader } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { qk, ucApi, type TaskResult } from "../learning/api";
import { LangContext, useT } from "../learning/i18n";
import { FullScreen } from "../learning/ui";
import { PracticePlayer } from "./PracticePlayer";
import { useTopicScreen } from "./useTopic";

export default function PracticePage() {
  const s = useTopicScreen();
  return (
    <LangContext.Provider value={s.lang}>
      <Practice s={s} />
    </LangContext.Provider>
  );
}

function Practice({ s }: { s: ReturnType<typeof useTopicScreen> }) {
  const [params] = useSearchParams();
  const challenge = params.get("challenge") === "1";
  // ?skill=<id> (from the test plan): only that skill's tasks, if the topic marks skills.
  const skill = params.get("skill");
  const topic = useMemo(() => {
    if (!s.topic || !skill) return s.topic;
    const tasks = s.topic.tasks.filter((x) => x.skill === skill);
    return tasks.length ? { ...s.topic, tasks, learn: [] } : s.topic;
  }, [s.topic, skill]);
  const { t } = useT();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const back = () => navigate(s.homePath);
  const card = s.home?.topics.find((x) => x.id === s.tid);
  // A learner opens the challenge only after finishing the practice (a parent may always preview it).
  const locked = challenge && s.owner && !card?.challenge_state?.unlocked;
  const owl = s.owner && s.home?.tutor.configured && s.home.tutor.enabled && s.home.tutor.left_today > 0;

  const save = (results: Record<string, TaskResult>, finished: boolean) => {
    if (!s.owner || !Object.keys(results).length) return;
    ucApi
      .run(s.lid, s.tid, results, finished, challenge)
      .then(() => qc.invalidateQueries({ queryKey: qk.all }))
      .catch((e) => toast.error(errorMessage(e)));
  };

  return (
    <FullScreen title={`${challenge ? t("challengeTitle") : t("practice")}${s.topic ? ` · ${s.topic.title}` : ""}`} onClose={back} closeLabel={t("leave")}>
      {s.error ? (
        <ErrorState error={s.error} />
      ) : s.loading ? (
        <PageLoader />
      ) : locked || (challenge && !topic!.challenge?.length) ? (
        <Feedback>{t("challengeLocked")}</Feedback>
      ) : (
        <>
          {!s.owner && <Feedback>{t("preview")}</Feedback>}
          <PracticePlayer
            topic={topic!}
            challenge={challenge}
            onRunFinished={(r) => save(r, true)}
            onPartial={(r) => save(r, false)}
            onExit={back}
            onAskFoxy={owl ? (taskId) => navigate(`/l/${s.lid}/chat/new?topic=${s.tid}&task=${taskId}`) : undefined}
          />
        </>
      )}
    </FullScreen>
  );
}
