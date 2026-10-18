/**
 * A mock test ("Poskusni test"), full screen: the teacher's format, a timer, no hints and no checking on the
 * way. At the end the learner compares open tasks with the solution, hands it in, and sees the points and what
 * to repeat (never a grade). A parent's preview (from the studio or a learner's space) is never saved.
 */
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, Clock, Send, Snail, Volume2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { ChoiceTile, Feedback, Prompt } from "@/components/kid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState, PageLoader, Progress } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { numberIsRight, textIsRight } from "../learning/answers";
import { qk, ucApi, useLearnerHome, useLearnerMock, useStudioMock, type Mock, type MockAnswer, type MockResult, type MockTask } from "../learning/api";
import { LangContext, useT } from "../learning/i18n";
import { CAN_SPEAK, speak } from "../learning/speech";
import { FullScreen, RichText } from "../learning/ui";

export function isRight(task: MockTask, given: string): boolean {
  if (!given.trim()) return false;
  if (task.kind === "choice") return task.options?.[Number(task.answer)] === given;
  if (task.kind === "number") return numberIsRight(given, task.answer ?? "");
  if (task.kind === "text") return textIsRight(given, task);
  return false;
}

/** Points and missed tasks worked out in the browser (the parent's preview; the server does the same). */
export function scoreMock(mock: Mock, answers: Record<string, MockAnswer>): { points: number; max: number } {
  let points = 0;
  let max = 0;
  for (const sec of mock.sections)
    for (const t of sec.tasks) {
      max += t.points;
      const a = answers[t.id];
      if (a && (t.kind === "open" ? a.got_it === true : a.right)) points += t.points;
    }
  return { points, max };
}

export default function MockPage() {
  const { lid: lidParam = "", mid = "" } = useParams();
  const preview = !lidParam;
  const lid = preview ? 0 : Number(lidParam) || 0;
  const home = useLearnerHome(preview ? null : lid);
  const learnerMock = useLearnerMock(lid, mid, !preview);
  const studio = useStudioMock(preview ? mid : null);
  const mock = preview ? studio.data?.mock : learnerMock.data;
  const error = preview ? studio.error : learnerMock.error;
  const owner = !preview && !!home.data?.owner;
  const back = preview ? "/topics" : `/l/${lid}`;
  return (
    <LangContext.Provider value={!preview && home.data && !home.data.owner ? home.data.lang : null}>
      <MockScreen mock={mock} error={error} loading={!mock || (!preview && !home.data)} owner={owner} lid={lid} back={back} />
    </LangContext.Provider>
  );
}

type Phase = "intro" | "task" | "check" | "done";

function MockScreen({ mock, error, loading, owner, lid, back }: { mock?: Mock; error: unknown; loading: boolean; owner: boolean; lid: number; back: string }) {
  const { t } = useT();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const tasks = useMemo(() => (mock ? mock.sections.flatMap((s) => s.tasks.map((x) => ({ ...x, section: s.title }))) : []), [mock]);
  const [phase, setPhase] = useState<Phase>("intro");
  const [index, setIndex] = useState(0);
  const [given, setGiven] = useState<Record<string, string>>({});
  const [gotIt, setGotIt] = useState<Record<string, boolean>>({});
  const [startedAt, setStartedAt] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [result, setResult] = useState<MockResult | { points: number; max: number; missed: MockResult["missed"] } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (phase !== "task") return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [phase]);

  if (error) return <FullScreen title="📝" onClose={() => navigate(back)} closeLabel={t("leave")}><ErrorState error={error} /></FullScreen>;
  if (loading || !mock) return <PageLoader />;

  const total = tasks.reduce((s, x) => s + x.points, 0);
  const leftMs = startedAt ? mock.minutes * 60_000 - (now - startedAt) : mock.minutes * 60_000;
  const minutesUsed = startedAt ? Math.max(1, Math.round((Date.now() - startedAt) / 60_000)) : 0;
  const open = tasks.filter((x) => x.kind === "open");

  const answers = (): Record<string, MockAnswer> =>
    Object.fromEntries(
      tasks.map((x) => [x.id, x.kind === "open" ? { right: false, got_it: gotIt[x.id] ?? false } : { right: isRight(x, given[x.id] ?? ""), given: given[x.id] ?? null }]),
    );

  const handIn = async () => {
    const a = answers();
    if (!owner) {
      const s = scoreMock(mock, a);
      setResult({
        ...s,
        missed: tasks
          .filter((x) => !(x.kind === "open" ? a[x.id].got_it : a[x.id].right))
          .map((x) => ({ id: x.id, prompt: x.prompt, wrong: given[x.id] ? [given[x.id]] : [], points: 0, max_points: x.points, topic_id: x.topic, skill_id: x.skill ?? null })),
      });
      setPhase("done");
      return;
    }
    setBusy(true);
    try {
      setResult(await ucApi.submitMock(lid, mock.id, a, minutesUsed));
      void qc.invalidateQueries({ queryKey: qk.all });
      setPhase("done");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const title = `📝 ${mock.title}`;
  if (phase === "intro")
    return (
      <FullScreen title={title} onClose={() => navigate(back)} closeLabel={t("leave")}>
        {!owner && <Feedback>{t("preview")}</Feedback>}
        <h1 className="font-display text-3xl leading-tight">{mock.title}</h1>
        <p className="text-lg text-muted-foreground">{mock.intro}</p>
        <Feedback>{t("mockIntro", { minutes: mock.minutes, points: total })}</Feedback>
        <Button
          variant="primary"
          size="xl"
          className="w-full"
          onClick={() => {
            setStartedAt(Date.now());
            setNow(Date.now());
            setPhase("task");
          }}
        >
          <Clock /> {t("mockStart")}
        </Button>
      </FullScreen>
    );

  if (phase === "done" && result)
    return (
      <FullScreen title={title} onClose={() => navigate(back)} closeLabel={t("leave")}>
        <div className="space-y-2 text-center">
          <div className="font-display text-5xl text-primary">{t("mockResult", { p: result.points, max: result.max })}</div>
          {"grade_estimate" in result && result.grade_estimate !== undefined && (
            <p className="text-sm text-muted-foreground">Grade estimate (parents only): {result.grade_estimate}</p>
          )}
        </div>
        {result.missed.length === 0 ? (
          <Feedback>{t("mockAllRight")}</Feedback>
        ) : (
          <section className="space-y-2">
            <h2 className="font-display text-xl">{t("mockMissed")}</h2>
            {result.missed.map((m) => {
              const task = tasks.find((x) => x.id === m.id);
              return (
                <div key={m.id} className="space-y-1 rounded-2xl border border-border bg-card p-3 text-sm">
                  <div className="font-medium">{task?.prompt ?? m.prompt}</div>
                  {task?.kind !== "open" && (
                    <div className="text-muted-foreground">{t("mockYourAnswer", { a: m.wrong[0] ?? given[m.id] ?? t("mockEmpty") })}</div>
                  )}
                  {task && <RichText text={task.solution} className="rounded-xl bg-info/10 px-3 py-2" />}
                </div>
              );
            })}
          </section>
        )}
        <Button variant="primary" size="lg" className="w-full" onClick={() => navigate(back)}>
          {t("backHome")}
        </Button>
      </FullScreen>
    );

  if (phase === "check")
    return (
      <FullScreen title={title} onClose={() => navigate(back)} closeLabel={t("leave")}>
        <p className="text-muted-foreground">{t("mockCheckOpen")}</p>
        {open.map((x) => (
          <div key={x.id} className="space-y-2 rounded-2xl border border-border bg-card p-3">
            <div className="font-medium">{x.prompt}</div>
            <RichText text={x.solution} className="rounded-xl bg-info/10 px-3 py-2 text-sm" />
            <div className="flex gap-2">
              <ChoiceTile selected={gotIt[x.id] === true} onClick={() => setGotIt({ ...gotIt, [x.id]: true })} className="text-center">
                <Check className="mr-1 inline size-4" /> {t("gotIt")}
              </ChoiceTile>
              <ChoiceTile selected={gotIt[x.id] === false} onClick={() => setGotIt({ ...gotIt, [x.id]: false })} className="text-center">
                {t("notYetSelf")}
              </ChoiceTile>
            </div>
          </div>
        ))}
        <Button variant="primary" size="xl" className="w-full" loading={busy} disabled={open.some((x) => gotIt[x.id] === undefined)} onClick={() => void handIn()}>
          <Send /> {t("mockFinish")}
        </Button>
      </FullScreen>
    );

  const task = tasks[index];
  const last = index === tasks.length - 1;
  const mm = Math.max(0, Math.floor(leftMs / 60_000));
  const ss = Math.max(0, Math.floor((leftMs % 60_000) / 1000));
  const timer = (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-sm font-semibold tabular", leftMs <= 0 ? "bg-danger/10 text-danger" : leftMs < 5 * 60_000 ? "bg-warning/15 text-warning" : "bg-muted")}>
      <Clock className="size-4" /> {t("mockTimeLeft", { t: `${mm}:${String(ss).padStart(2, "0")}` })}
    </span>
  );
  const next = () => (last ? (open.length ? setPhase("check") : void handIn()) : setIndex(index + 1));

  return (
    <FullScreen title={title} onClose={() => navigate(back)} closeLabel={t("leave")} right={timer}>
      {leftMs <= 0 && <Feedback tone="warn">{t("mockTimeUp")}</Feedback>}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {task.section} · {t("taskOf", { n: index + 1, total: tasks.length })}
          </span>
          <span className="rounded-full bg-primary-soft px-2 py-0.5 text-xs font-semibold text-primary">{t("pointsN", { n: task.points })}</span>
        </div>
        <Progress value={index / tasks.length} />
      </div>
      <Prompt>{task.prompt}</Prompt>
      {task.say && CAN_SPEAK && (
        <div className="flex gap-2">
          <Button variant="soft" size="lg" onClick={() => speak(task.say!, 0.85)}>
            <Volume2 /> {t("listen")}
          </Button>
          <Button variant="ghost" size="lg" onClick={() => speak(task.say!, 0.55)}>
            <Snail /> {t("slower")}
          </Button>
        </div>
      )}
      {task.kind === "choice" && (
        <div className="grid gap-2">
          {task.options!.map((o) => (
            <ChoiceTile key={o} selected={given[task.id] === o} onClick={() => setGiven({ ...given, [task.id]: o })}>
              {o}
            </ChoiceTile>
          ))}
        </div>
      )}
      {(task.kind === "number" || task.kind === "text") && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            next();
          }}
        >
          <Input
            key={task.id}
            autoFocus
            value={given[task.id] ?? ""}
            onChange={(e) => setGiven({ ...given, [task.id]: e.target.value })}
            inputMode={task.kind === "number" ? "decimal" : "text"}
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            placeholder={task.kind === "number" ? t("typeNumber") : t("typeAnswer")}
            aria-label={t("yourAnswer")}
            className="h-14 text-xl"
          />
        </form>
      )}
      {task.kind === "open" && <Feedback tone="soft">{t("openTask")}</Feedback>}
      <div className="flex gap-2">
        <Button variant="secondary" size="lg" disabled={index === 0} onClick={() => setIndex(index - 1)} aria-label={t("mockPrev")}>
          <ArrowLeft />
        </Button>
        <Button variant={last ? "primary" : "secondary"} size="lg" className="flex-1" loading={busy} onClick={next}>
          {last ? (
            <>
              <Send /> {t("mockFinish")}
            </>
          ) : (
            <>
              {given[task.id] || task.kind === "open" ? t("next") : t("mockSkip")} <ArrowRight />
            </>
          )}
        </Button>
      </div>
      <div className="flex flex-wrap gap-1.5" aria-hidden>
        {tasks.map((x, i) => (
          <button
            key={x.id}
            type="button"
            onClick={() => setIndex(i)}
            className={cn(
              "size-7 rounded-lg text-xs font-semibold",
              i === index ? "bg-primary text-primary-foreground" : given[x.id] ? "bg-primary-soft text-primary" : "bg-muted text-muted-foreground",
            )}
          >
            {i + 1}
          </button>
        ))}
      </div>
    </FullScreen>
  );
}
