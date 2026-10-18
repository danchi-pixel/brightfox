import { describe, expect, it } from "vitest";
import { normalizeText, numberCandidates, numberIsRight, textIsRight } from "./answers";

describe("typed numbers", () => {
  it.each([
    ["5", [5]],
    ["-3", [-3]],
    ["2,5", [2.5]],
    ["2.5", [2.5]],
    ["3/4", [0.75]],
    ["1 3/4", [1.75]],
    ["1 500", [1500]],
    ["12 cm", [12]],
    ["6 €", [6]],
    ["1.234,5", [1234.5]],
    ["", []],
    ["abc", []],
    ["3/0", []],
  ])("%s", (input, expected) => {
    expect(numberCandidates(input)).toEqual(expected);
  });

  it("reads 1.500 as 1,5 or as 1500 (Slovenian thousands)", () => {
    expect(numberCandidates("1.500").sort((a, b) => a - b)).toEqual([1.5, 1500]);
    expect(numberIsRight("1.500", 1500)).toBe(true);
    expect(numberIsRight("1.500", "1,5")).toBe(true);
  });

  it("compares values, so 0,75 is right for 3/4", () => {
    expect(numberIsRight("0,75", "3/4")).toBe(true);
    expect(numberIsRight("3/10", "3/10")).toBe(true);
    expect(numberIsRight("1 1/2", 1.5)).toBe(true);
    expect(numberIsRight("40 min", 40)).toBe(true);
    expect(numberIsRight("41", 40)).toBe(false);
    expect(numberIsRight("1/3", "0,333")).toBe(false);
  });
});

describe("typed words", () => {
  it("ignores case, spaces and a full stop; č š ž only matter when exact", () => {
    expect(normalizeText("  Polovica. ")).toBe("polovica");
    expect(textIsRight("pol", { answer: "polovica", accept: ["pol"] })).toBe(true);
    expect(textIsRight("macka", { answer: "mačka" })).toBe(true);
    expect(textIsRight("macka", { answer: "mačka", exact: true })).toBe(false);
    expect(textIsRight("Mačka", { answer: "mačka", exact: true })).toBe(true);
    expect(textIsRight("", { answer: "mačka" })).toBe(false);
  });

  it("accepts whole sentences typed on a phone: ’ for ', commas, a final full stop or question mark", () => {
    expect(textIsRight("No, I can’t", { answer: "can't", accept: ["No I can't"] })).toBe(true);
    expect(textIsRight("Ronaldo can play football, but he can't fly", { answer: "Ronaldo can play football but he can't fly." })).toBe(true);
    expect(textIsRight("how many languages can you speak", { answer: "How many languages can you speak?" })).toBe(true);
    expect(textIsRight("His favourite football player is Mbappe.", { answer: "His favourite football player is Mbappé." })).toBe(true);
    expect(textIsRight("Hes favourite football player is Mbappé", { answer: "His favourite football player is Mbappé." })).toBe(false);
  });
});
