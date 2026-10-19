/**
 * The video lesson's script, as beats: each scene becomes a short list of moments the player shows one after
 * another (a title, a rule's step, a pair on the flip board, a quiz's question / countdown / answer). Pure
 * functions, so the order and timing can be tested without a browser.
 */
import type { VideoScene } from "../learning/api";

export type Beat =
  | { kind: "open" } // the scene appears; Foxy says the scene's "foxy" line
  | { kind: "step"; i: number } // rule step i
  | { kind: "pair"; i: number } // pair i flips
  | { kind: "point"; i: number } // recap point i
  | { kind: "ask" } // quiz: the question and the options
  | { kind: "countdown" } // quiz: time to tap an answer
  | { kind: "reveal" }; // quiz: the right answer and why

export const COUNTDOWN_S = 6;

export function beatsOf(scene: VideoScene): Beat[] {
  switch (scene.type) {
    case "intro":
      return [{ kind: "open" }];
    case "rule":
      return [{ kind: "open" }, ...scene.steps.map((_, i) => ({ kind: "step" as const, i }))];
    case "pairs":
      return [{ kind: "open" }, ...scene.pairs.map((_, i) => ({ kind: "pair" as const, i }))];
    case "recap":
      return [{ kind: "open" }, ...scene.points.map((_, i) => ({ kind: "point" as const, i }))];
    case "quiz":
      return [{ kind: "ask" }, { kind: "countdown" }, { kind: "reveal" }];
  }
}

/** "{name}" becomes the learner's name; without a name (a parent's preview) it's left out with its comma. */
export function fillName(text: string, name?: string | null): string {
  if (name) return text.split("{name}").join(name);
  return text
    .replace(/\{name\},\s*/g, "")
    .replace(/,\s*\{name\}/g, "")
    .replace(/\s*\{name\}/g, "")
    .replace(/^\s*(\p{Ll})/u, (m) => m.toUpperCase());
}

/** How long a caption stays when it isn't read aloud: long enough for an 11-year-old to read it. */
export function readingMs(text: string): number {
  return Math.min(9000, 1400 + text.length * 60);
}

/** The match clock in the scoreboard: the video runs from 1' to 90'. */
export function matchMinute(sceneIndex: number, scenes: number): number {
  if (scenes <= 1) return 90;
  return Math.max(1, Math.round((sceneIndex / (scenes - 1)) * 90));
}

/** Quizzes in the video (for "your goals: n of m"). */
export function quizCount(scenes: VideoScene[]): number {
  return scenes.filter((s) => s.type === "quiz").length;
}
