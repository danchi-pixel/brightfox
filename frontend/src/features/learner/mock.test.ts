import { describe, expect, it } from "vitest";
import type { Mock, MockTask } from "../learning/api";
import { isRight, scoreMock } from "./MockPage";

const base = { level: 2 as const, solution: "S", topic: "t", points: 1 };
const tasks: MockTask[] = [
  { ...base, id: "a", kind: "text", prompt: "Spain →", answer: "Spanish" },
  { ...base, id: "b", kind: "choice", prompt: "x", options: ["Her", "His"], answer: 0, points: 2 },
  { ...base, id: "c", kind: "number", prompt: "3/4 od 8", answer: 6 },
  { ...base, id: "d", kind: "open", prompt: "Write", points: 5 },
];
const mock: Mock = { id: "m", version: 1, subject: "english", grade: 6, title: "M", intro: "", minutes: 30, topics: ["t"], sections: [{ title: "A", tasks }] };

describe("mock tests", () => {
  it("checks typed answers like the practice does", () => {
    expect(isRight(tasks[0], " spanish ")).toBe(true);
    expect(isRight(tasks[0], "Spain")).toBe(false);
    expect(isRight(tasks[1], "Her")).toBe(true);
    expect(isRight(tasks[2], "6,0")).toBe(true);
    expect(isRight(tasks[2], "")).toBe(false);
  });

  it("adds up points, with open tasks by the learner's own check", () => {
    expect(scoreMock(mock, { a: { right: true }, b: { right: false }, c: { right: true }, d: { right: false, got_it: true } })).toEqual({ points: 7, max: 9 });
    expect(scoreMock(mock, {})).toEqual({ points: 0, max: 9 });
  });
});
