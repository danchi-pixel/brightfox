/**
 * "Uči se": a topic's study part, before the practice. Notes (sections with rules, tables, examples and
 * "Pazi!" boxes of typical mistakes), flashcards (flip, "I know it" / "not yet"; not-yet cards come back in
 * the round) and an "I can" checklist to tick before a test. The learner's own account saves the cards known
 * and the goals ticked (by goal id); a parent's preview isn't saved. Printable.
 */
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeftRight, ArrowRight, Check, MessageCircle, Printer, RotateCcw, Volume2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { Feedback } from "@/components/kid";
import { Button } from "@/components/ui/button";
import { ErrorState, PageLoader, Segmented } from "@/components/ui/misc";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { goalList, qk, ucApi, type StudyPart, type StudySection, type Topic } from "../learning/api";
import { LangContext, useT } from "../learning/i18n";
import { CAN_SPEAK, speak } from "../learning/speech";
import { FullScreen, RichText, SubjectBubble } from "../learning/ui";
import { useTopicScreen } from "./useTopic";

type Tab = "notes" | "cards" | "goals";

export default function LearnPage() {
  const s = useTopicScreen();
  return (
    <LangContext.Provider value={s.lang}>
      {s.error ? (
        <div className="mx-auto max-w-2xl p-4">
          <ErrorState error={s.error} />
        </div>
      ) : s.loading ? (
        <PageLoader />
      ) : !s.topic?.study ? (
        // An older topic without a study part: straight to the practice.
        <Navigate to={s.preview ? `/preview/${s.tid}` : `/l/${s.lid}/practice/${s.tid}`} replace />
      ) : (
        <Learn s={s} topic={s.topic as Topic & { study: StudyPart }} />
      )}
    </LangContext.Provider>
  );
}

function Learn({ s, topic }: { s: ReturnType<typeof useTopicScreen>; topic: Topic & { study: StudyPart } }) {
  const { t } = useT();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const study = topic.study;
  const goals = goalList(study);
  const english = topic.subject === "english";
  const saved = s.home?.topics.find((x) => x.id === topic.id)?.study_state;
  const [params] = useSearchParams();
  const [tab, setTab] = useState<Tab>(() => (params.get("tab") === "cards" && study.cards?.length ? "cards" : "notes"));
  const [known, setKnown] = useState<string[]>(saved?.known ?? []);
  const [ticked, setTicked] = useState<string[]>(saved?.ticked ?? []);
  const owl = s.owner && s.home?.tutor.configured && s.home.tutor.enabled && s.home.tutor.left_today > 0;

  const save = (nextKnown: string[], nextTicked: string[]) => {
    if (!s.owner) return; // a parent's preview isn't saved
    ucApi
      .saveProgress(s.lid, topic.id, nextKnown, nextTicked)
      .then(() => qc.invalidateQueries({ queryKey: qk.home(s.lid) }))
      .catch((e) => toast.error(errorMessage(e)));
  };

  const tabs: { value: Tab; label: string }[] = [
    { value: "notes", label: t("tabNotes") },
    ...(study.cards?.length ? [{ value: "cards" as Tab, label: t("tabCards") }] : []),
    ...(goals.length ? [{ value: "goals" as Tab, label: t("tabGoals") }] : []),
  ];

  return (
    <FullScreen title={`📖 ${t("learnTitle")} · ${topic.title}`} onClose={() => navigate(s.homePath)} closeLabel={t("leave")}>
      {!s.owner && <Feedback className="print:hidden">{t("preview")}</Feedback>}
      <div className="flex items-center gap-3">
        <SubjectBubble subject={topic.subject} />
        <h1 className="font-display text-3xl leading-tight">{topic.title}</h1>
      </div>
      {tabs.length > 1 && <Segmented<Tab> value={tab} onChange={setTab} options={tabs} className="print:hidden" />}

      {tab === "notes" && (
        <>
          {study.sections.map((sec, i) => (
            <Section key={i} section={sec} english={english} />
          ))}
          <div className="flex flex-wrap gap-2 print:hidden">
            <Button variant="secondary" size="lg" onClick={() => window.print()}>
              <Printer /> {t("printPage")}
            </Button>
            {owl && (
              <Button variant="secondary" size="lg" onClick={() => navigate(`/l/${s.lid}/chat/new?topic=${topic.id}`)}>
                <MessageCircle /> {t("askAboutThis")}
              </Button>
            )}
            <Button variant="primary" size="lg" className="flex-1" onClick={() => setTab(study.cards?.length ? "cards" : "goals")} disabled={tabs.length < 2}>
              {study.cards?.length ? t("tabCards") : t("tabGoals")} <ArrowRight />
            </Button>
          </div>
        </>
      )}

      {tab === "cards" && study.cards && (
        <Flashcards
          cards={study.cards}
          english={english}
          known={known}
          onKnown={(k) => {
            setKnown(k);
            save(k, ticked);
          }}
        />
      )}

      {tab === "goals" && goals.length > 0 && (
        <div className="space-y-3">
          <p className="text-muted-foreground">{t("goalsIntro")}</p>
          {goals.map((g) => {
            const on = ticked.includes(g.id);
            return (
              <button
                key={g.id}
                type="button"
                aria-pressed={on}
                onClick={() => {
                  const next = on ? ticked.filter((x) => x !== g.id) : goals.map((x) => x.id).filter((id) => id === g.id || ticked.includes(id));
                  setTicked(next);
                  save(known, next);
                }}
                className={cn(
                  "flex w-full items-center gap-3 rounded-2xl border-2 px-4 py-3.5 text-left text-base font-medium transition-colors",
                  on ? "border-success bg-success/10" : "border-border bg-card hover:border-input",
                )}
              >
                <span className={cn("grid size-7 shrink-0 place-items-center rounded-lg border-2", on ? "border-success bg-success text-white" : "border-input")}>
                  {on && <Check className="size-4" />}
                </span>
                {g.text}
              </button>
            );
          })}
          {ticked.length === goals.length && <Feedback>{t("goalsAll")}</Feedback>}
        </div>
      )}

      <Button
        variant={tab === "goals" ? "primary" : "secondary"}
        size="lg"
        className="w-full print:hidden"
        onClick={() => navigate(s.preview ? `/preview/${topic.id}` : `/l/${s.lid}/practice/${topic.id}`)}
      >
        ✏️ {t("toPractice")} <ArrowRight />
      </Button>
    </FullScreen>
  );
}

function Section({ section, english }: { section: StudySection; english: boolean }) {
  const { t } = useT();
  const say = section.table?.say ?? [];
  const canListen = english && CAN_SPEAK;
  return (
    <section className="space-y-3 rounded-2xl border border-border bg-card p-4 print:break-inside-avoid print:border-black/30">
      <h2 className="font-display text-xl">{section.title}</h2>
      {section.text && <RichText text={section.text} className="leading-relaxed" />}
      {section.table && (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-[15px]">
            <thead>
              <tr>
                {section.table.head.map((h) => (
                  <th key={h} className="border-b border-border px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {h}
                  </th>
                ))}
                {canListen && say.length > 0 && <th className="w-10 border-b border-border print:hidden" />}
              </tr>
            </thead>
            <tbody>
              {section.table.rows.map((row, ri) => (
                <tr key={ri} className="odd:bg-card-2/60">
                  {row.map((cell, ci) => (
                    <td key={ci} className={cn("px-2 py-1.5", say.includes(ci) && "font-medium")}>
                      {cell}
                    </td>
                  ))}
                  {canListen && say.length > 0 && (
                    <td className="px-1 py-1 text-right print:hidden">
                      <button
                        type="button"
                        onClick={() => speak(say.map((i) => row[i]).filter(Boolean).join(". "))}
                        className="rounded-lg p-1.5 text-primary hover:bg-primary-soft"
                        aria-label={t("listenRow")}
                      >
                        <Volume2 className="size-4" />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {section.examples && (
        <ul className="space-y-1.5">
          {section.examples.map((ex, i) => (
            <li key={i} className="flex items-center gap-2 rounded-xl bg-card-2 px-3 py-2">
              <span className="flex-1">{ex}</span>
              {canListen && (
                <button type="button" onClick={() => speak(ex)} className="rounded-lg p-1.5 text-primary hover:bg-primary-soft print:hidden" aria-label={t("listenRow")}>
                  <Volume2 className="size-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {section.watch_out && (
        <div className="space-y-2 rounded-xl border border-warning/40 bg-warning/10 p-3">
          <div className="text-sm font-bold text-warning">⚠️ {t("watchOut")}</div>
          {section.watch_out.map((w, i) => (
            <div key={i} className="space-y-0.5">
              <div>
                <span className="mr-1">❌</span>
                <span className="text-muted-foreground line-through">{w.wrong}</span>
              </div>
              <div className="font-semibold">
                <span className="mr-1">✅</span>
                {w.right}
              </div>
              {w.why && <div className="text-sm text-muted-foreground">{w.why}</div>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/** Flip cards: the ones not known yet, round after round; "not yet" sends a card to the end of the round. */
function Flashcards({ cards, english, known, onKnown }: { cards: { front: string; back: string }[]; english: boolean; known: string[]; onKnown: (known: string[]) => void }) {
  const { t } = useT();
  const [reverse, setReverse] = useState(false);
  const [queue, setQueue] = useState<string[]>(() => cards.filter((c) => !known.includes(c.back)).map((c) => c.back));
  const [flipped, setFlipped] = useState(false);
  const byBack = useMemo(() => new Map(cards.map((c) => [c.back, c])), [cards]);
  const card = queue.length ? byBack.get(queue[0]) : undefined;
  const front = card && (reverse ? card.back : card.front);
  const backSide = card && (reverse ? card.front : card.back);

  // A new card starts face down.
  useEffect(() => setFlipped(false), [queue[0], reverse]); // eslint-disable-line react-hooks/exhaustive-deps

  const answer = (knowIt: boolean) => {
    if (!card) return;
    if (knowIt) {
      if (!known.includes(card.back)) onKnown([...known, card.back]);
      setQueue((q) => q.slice(1));
    } else {
      setQueue((q) => [...q.slice(1), q[0]]);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>{t("cardsKnown", { n: known.length, total: cards.length })}</span>
        <Button variant="ghost" size="sm" onClick={() => setReverse((r) => !r)}>
          <ArrowLeftRight /> {reverse ? t("dirBack") : t("dirForward")}
        </Button>
      </div>
      {card ? (
        <>
          <button
            type="button"
            onClick={() => {
              setFlipped(true);
              if (english && CAN_SPEAK && !reverse) speak(card.back);
            }}
            className={cn(
              "flex min-h-52 w-full flex-col items-center justify-center gap-3 rounded-3xl border-2 p-6 text-center transition-colors",
              flipped ? "border-primary bg-primary-soft" : "border-border bg-card hover:border-input",
            )}
          >
            <span className="text-2xl font-bold">{front}</span>
            {flipped ? <span className="text-3xl font-extrabold text-primary">{backSide}</span> : <span className="text-sm text-muted-foreground">{t("flip")} 👆</span>}
          </button>
          {flipped ? (
            <div className="flex gap-2">
              <Button variant="secondary" size="xl" className="flex-1" onClick={() => answer(false)}>
                {t("notYetCard")}
              </Button>
              <Button variant="primary" size="xl" className="flex-1" onClick={() => answer(true)}>
                <Check /> {t("knowIt")}
              </Button>
            </div>
          ) : (
            // Listening before turning over only when the front is the English side (it would give the answer away).
            english &&
            reverse &&
            CAN_SPEAK && (
              <Button variant="soft" size="lg" className="w-full" onClick={() => speak(card.back)}>
                <Volume2 /> {t("listen")}
              </Button>
            )
          )}
          <p className="text-center text-xs text-muted-foreground">{t("cardsLeft", { n: queue.length })}</p>
        </>
      ) : (
        <div className="space-y-3 text-center">
          <Feedback>{t("allCardsKnown")}</Feedback>
          <Button variant="secondary" size="lg" onClick={() => setQueue(cards.map((c) => c.back))}>
            <RotateCcw /> {t("cardsAgain")}
          </Button>
        </div>
      )}
    </div>
  );
}
