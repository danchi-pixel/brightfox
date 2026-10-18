/**
 * One topic's practice, one task at a time: a short "Remember" recap, then tasks from warm-up to challenge.
 * A wrong answer gets "have another go" (or, for a known trap answer, the reason it's wrong); hints come one
 * by one; the solution can be opened after two tries (or once every hint is used). Nothing is scored: the
 * end screen lists the tasks worth another look and offers to practise just those. With ``challenge`` it
 * plays the topic's harder "Liga prvakov" level instead, and finishing it wins the trophy.
 */
import { ArrowRight, Check, Eye, Lightbulb, MessageCircle, RotateCcw, Snail, Sparkles, Trophy, Volume2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChoiceTile, Feedback, Prompt } from "@/components/kid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import { normalizeText, numberIsRight, textIsRight } from "../learning/answers";
import type { Task, TaskResult, Topic } from "../learning/api";
import { useT, type Key } from "../learning/i18n";
import { CAN_SPEAK, speak } from "../learning/speech";
import { RichText, SubjectBubble } from "../learning/ui";

type Results = Record<string, TaskResult>;

const RIGHT: Key[] = ["right1", "right2", "right3"];

function shuffled(n: number): number[] {
  const a = Array.from({ length: n }, (_, i) => i);
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** Worth another look: not right first time, or the solution was needed (an open task: "not yet"). */
export function isTricky(r: TaskResult | undefined, kind: Task["kind"] | undefined): boolean {
  if (!r) return true;
  if (kind === "open") return r.got_it !== true;
  return !r.first || r.shown;
}

/** The reason for a known wrong answer, if what was typed is one of the topic's traps. */
export function trapFor(task: Task, given: string): string | null {
  const g = normalizeText(given, true);
  return task.traps?.find((tr) => normalizeText(tr.answer, true) === g)?.why ?? null;
}

export function PracticePlayer({
  topic,
  challenge = false,
  onRunFinished,
  onPartial,
  onExit,
  onAskFoxy,
}: {
  topic: Topic;
  challenge?: boolean;
  onRunFinished?: (results: Results) => void;
  onPartial?: (results: Results) => void;
  onExit: () => void;
  /** "Ask Foxy about this task" (only when Foxy is available to this learner). */
  onAskFoxy?: (taskId: string) => void;
}) {
  const { t } = useT();
  const taskList = challenge ? (topic.challenge ?? []) : topic.tasks;
  const [queue, setQueue] = useState<string[]>(() => taskList.map((x) => x.id));
  const [phase, setPhase] = useState<"intro" | "task" | "done">(challenge || topic.learn?.length ? "intro" : "task");
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<Results>({});
  const [run, setRun] = useState(0);
  const resultsRef = useRef(results);
  resultsRef.current = results;
  const doneRef = useRef(false);

  // Leaving half-way still tells the parent how the tasks so far went.
  useEffect(
    () => () => {
      if (!doneRef.current && Object.keys(resultsRef.current).length) onPartial?.(resultsRef.current);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [run],
  );

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const tasks = useMemo(() => new Map(taskList.map((x) => [x.id, x])), [topic, challenge]);
  const task = tasks.get(queue[index]);

  /** A task is settled (right, or the solution opened): keep it even if the learner leaves before "Next". */
  const record = (r: TaskResult) => setResults((prev) => ({ ...prev, [queue[index]]: r }));

  const finishTask = (r: TaskResult) => {
    const next = { ...results, [queue[index]]: r };
    setResults(next);
    if (index + 1 < queue.length) {
      setIndex(index + 1);
    } else {
      doneRef.current = true;
      setPhase("done");
      onRunFinished?.(next);
    }
  };

  const repeat = (ids: string[]) => {
    doneRef.current = false;
    setRun((n) => n + 1);
    setResults({});
    setQueue(ids);
    setIndex(0);
    setPhase("task");
  };

  if (phase === "intro" && challenge) {
    return (
      <div className="mx-auto max-w-md space-y-6 py-6 text-center">
        <div className="flex justify-center">
          <span className="rounded-full bg-warning/15 p-5 text-warning">
            <Trophy className="size-12" />
          </span>
        </div>
        <h1 className="font-display text-4xl">{t("challengeTitle")}</h1>
        <p className="text-lg text-muted-foreground">{topic.title}</p>
        <Feedback>{t("challengeIntro")}</Feedback>
        <Button variant="primary" size="xl" className="w-full" onClick={() => setPhase("task")}>
          {t("challengeStart")} <ArrowRight />
        </Button>
      </div>
    );
  }

  if (phase === "intro") {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <SubjectBubble subject={topic.subject} />
          <h1 className="font-display text-3xl leading-tight">{topic.title}</h1>
        </div>
        <p className="text-lg leading-relaxed text-muted-foreground">{topic.intro}</p>
        <div className="space-y-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("remember")}</div>
          {topic.learn!.map((card, i) => (
            <div key={i} className="space-y-2 rounded-2xl border border-border bg-card p-4">
              <div className="text-lg font-semibold">{card.title}</div>
              <p className="leading-relaxed">{card.text}</p>
              {card.example && (
                <p className="rounded-xl bg-card-2 px-3 py-2 leading-relaxed">
                  <span className="mr-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("example")}</span>
                  {card.example}
                </p>
              )}
            </div>
          ))}
        </div>
        <Button variant="primary" size="xl" className="w-full" onClick={() => setPhase("task")}>
          {t("toTasks")} <ArrowRight />
        </Button>
      </div>
    );
  }

  if (phase === "done") {
    const tricky = queue.filter((id) => isTricky(results[id], tasks.get(id)?.kind));
    return (
      <div className="mx-auto max-w-md space-y-6 py-6 text-center">
        <div className="flex justify-center">
          {challenge ? (
            <span className="rounded-full bg-warning/15 p-5 text-warning">
              <Trophy className="size-14" />
            </span>
          ) : (
            <span className="rounded-full bg-primary-soft p-4 text-primary">
              <Sparkles className="size-10" />
            </span>
          )}
        </div>
        <h1 className="font-display text-4xl">{challenge ? t("challengeDoneTitle") : t("doneTitle")}</h1>
        <p className="text-lg text-muted-foreground">{challenge ? t("challengeDoneText") : t("doneText")}</p>
        {tricky.length === 0 ? (
          <Feedback>{t("allFirst")}</Feedback>
        ) : (
          <div className="space-y-2 text-left">
            <div className="text-sm font-semibold text-muted-foreground">{t("lookAgain")}</div>
            <ul className="space-y-1.5">
              {tricky.map((id) => (
                <li key={id} className="line-clamp-2 rounded-xl bg-card px-3 py-2 text-sm">
                  {tasks.get(id)?.prompt}
                </li>
              ))}
            </ul>
            <Button variant="soft" size="lg" className="w-full" onClick={() => repeat(tricky)}>
              <RotateCcw /> {t("repeatTricky")}
            </Button>
          </div>
        )}
        <Button variant="primary" size="lg" className="w-full" onClick={onExit}>
          {t("backHome")}
        </Button>
      </div>
    );
  }

  if (!task) return null;
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{t("taskOf", { n: index + 1, total: queue.length })}</span>
          {challenge ? (
            <span className="rounded-full bg-warning/15 px-2.5 py-0.5 text-xs font-semibold text-warning">{t("challengeTitle")}</span>
          ) : (
            <LevelBadge task={task} />
          )}
        </div>
        <Progress value={index / queue.length} />
      </div>
      <TaskView key={`${run}-${task.id}`} task={task} onSettled={record} onDone={finishTask} onAskFoxy={onAskFoxy} />
    </div>
  );
}

function LevelBadge({ task }: { task: Task }) {
  const { t } = useT();
  const colors = { 1: "#16a34a", 2: "#0ea5e9", 3: "#f97316" } as const;
  const c = task.extra ? "#8b5cf6" : colors[task.level];
  return (
    <span className="rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ color: c, background: `color-mix(in srgb, ${c} 15%, transparent)` }}>
      {task.extra ? t("bonus") : t(`level${task.level}` as Key)}
    </span>
  );
}

/** Listen buttons for a task's English (dictation, pronunciation). Without speech, the words are shown. */
function Listen({ text }: { text: string }) {
  const { t } = useT();
  if (!CAN_SPEAK) return <Feedback tone="soft">{text}</Feedback>;
  return (
    <div className="flex flex-wrap gap-2">
      <Button variant="soft" size="xl" onClick={() => speak(text, 0.85)}>
        <Volume2 /> {t("listen")}
      </Button>
      <Button variant="ghost" size="xl" onClick={() => speak(text, 0.55)}>
        <Snail /> {t("slower")}
      </Button>
    </div>
  );
}

function TaskView({
  task,
  onSettled,
  onDone,
  onAskFoxy,
}: {
  task: Task;
  onSettled: (r: TaskResult) => void;
  onDone: (r: TaskResult) => void;
  onAskFoxy?: (taskId: string) => void;
}) {
  const { t } = useT();
  const [value, setValue] = useState("");
  const [picked, setPicked] = useState<number | null>(null);
  const [wrongPicks, setWrongPicks] = useState<number[]>([]);
  const [tries, setTries] = useState(0);
  const [hints, setHints] = useState(0);
  // What was typed or picked before the right answer (shown to parents; at most five).
  const [wrong, setWrong] = useState<string[]>([]);
  const [trap, setTrap] = useState<string | null>(null);
  const [state, setState] = useState<"answering" | "wrong" | "right" | "shown">("answering");
  const [showMethod, setShowMethod] = useState(false);
  const [praise] = useState(() => RIGHT[Math.floor(Math.random() * RIGHT.length)]);
  const order = useMemo(() => shuffled(task.options?.length ?? 0), [task]);
  const inputRef = useRef<HTMLInputElement>(null);
  const allHints = task.hints ?? [];
  const isOpen = task.kind === "open";

  const result = (extra: Partial<TaskResult> = {}): TaskResult => ({ first: false, tries, hints, shown: false, wrong, ...extra });

  const check = () => {
    let right = false;
    let given = value.trim();
    if (task.kind === "choice") {
      if (picked === null) return;
      right = picked === task.answer;
      given = task.options?.[picked] ?? "";
      if (!right) setWrongPicks((w) => [...w, picked]);
      setPicked(null);
    } else if (task.kind === "number") {
      if (!given) return;
      right = numberIsRight(value, task.answer ?? "");
    } else {
      if (!given) return;
      right = textIsRight(value, task);
    }
    const n = tries + 1;
    setTries(n);
    setState(right ? "right" : "wrong");
    setTrap(right ? null : trapFor(task, given));
    if (right) onSettled({ first: n === 1, tries: n, hints, shown: false, wrong });
    else {
      setWrong((w) => (w.length < 5 ? [...w, given.slice(0, 100)] : w));
      setTimeout(() => inputRef.current?.select(), 0);
    }
  };

  const reveal = () => {
    setState("shown");
    if (!isOpen) onSettled(result({ shown: true }));
  };

  const canShow = isOpen || tries >= 2 || (tries >= 1 && hints >= allHints.length);
  const finished = state === "right" || state === "shown";

  return (
    <div className="space-y-4">
      <Prompt>{task.prompt}</Prompt>
      {task.say && <Listen text={task.say} />}
      {isOpen && state !== "shown" && <Feedback tone="soft">{t("openTask")}</Feedback>}

      {task.kind === "choice" && (
        <div className="grid gap-2">
          {order.map((i) => {
            const isWrong = wrongPicks.includes(i);
            const isAnswer = finished && i === task.answer;
            return (
              <ChoiceTile key={i} selected={picked === i || isAnswer} disabled={finished || isWrong} onClick={() => setPicked(i)} className={cn(isWrong && "line-through opacity-50")}>
                {task.options![i]}
              </ChoiceTile>
            );
          })}
        </div>
      )}

      {(task.kind === "number" || task.kind === "text") && (
        <form
          className="space-y-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (!finished) check();
          }}
        >
          <div className="flex items-center gap-2">
            <Input
              ref={inputRef}
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                if (state === "wrong") setState("answering");
              }}
              disabled={finished}
              inputMode={task.kind === "number" ? "decimal" : "text"}
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              placeholder={task.kind === "number" ? t("typeNumber") : t("typeAnswer")}
              aria-label={t("yourAnswer")}
              className="h-14 flex-1 text-xl"
            />
            {task.unit && <span className="text-lg text-muted-foreground">{task.unit}</span>}
          </div>
          {task.kind === "number" && <p className="text-xs text-muted-foreground">{t("numberTip")}</p>}
        </form>
      )}

      {state === "wrong" &&
        (trap ? (
          <Feedback tone="warn">
            <b>{t("trap")}</b> {trap}
          </Feedback>
        ) : (
          <Feedback tone="soft">{t("notYet")}</Feedback>
        ))}
      {state === "right" && (
        <div role="status" className="flex items-center gap-2 rounded-2xl border border-success/40 bg-success/10 px-4 py-3 text-lg font-semibold text-success">
          <Check className="size-6" /> {t(praise)}
        </div>
      )}

      {hints > 0 && (
        <div className="space-y-2">
          {allHints.slice(0, hints).map((h, i) => (
            <div key={i} className="flex gap-2 rounded-2xl border border-warning/30 bg-warning/10 px-4 py-3 leading-relaxed">
              <Lightbulb className="mt-0.5 size-5 shrink-0 text-warning" />
              <span>{h}</span>
            </div>
          ))}
        </div>
      )}

      {(state === "shown" || showMethod) && (
        <div className="rounded-2xl border border-info/30 bg-info/10 px-4 py-3">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("solution")}</div>
          <RichText text={task.solution} className="leading-relaxed" />
        </div>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        {!finished && !isOpen && (
          <Button variant="primary" size="lg" className="flex-1" onClick={check} disabled={task.kind === "choice" ? picked === null : !value.trim()}>
            {t("check")}
          </Button>
        )}
        {!finished && hints < allHints.length && (
          <Button variant="secondary" size="lg" onClick={() => setHints((h) => h + 1)}>
            <Lightbulb /> {t("hint")}
            {allHints.length > 1 ? ` ${hints + 1}/${allHints.length}` : ""}
          </Button>
        )}
        {!finished && canShow && (
          <Button variant={isOpen ? "primary" : "ghost"} size="lg" className={cn(isOpen && "flex-1")} onClick={reveal}>
            <Eye /> {t("showSolution")}
          </Button>
        )}
        {state === "right" && !showMethod && (
          <Button variant="ghost" size="lg" onClick={() => setShowMethod(true)}>
            <Eye /> {t("seeSolution")}
          </Button>
        )}
        {state === "right" && (
          <Button variant="primary" size="lg" className="flex-1" onClick={() => onDone(result({ first: tries === 1 }))}>
            {t("next")} <ArrowRight />
          </Button>
        )}
        {state === "shown" && !isOpen && (
          <Button variant="primary" size="lg" className="flex-1" onClick={() => onDone(result({ shown: true }))}>
            {t("next")} <ArrowRight />
          </Button>
        )}
        {state === "shown" && isOpen && (
          <>
            <Button variant="primary" size="lg" className="flex-1" onClick={() => onDone(result({ shown: true, first: true, got_it: true }))}>
              <Check /> {t("gotIt")}
            </Button>
            <Button variant="secondary" size="lg" className="flex-1" onClick={() => onDone(result({ shown: true, got_it: false }))}>
              {t("notYetSelf")}
            </Button>
          </>
        )}
      </div>
      {onAskFoxy && (state === "wrong" || state === "shown") && (
        <Button variant="ghost" size="sm" onClick={() => onAskFoxy(task.id)}>
          <MessageCircle /> {t("askAboutThis")}
        </Button>
      )}
    </div>
  );
}
