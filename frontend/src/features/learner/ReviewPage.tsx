/** Moje napake: today's tricky tasks again, one by one (the same player as the practice). A parent's look is a preview. */
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Feedback } from "@/components/kid";
import { ErrorState, PageLoader } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { qk, ucApi, useLearnerHome, useReview, type TaskResult, type Topic } from "../learning/api";
import { LangContext, useT } from "../learning/i18n";
import { FullScreen } from "../learning/ui";
import { PracticePlayer } from "./PracticePlayer";

export default function ReviewPage() {
  const { lid: lidParam = "" } = useParams();
  const home = useLearnerHome(Number(lidParam) || 0);
  return (
    <LangContext.Provider value={home.data && !home.data.owner ? home.data.lang : null}>
      <Review />
    </LangContext.Provider>
  );
}

function Review() {
  const { lid: lidParam = "" } = useParams();
  const lid = Number(lidParam) || 0;
  const review = useReview(lid);
  const home = useLearnerHome(lid);
  const { t } = useT();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const owner = !!home.data?.owner;
  const items = review.data?.items;
  // One "topic" made of today's items (task ids are the review item ids, so the answers map back). Frozen on
  // first load, so saving answers (which refreshes the list) doesn't change the tasks mid-way.
  const [topic, setTopic] = useState<Topic | null | undefined>(undefined);
  useEffect(() => {
    if (topic === undefined && items)
      setTopic(
        items.length
          ? { id: "review", version: 1, subject: "other", grade: 1, title: t("reviewTitle"), intro: "", tasks: items.map((i) => ({ ...i.task, id: `${i.id}`, extra: false })) }
          : null,
      );
  }, [items, topic, t]);

  const save = (results: Record<string, TaskResult>) => {
    if (!owner || !Object.keys(results).length) return;
    ucApi
      .answerReview(lid, results)
      .then(() => qc.invalidateQueries({ queryKey: qk.all }))
      .catch((e) => toast.error(errorMessage(e)));
  };

  return (
    <FullScreen title={`🔁 ${t("reviewTitle")}`} onClose={() => navigate(`/l/${lid}`)} closeLabel={t("leave")}>
      {review.isError ? (
        <ErrorState error={review.error} />
      ) : topic === undefined || !home.data ? (
        <PageLoader />
      ) : !topic ? (
        <Feedback>{t("reviewNone")}</Feedback>
      ) : (
        <>
          {!owner && <Feedback>{t("preview")}</Feedback>}
          <PracticePlayer topic={topic} onRunFinished={save} onPartial={save} onExit={() => navigate(`/l/${lid}`)} />
        </>
      )}
    </FullScreen>
  );
}
