/** A topic for the practice and learning screens: from the learner's space, or (a parent's studio preview)
 * from the studio, which shows any topic of the family before it is approved. */
import { useParams } from "react-router";
import { useLearnerHome, useLearnerTopic, useStudioTopic } from "../learning/api";
import type { Lang } from "../learning/i18n";

export function useTopicScreen() {
  const { lid: lidParam = "", tid = "" } = useParams();
  const preview = !lidParam; // /preview/:tid has no learner
  const lid = preview ? 0 : Number(lidParam) || 0;
  const learnerTopic = useLearnerTopic(lid, tid, !preview);
  const studio = useStudioTopic(preview ? tid : null);
  const home = useLearnerHome(preview ? null : lid);
  const topic = preview ? studio.data?.topic : learnerTopic.data;
  const error = preview ? studio.error : learnerTopic.error || home.error;
  const owner = !preview && !!home.data?.owner;
  // A parent looking at a learner's space sees it in the learner's language.
  const lang: Lang | null = !preview && home.data && !home.data.owner ? home.data.lang : null;
  const loading = !topic || (!preview && !home.data);
  const homePath = preview ? "/topics" : `/l/${lid}`;
  return { lid, tid, preview, topic, home: home.data, error, owner, lang, loading, homePath };
}
