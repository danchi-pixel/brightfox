import { describe, expect, it } from "vitest";
import type { VideoScene } from "../learning/api";
import { beatsOf, fillName, matchMinute, quizCount, readingMs } from "./video";

const scenes: VideoScene[] = [
  { type: "intro", title: "Tekma", foxy: "Živjo, {name}!" },
  { type: "rule", title: "has got", steps: [{ sl: "he → has got", en: "He has got a ball." }, { en: "She has got a dog." }] },
  { type: "pairs", title: "Narodnosti", pairs: [["Japan", "Japanese"], ["Holland", "Dutch"]], say: [0, 1] },
  { type: "quiz", question: "Holland → ?", options: ["Hollish", "Dutch"], answer: 1 },
  { type: "recap", title: "Konec", points: ["A", "B", "C"] },
];

describe("video lesson", () => {
  it("turns every scene into beats in order", () => {
    expect(scenes.map((s) => beatsOf(s).length)).toEqual([1, 3, 3, 3, 4]);
    expect(beatsOf(scenes[3]).map((b) => b.kind)).toEqual(["ask", "countdown", "reveal"]);
    expect(beatsOf(scenes[1])[2]).toEqual({ kind: "step", i: 1 });
  });

  it("puts the learner's name in, or leaves it out neatly", () => {
    expect(fillName("Živjo, {name}! Gremo.", "Erik")).toBe("Živjo, Erik! Gremo.");
    expect(fillName("{name}, sezona se začne.", null)).toBe("Sezona se začne.");
    expect(fillName("Bravo, {name}! Zdaj pa v Vajo.", undefined)).toBe("Bravo! Zdaj pa v Vajo.");
    expect(fillName("Še malo, {name}!", "")).toBe("Še malo!");
  });

  it("gives captions time to be read and runs the clock to 90'", () => {
    expect(readingMs("Kratko.")).toBeGreaterThanOrEqual(1400);
    expect(readingMs("x".repeat(1000))).toBe(9000);
    expect(matchMinute(0, 19)).toBe(1);
    expect(matchMinute(9, 19)).toBe(45);
    expect(matchMinute(18, 19)).toBe(90);
    expect(quizCount(scenes)).toBe(1);
  });
});
