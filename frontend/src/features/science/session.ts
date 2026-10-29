import type { Bank, Mode, Progress, Question, Session } from "./types";

export function shuffle<T>(items: T[], random = Math.random): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) { const j = Math.floor(random() * (i + 1)); [out[i], out[j]] = [out[j], out[i]]; }
  return out;
}
export function recallKey(mode: Mode, qid: string) { return `${mode === "cards" ? "cards" : "practice"}:${qid}`; }
export function makeSession(bank: Bank, mode: Mode, progress: Progress, lesson = "all", count = 7, weak = false): Session {
  let pool = bank.questions.filter(q => mode === "mock" || lesson === "all" || q.topic === lesson);
  pool = pool.filter(q => mode === "quiz" ? q.kind !== "oral" : mode === "images" ? !!q.image : mode === "cards" ? !!q.card : q.kind === "oral");
  if (weak) pool = pool.filter(q => { const r = progress.answers[recallKey(mode, q.id)]; return r && r.rating !== "know"; });
  pool = shuffle(pool);
  if (mode === "mock") {
    // Round-robin topics makes a short mock genuinely cover different areas.
    const groups = shuffle([...new Set(pool.map(q => q.topic))]).map(id => pool.filter(q => q.topic === id));
    const mixed: Question[] = [];
    while (groups.some(g => g.length)) for (const g of groups) { const q = g.shift(); if (q) mixed.push(q); }
    pool = mixed.slice(0, count);
    // Include an image-based question whenever the selected scope has one.
    if (!pool.some(q => q.image)) {
      const visual = mixed.find(q => q.image && !pool.some(p => p.id === q.id));
      if (visual && pool.length) {
        const sameTopic = pool.findIndex(q => q.topic === visual.topic);
        pool[sameTopic >= 0 ? sameTopic : pool.length - 1] = visual;
      }
    }
  } else if (mode === "cards" || weak) {
    const priority = (q: Question) => {
      const r = progress.answers[recallKey(mode, q.id)];
      if (!r) return 1;
      if (r.rating !== "know") return 0;
      return Date.parse(r.due) <= Date.now() ? 2 : 3;
    };
    pool.sort((a, b) => priority(a) - priority(b));
  }
  // Topic practice starts gently, while review and mock sessions keep varied order.
  if (lesson !== "all" && mode === "oral" && !weak) pool.sort((a, b) => a.difficulty - b.difficulty);
  return { mode, queue: pool.slice(0, mode === "mock" ? count : 12).map(q => q.id), index: 0, ratings: {} };
}
export function normalize(s: string) { return s.trim().toLocaleLowerCase("sl").replace(/\s+/g, " ").replace(/[.!?]+$/, ""); }
export function isCorrect(q: Question, values: string[]) {
  if (q.kind === "fill") return (q.correct ?? []).some(x => normalize(x) === normalize(values[0] ?? ""));
  return values.length === q.correct?.length && values.every((x, i) => normalize(x) === normalize(q.correct![i]));
}
