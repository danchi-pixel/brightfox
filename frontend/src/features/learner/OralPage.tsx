/**
 * The oral exam ("Ustno spraševanje"), typed: Foxy reads each question aloud (the browser's voice; nothing is
 * recorded), the learner types the answer like they'd say it, and Foxy checks it against the key points.
 */
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Loader2, Volume2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Feedback } from "@/components/kid";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { ErrorState, PageLoader, Progress } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { qk, ucApi, useLearnerHome, type OralSession, type Verdict } from "../learning/api";
import { LangContext, useT, type Key } from "../learning/i18n";
import { CAN_SPEAK, speak } from "../learning/speech";
import { FullScreen, FoxAvatar, RichText } from "../learning/ui";
import { subjectHomePath } from "../learning/english";

const VERDICT_STYLE: Record<Verdict, string> = {
  right: "border-success/40 bg-success/10 text-success",
  partly: "border-warning/40 bg-warning/10 text-warning",
  not_yet: "border-danger/30 bg-danger/5 text-danger",
};

export default function OralPage() {
  const { lid: lidParam = "" } = useParams();
  const home = useLearnerHome(Number(lidParam) || 0);
  return (
    <LangContext.Provider value={home.data && !home.data.owner ? home.data.lang : null}>
      <Oral />
    </LangContext.Provider>
  );
}

function Oral() {
  const { lid: lidParam = "", tid = "" } = useParams();
  const lid = Number(lidParam) || 0;
  const home = useLearnerHome(lid);
  const { t } = useT();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [session, setSession] = useState<OralSession | null>(null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [checked, setChecked] = useState<{ verdict: Verdict; feedback: string; model_answer: string } | null>(null);
  const [verdicts, setVerdicts] = useState<Verdict[]>([]);
  const topic = home.data?.topics.find((x) => x.id === tid);
  const english = topic?.subject === "english";
  const back = () => navigate(subjectHomePath(lid, home.data?.topics.find(t => t.id === tid)?.subject));
  const q = session?.questions[index];

  // Foxy asks each new question aloud.
  useEffect(() => {
    if (q && CAN_SPEAK) speak(q.question, 0.85, english ? "en" : "sl");
  }, [q, english]);

  const start = async () => {
    setBusy(true);
    try {
      setSession(await ucApi.startOral(lid, tid));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const check = async () => {
    if (!session || !q || !answer.trim()) return;
    setBusy(true);
    try {
      const r = await ucApi.answerOral(lid, session.id, q.id, answer.trim());
      setChecked(r);
      setVerdicts((v) => [...v, r.verdict]);
      void qc.invalidateQueries({ queryKey: qk.home(lid) });
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const next = () => {
    setChecked(null);
    setAnswer("");
    setIndex((i) => i + 1);
  };

  const title = `🎤 ${t("oralTitle")}${topic ? ` · ${topic.title}` : ""}`;
  if (home.isError) return <ErrorState error={home.error} />;
  if (!home.data) return <PageLoader />;
  if (!home.data.owner)
    return (
      <FullScreen title={title} onClose={back} closeLabel={t("leave")}>
        <Feedback>{t("preview")}</Feedback>
      </FullScreen>
    );

  if (!session)
    return (
      <FullScreen title={title} onClose={back} closeLabel={t("leave")}>
        <div className="flex items-start gap-3">
          <FoxAvatar size="lg" />
          <p className="text-lg leading-relaxed">{t("oralIntro")}</p>
        </div>
        <Button variant="primary" size="xl" className="w-full" loading={busy} onClick={() => void start()}>
          {t("oralStart")} <ArrowRight />
        </Button>
      </FullScreen>
    );

  if (!q) {
    const count = (v: Verdict) => verdicts.filter((x) => x === v).length;
    return (
      <FullScreen title={title} onClose={back} closeLabel={t("leave")}>
        <div className="space-y-3 py-6 text-center">
          <div className="text-5xl">🦊</div>
          <h1 className="font-display text-3xl">{t("oralDone")}</h1>
          <p className="text-lg text-muted-foreground">{t("oralSummary", { r: count("right"), p: count("partly"), n: count("not_yet") })}</p>
        </div>
        <Button variant="primary" size="lg" className="w-full" onClick={back}>
          {t("backHome")}
        </Button>
      </FullScreen>
    );
  }

  return (
    <FullScreen title={title} onClose={back} closeLabel={t("leave")}>
      <div className="space-y-2">
        <div className="text-sm text-muted-foreground">{t("taskOf", { n: index + 1, total: session.questions.length })}</div>
        <Progress value={index / session.questions.length} />
      </div>
      <div className="flex items-start gap-3">
        <FoxAvatar size="lg" />
        <div className="min-w-0 flex-1 space-y-2 rounded-3xl rounded-tl-lg border border-border bg-card px-4 py-3">
          <p className="text-xl font-semibold leading-snug">{q.question}</p>
          {CAN_SPEAK && (
            <Button variant="ghost" size="sm" onClick={() => speak(q.question, 0.75, english ? "en" : "sl")}>
              <Volume2 /> {t("oralRepeat")}
            </Button>
          )}
        </div>
      </div>
      <Textarea
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        placeholder={t("oralAnswer")}
        maxLength={1500}
        rows={3}
        disabled={!!checked || busy}
        autoCapitalize="sentences"
        spellCheck={false}
        className="text-lg"
      />
      {!checked ? (
        <Button variant="primary" size="lg" className="w-full" disabled={!answer.trim() || busy} onClick={() => void check()}>
          {busy ? (
            <>
              <Loader2 className="animate-spin" /> {t("oralChecking")}
            </>
          ) : (
            t("oralCheck")
          )}
        </Button>
      ) : (
        <>
          <div className={cn("space-y-1 rounded-2xl border px-4 py-3", VERDICT_STYLE[checked.verdict])}>
            <div className="text-lg font-bold">{t(`v_${checked.verdict}` as Key)}</div>
            <RichText text={checked.feedback} className="text-foreground" />
          </div>
          <div className="rounded-2xl bg-card-2 px-4 py-3 text-sm">
            <span className="font-semibold">{t("oralModel")}</span> {checked.model_answer}
          </div>
          <Button variant="primary" size="lg" className="w-full" onClick={next}>
            {t("next")} <ArrowRight />
          </Button>
        </>
      )}
    </FullScreen>
  );
}
