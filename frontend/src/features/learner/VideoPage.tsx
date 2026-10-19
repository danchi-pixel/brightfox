/**
 * 🎬 Video lesson: a topic's "video" played like a football match. Foxy comments (Slovene captions, read aloud
 * where the device has a Slovene voice), English words and sentences are read aloud, pairs flip like a
 * scoreboard, and quiz scenes give a few seconds to tap an answer ("GOOOL!" when it's right). Nothing is saved:
 * it's for watching, the practice is where results count. Works without sound (captions stay long enough to
 * read), and for a parent's preview (no name, no learner).
 */
import { ArrowRight, Pause, Play, RotateCcw, SkipBack, SkipForward, Volume2, VolumeX } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router";
import { ErrorState, PageLoader } from "@/components/ui/misc";
import { cn } from "@/lib/utils";
import type { Video, VideoScene } from "../learning/api";
import { LangContext, useT } from "../learning/i18n";
import { CAN_SPEAK, hasVoice, speak, speakAndWait, stopSpeaking } from "../learning/speech";
import { beatsOf, COUNTDOWN_S, fillName, matchMinute, quizCount, readingMs, type Beat } from "./video";
import { useTopicScreen } from "./useTopic";

export default function VideoPage() {
  const s = useTopicScreen();
  const navigate = useNavigate();
  const learnPath = s.preview ? `/preview/${s.tid}/learn` : `/l/${s.lid}/learn/${s.tid}`;
  return (
    <LangContext.Provider value={s.lang}>
      {s.error ? (
        <div className="mx-auto max-w-2xl p-4">
          <ErrorState error={s.error} />
        </div>
      ) : s.loading ? (
        <PageLoader />
      ) : !s.topic?.video ? (
        <Navigate to={learnPath} replace />
      ) : (
        <Player
          video={s.topic.video}
          name={s.preview ? null : s.home?.learner.name}
          avatar={s.preview ? "🦊" : s.home?.learner.avatar || "⚽"}
          onClose={() => navigate(s.homePath)}
          onPractice={() => navigate(s.preview ? `/preview/${s.tid}` : `/l/${s.lid}/practice/${s.tid}`)}
        />
      )}
    </LangContext.Provider>
  );
}

const wait = (ms: number) => new Promise<void>((r) => window.setTimeout(r, ms));

/** Re-render when the browser has loaded its voices (they arrive a moment after the page). */
function useVoicesReady() {
  const [, setN] = useState(0);
  useEffect(() => {
    if (!CAN_SPEAK) return;
    const bump = () => setN((n) => n + 1);
    window.speechSynthesis.addEventListener("voiceschanged", bump);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", bump);
  }, []);
}

function Player({ video, name, avatar, onClose, onPractice }: { video: Video; name?: string | null; avatar: string; onClose: () => void; onPractice: () => void }) {
  const { t } = useT();
  useVoicesReady();
  const scenes = video.scenes;
  const [started, setStarted] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [pos, setPos] = useState({ scene: 0, beat: 0 });
  const [done, setDone] = useState(false);
  const [voice, setVoice] = useState(CAN_SPEAK);
  const [talking, setTalking] = useState(false);
  const [picked, setPicked] = useState<Record<number, number>>({});
  const [goalFlash, setGoalFlash] = useState(0);
  const posRef = useRef(pos);
  posRef.current = pos;

  const scene = scenes[pos.scene];
  const beats = useMemo(() => beatsOf(scene), [scene]);
  const beat = beats[Math.min(pos.beat, beats.length - 1)];
  const fill = useCallback((text: string) => fillName(text, name), [name]);
  const slVoice = voice && hasVoice("sl");
  const goals = Object.entries(picked).filter(([i, a]) => {
    const sc = scenes[Number(i)];
    return sc?.type === "quiz" && sc.answer === a;
  }).length;

  const advance = useCallback(() => {
    const p = posRef.current;
    if (p.beat + 1 < beatsOf(scenes[p.scene]).length) setPos({ scene: p.scene, beat: p.beat + 1 });
    else if (p.scene + 1 < scenes.length) setPos({ scene: p.scene + 1, beat: 0 });
    else {
      setDone(true);
      setPlaying(false);
    }
  }, [scenes]);

  // Plays the current beat (speaks or waits), then moves on. Leaving the beat (pause, skip, a tap) cancels it.
  useEffect(() => {
    if (!playing || done) return;
    let cancelled = false;
    const caption = async (text?: string) => {
      if (!text || cancelled) return;
      if (slVoice) {
        setTalking(true);
        await speakAndWait(fill(text), 1, "sl");
        setTalking(false);
      } else await wait(readingMs(fill(text)));
    };
    const english = async (text: string) => {
      if (cancelled) return;
      if (voice) {
        setTalking(true);
        await speakAndWait(text, 0.85, "en");
        setTalking(false);
        await wait(250);
      } else await wait(Math.max(1200, readingMs(text) * 0.8));
    };
    const run = async () => {
      const sc = scene;
      const b: Beat = beat;
      if (b.kind === "open") {
        await wait(sc.type === "intro" ? 900 : 500);
        if (sc.foxy) await caption(sc.foxy);
        else await wait(1500);
        await wait(sc.type === "intro" ? 900 : 300);
      } else if (b.kind === "step" && sc.type === "rule") {
        const st = sc.steps[b.i];
        await caption(st.sl);
        if (st.en) await english(st.en);
        await wait(500);
      } else if (b.kind === "pair" && sc.type === "pairs") {
        await wait(650);
        const say = sc.say ?? [];
        for (const side of say) await english(sc.pairs[b.i][side]);
        if (!say.length) await wait(1500);
      } else if (b.kind === "point") {
        await wait(1400);
      } else if (b.kind === "ask" && sc.type === "quiz") {
        if (sc.foxy) await caption(sc.foxy);
        if (sc.say) await english(sc.say);
        else await wait(readingMs(sc.question));
      } else if (b.kind === "countdown") {
        await wait(COUNTDOWN_S * 1000);
      } else if (b.kind === "reveal" && sc.type === "quiz") {
        await wait(picked[pos.scene] === sc.answer ? 1700 : 600);
        await english(sc.options[sc.answer]);
        if (sc.explain) await caption(sc.explain);
        await wait(700);
      }
      if (!cancelled) advance();
    };
    void run();
    return () => {
      cancelled = true;
      stopSpeaking();
      setTalking(false);
    };
    // picked is read only for the reveal's pause; re-running on a pick would replay the beat
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, done, pos, voice, slVoice, advance, fill]);

  const pick = (i: number) => {
    if (scene.type !== "quiz" || picked[pos.scene] !== undefined || beat.kind === "reveal") return;
    setPicked((p) => ({ ...p, [pos.scene]: i }));
    if (i === scene.answer) setGoalFlash((n) => n + 1);
    setPos({ scene: pos.scene, beat: 2 });
  };

  useEffect(() => {
    if (!goalFlash) return;
    const id = window.setTimeout(() => setGoalFlash(0), 1700);
    return () => window.clearTimeout(id);
  }, [goalFlash]);

  const jump = (scene: number) => {
    setDone(false);
    setPos({ scene: Math.max(0, Math.min(scenes.length - 1, scene)), beat: 0 });
  };
  const restart = () => {
    setPicked({});
    setDone(false);
    setPos({ scene: 0, beat: 0 });
    setPlaying(true);
  };

  const captionText = (() => {
    if (scene.type === "rule" && beat.kind === "step") return scene.steps[beat.i].sl ?? scene.steps.slice(0, beat.i).reverse().find((x) => x.sl)?.sl ?? scene.foxy;
    if (scene.type === "quiz" && beat.kind === "reveal") return scene.explain ?? scene.foxy;
    if (scene.type === "quiz" && beat.kind === "countdown") return t("videoTap");
    return scene.foxy;
  })();

  return (
    <div className="fixed inset-0 z-30 flex flex-col bg-[#0a2e18] text-white">
      <header className="flex h-14 shrink-0 items-center gap-2 px-3">
        <button onClick={onClose} className="rounded-xl p-2 text-white/70 hover:bg-white/10 hover:text-white" aria-label={t("leave")}>
          <span aria-hidden className="text-xl leading-none">✕</span>
        </button>
        <div className="min-w-0 flex-1 truncate text-sm font-semibold text-white/80">{video.title}</div>
        {CAN_SPEAK && (
          <button
            onClick={() => setVoice((v) => !v)}
            className="rounded-xl p-2 text-white/80 hover:bg-white/10"
            aria-label={voice ? t("videoVoiceOn") : t("videoVoiceOff")}
            title={voice ? t("videoVoiceOn") : t("videoVoiceOff")}
          >
            {voice ? <Volume2 className="size-5" /> : <VolumeX className="size-5" />}
          </button>
        )}
      </header>

      <main className="vp-pitch relative mx-auto flex w-full max-w-3xl flex-1 flex-col overflow-hidden sm:rounded-3xl">
        {/* Scoreboard */}
        <div className="z-10 mx-auto mt-3 flex items-center gap-2 rounded-full bg-black/60 px-3 py-1.5 text-sm font-bold tabular-nums shadow-lg">
          <span className="rounded-md bg-white/15 px-1.5">{matchMinute(pos.scene, scenes.length)}'</span>
          <span aria-hidden>{avatar}</span>
          <span className="max-w-32 truncate">{name || "BrightFox"}</span>
          <span aria-hidden>⚽</span>
          <span className="text-lg text-amber-300">{goals}</span>
        </div>

        <div className="relative z-0 flex min-h-0 flex-1 flex-col justify-center px-3 py-3">
          {!started ? (
            <StartCard video={video} onStart={() => { setStarted(true); setPlaying(true); }} />
          ) : done ? (
            <EndCard goals={goals} total={quizCount(scenes)} onAgain={restart} onPractice={onPractice} />
          ) : (
            <SceneView key={pos.scene} scene={scene} beat={beat} beatIndex={pos.beat} fill={fill} picked={picked[pos.scene]} onPick={pick} voice={voice} />
          )}
        </div>

        {/* Foxy, the commentator */}
        {started && !done && captionText && (
          <div className="z-10 flex items-end gap-2 px-3 pb-3">
            <span className={cn("grid size-12 shrink-0 place-items-center rounded-full bg-white text-3xl shadow-lg", talking && "vp-bob")} aria-hidden>
              🦊
            </span>
            <div key={`${pos.scene}-${captionText}`} className="vp-in relative rounded-2xl rounded-bl-sm bg-white px-3.5 py-2.5 text-[15px] font-semibold leading-snug text-slate-900 shadow-lg" aria-live="polite">
              {fill(captionText)}
            </div>
          </div>
        )}

        {goalFlash > 0 && <GoalFlash key={goalFlash} label={t("videoGoal")} />}
        {!CAN_SPEAK && started && !done && (
          <p className="z-10 mx-3 mb-2 rounded-xl bg-black/50 px-3 py-1.5 text-center text-xs text-white/80">{t("videoNoVoice")}</p>
        )}
      </main>

      {/* Controls */}
      <footer className="mx-auto w-full max-w-3xl shrink-0 space-y-2 px-3 pt-2 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <div className="flex gap-0.5" aria-hidden>
          {scenes.map((sc, i) => (
            <button
              key={i}
              tabIndex={-1}
              onClick={() => started && jump(i)}
              className={cn(
                "h-2 flex-1 rounded-full transition-colors",
                i < pos.scene || done ? "bg-amber-300" : i === pos.scene ? "bg-white" : "bg-white/25",
                sc.type === "quiz" && "h-3",
              )}
            />
          ))}
        </div>
        <div className="flex items-center justify-center gap-3">
          <button disabled={!started} onClick={() => jump(pos.scene - 1)} className="rounded-full p-3 text-white/80 hover:bg-white/10 disabled:opacity-30" aria-label={t("videoPrev")}>
            <SkipBack className="size-6" />
          </button>
          <button
            onClick={() => {
              if (!started) {
                setStarted(true);
                setPlaying(true);
              } else if (done) restart();
              else setPlaying((p) => !p);
            }}
            className="grid size-16 place-items-center rounded-full bg-amber-300 text-slate-900 shadow-lg transition hover:scale-105"
            aria-label={playing ? t("videoPause") : t("videoPlay")}
          >
            {done ? <RotateCcw className="size-7" /> : playing ? <Pause className="size-8" /> : <Play className="ml-1 size-8" />}
          </button>
          <button disabled={!started} onClick={() => jump(pos.scene + 1)} className="rounded-full p-3 text-white/80 hover:bg-white/10 disabled:opacity-30" aria-label={t("videoNext")}>
            <SkipForward className="size-6" />
          </button>
        </div>
      </footer>
    </div>
  );
}

function StartCard({ video, onStart }: { video: Video; onStart: () => void }) {
  const { t } = useT();
  const first = video.scenes[0];
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <div className="vp-pop text-7xl drop-shadow-lg" aria-hidden>
        {first.type === "intro" && first.emoji ? first.emoji : "🎬"}
      </div>
      <h1 className="font-display text-3xl leading-tight drop-shadow-md sm:text-4xl">{video.title}</h1>
      <button onClick={onStart} className="vp-in flex items-center gap-2 rounded-full bg-amber-300 px-7 py-4 text-lg font-extrabold text-slate-900 shadow-xl transition hover:scale-105">
        <Play className="size-6" /> {t("videoStart")}
      </button>
      <div className="vp-roll text-3xl" aria-hidden>
        ⚽
      </div>
    </div>
  );
}

function EndCard({ goals, total, onAgain, onPractice }: { goals: number; total: number; onAgain: () => void; onPractice: () => void }) {
  const { t } = useT();
  return (
    <div className="flex flex-col items-center gap-3 text-center">
      <div className="vp-pop text-7xl" aria-hidden>
        🏆
      </div>
      <h2 className="font-display text-4xl drop-shadow-md">{t("videoEnd")}</h2>
      {total > 0 && <p className="text-lg font-bold text-amber-200">{t("videoGoals", { n: goals, total })}</p>}
      <div className="flex flex-wrap justify-center gap-2 pt-2">
        <button onClick={onAgain} className="flex items-center gap-2 rounded-full bg-white/15 px-5 py-3 font-bold hover:bg-white/25">
          <RotateCcw className="size-5" /> {t("videoAgain")}
        </button>
        <button onClick={onPractice} className="flex items-center gap-2 rounded-full bg-amber-300 px-5 py-3 font-extrabold text-slate-900 hover:scale-105">
          ✏️ {t("toPractice")} <ArrowRight className="size-5" />
        </button>
      </div>
    </div>
  );
}

/** A line read aloud in English: tap it to hear it again. */
function SayLine({ text, voice, className }: { text: string; voice: boolean; className?: string }) {
  return (
    <button type="button" onClick={() => voice && speak(text)} className={cn("text-left", voice && "cursor-pointer hover:underline decoration-primary/40 underline-offset-4", className)}>
      {text}
      {voice && <Volume2 className="ml-1.5 inline size-4 align-[-2px] text-primary/70" aria-hidden />}
    </button>
  );
}

/** The line being explained or flipped: scrolls into view on small screens. */
function useScrollTo(active: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [active]);
  return ref;
}

function Row({ active, className, children }: { active: boolean; className?: string; children: React.ReactNode }) {
  const ref = useScrollTo(active);
  return (
    <div ref={ref} className={cn(className, active ? "bg-amber-100 ring-2 ring-amber-300" : "bg-slate-100")}>
      {children}
    </div>
  );
}

function Board({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("vp-in mx-auto w-full max-w-xl max-h-full overflow-y-auto rounded-3xl bg-white/95 p-4 text-slate-900 shadow-2xl sm:p-5", className)}>{children}</div>;
}

function SceneView({ scene, beat, beatIndex, fill, picked, onPick, voice }: {
  scene: VideoScene;
  beat: Beat;
  beatIndex: number;
  fill: (s: string) => string;
  picked?: number;
  onPick: (i: number) => void;
  voice: boolean;
}) {
  const { t } = useT();
  if (scene.type === "intro") {
    return (
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="vp-pop text-8xl drop-shadow-lg" aria-hidden>
          {scene.emoji ?? "⚽"}
        </div>
        <h1 className="vp-in font-display text-4xl leading-tight drop-shadow-md sm:text-5xl" style={{ animationDelay: "0.25s" }}>
          {fill(scene.title)}
        </h1>
        {scene.sub && (
          <p className="vp-in max-w-md text-lg font-semibold text-white/90 drop-shadow" style={{ animationDelay: "0.5s" }}>
            {fill(scene.sub)}
          </p>
        )}
        <div className="vp-roll pt-4 text-3xl" aria-hidden>
          ⚽
        </div>
      </div>
    );
  }

  if (scene.type === "rule") {
    const shown = beat.kind === "step" ? beat.i + 1 : 0;
    return (
      <Board>
        <h2 className="mb-3 font-display text-2xl leading-tight">📋 {fill(scene.title)}</h2>
        <div className="space-y-2.5">
          {scene.steps.slice(0, shown).map((st, i) => (
            <Row key={i} active={i === shown - 1} className="vp-in rounded-2xl px-3 py-2 transition-colors">
              {st.sl && <div className="text-sm font-medium text-slate-600">{fill(st.sl)}</div>}
              {st.en && <SayLine text={st.en} voice={voice} className="text-xl font-extrabold leading-snug text-primary" />}
            </Row>
          ))}
        </div>
      </Board>
    );
  }

  if (scene.type === "pairs") {
    const flipped = beat.kind === "pair" ? beat.i + 1 : 0;
    return (
      <Board>
        <h2 className="mb-3 font-display text-2xl leading-tight">🔁 {fill(scene.title)}</h2>
        <div className="grid gap-1.5">
          {scene.pairs.map(([a, b], i) => (
            <Row key={i} active={i === flipped - 1} className="flex items-center gap-2 rounded-xl px-2.5 py-1.5">
              <span className="min-w-0 flex-1 truncate font-semibold">{a}</span>
              <span className="text-slate-400" aria-hidden>
                →
              </span>
              <span className="min-w-0 flex-1 text-right">
                {i < flipped ? (
                  <span key="b" className="vp-flip inline-block rounded-lg bg-slate-900 px-2 py-0.5 font-extrabold text-amber-300">
                    {b}
                  </span>
                ) : (
                  <span className="inline-block rounded-lg bg-slate-300 px-3 py-0.5 font-extrabold text-slate-500">?</span>
                )}
              </span>
            </Row>
          ))}
        </div>
      </Board>
    );
  }

  if (scene.type === "quiz") {
    const reveal = beat.kind === "reveal";
    return (
      <Board>
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-sm font-extrabold uppercase tracking-wide text-primary">🎯 {t("videoTap")}</span>
          {beat.kind === "countdown" && <Countdown key={beatIndex} />}
        </div>
        <h2 className="mb-3 font-display text-2xl leading-snug">{fill(scene.question)}</h2>
        <div className="grid gap-2">
          {scene.options.map((o, i) => {
            const right = reveal && i === scene.answer;
            const wrongPick = reveal && picked === i && i !== scene.answer;
            return (
              <button
                key={i}
                type="button"
                onClick={() => onPick(i)}
                disabled={reveal}
                className={cn(
                  "vp-in flex items-center gap-2 rounded-2xl border-2 px-4 py-3 text-left text-lg font-bold transition",
                  right ? "border-green-500 bg-green-100 text-green-900" : wrongPick ? "border-slate-300 bg-slate-100 text-slate-500 line-through" : "border-slate-200 bg-white hover:border-primary hover:bg-amber-50",
                )}
                style={{ animationDelay: `${i * 0.08}s` }}
              >
                <span className="flex-1">{o}</span>
                {right && <span aria-hidden>✅</span>}
              </button>
            );
          })}
        </div>
        {reveal && picked !== undefined && picked !== scene.answer && (
          <p className="vp-in mt-3 text-center font-semibold text-slate-600">{t("videoAlmost", { a: scene.options[scene.answer] })}</p>
        )}
      </Board>
    );
  }

  const shown = beat.kind === "point" ? beat.i + 1 : 0;
  return (
    <Board>
      <div className="flex items-center gap-3">
        <span className="vp-pop text-5xl" aria-hidden>
          🏆
        </span>
        <h2 className="font-display text-2xl leading-tight">{fill(scene.title)}</h2>
      </div>
      <ul className="mt-3 space-y-2">
        {scene.points.slice(0, shown).map((p, i) => (
          <li key={i} className="vp-in flex items-start gap-2 rounded-xl bg-slate-100 px-3 py-2 font-semibold">
            <span aria-hidden>✅</span>
            <span>{fill(p)}</span>
          </li>
        ))}
      </ul>
    </Board>
  );
}

function Countdown() {
  const [left, setLeft] = useState(COUNTDOWN_S);
  useEffect(() => {
    const id = window.setInterval(() => setLeft((n) => Math.max(0, n - 1)), 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <span className="relative grid size-11 place-items-center" aria-label={`${left}`}>
      <svg viewBox="0 0 40 40" className="absolute inset-0 -rotate-90">
        <circle cx="20" cy="20" r="18" fill="none" stroke="#e2e8f0" strokeWidth="4" />
        <circle cx="20" cy="20" r="18" fill="none" stroke="#f59e0b" strokeWidth="4" strokeDasharray="113" className="vp-ring" style={{ animationDuration: `${COUNTDOWN_S}s` }} />
      </svg>
      <span className="text-lg font-extrabold tabular-nums">{left}</span>
    </span>
  );
}

function GoalFlash({ label }: { label: string }) {
  const bits = useMemo(
    () => Array.from({ length: 18 }, (_, i) => ({ dx: `${Math.round(Math.cos(i) * 160)}px`, dy: `${Math.round(Math.sin(i * 1.7) * 140)}px`, rot: `${i * 47}deg`, c: ["#fbbf24", "#fff", "#22c55e", "#e8590c"][i % 4] })),
    [],
  );
  return (
    <div className="pointer-events-none absolute inset-0 z-20 grid place-items-center">
      <div className="confetti">
        {bits.map((b, i) => (
          <span key={i} style={{ background: b.c, ["--dx" as string]: b.dx, ["--dy" as string]: b.dy, ["--rot" as string]: b.rot }} />
        ))}
      </div>
      <div className="vp-goal font-display text-6xl font-black text-amber-300 drop-shadow-[0_4px_0_rgba(0,0,0,0.45)] sm:text-7xl">{label}</div>
    </div>
  );
}
