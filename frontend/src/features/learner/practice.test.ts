import { describe, expect, it } from "vitest";
import { goalList, type Task } from "../learning/api";
import { isTricky, trapFor } from "./PracticePlayer";

const task: Task = {
  id: "t1",
  level: 1,
  kind: "text",
  prompt: "Spain → ?",
  answer: "Spanish",
  solution: "Spanish",
  traps: [{ answer: "Spainish", why: "Narodnost: Spanish (brez 'i')." }],
};

describe("practice helpers", () => {
  it("finds a known trap answer, ignoring case and spaces", () => {
    expect(trapFor(task, "  spainish ")).toBe("Narodnost: Spanish (brez 'i').");
    expect(trapFor(task, "Spanisch")).toBeNull();
    expect(trapFor({ ...task, traps: undefined }, "Spainish")).toBeNull();
  });

  it("marks tasks worth another look", () => {
    expect(isTricky({ first: true, tries: 1, hints: 0, shown: false }, "text")).toBe(false);
    expect(isTricky({ first: false, tries: 2, hints: 0, shown: false }, "text")).toBe(true);
    expect(isTricky({ first: true, tries: 0, hints: 0, shown: true, got_it: true }, "open")).toBe(false);
    expect(isTricky(undefined, "choice")).toBe(true);
  });

  it("gives format-1 goals the same ids as the server", () => {
    expect(goalList({ sections: [], goals: ["A", "B"] })).toEqual([
      { id: "g0", text: "A" },
      { id: "g1", text: "B" },
    ]);
    expect(goalList({ sections: [], goals: [{ id: "x", text: "X", skill: "s" }] })).toEqual([{ id: "x", text: "X" }]);
    expect(goalList(undefined)).toEqual([]);
  });
});
