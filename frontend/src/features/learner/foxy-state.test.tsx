// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import { api } from "@/lib/api";
import type { ChatView, LearnerHome, Task, Topic } from "../learning/api";
import ChatPage from "../tutor/ChatPage";
import LearnPage from "./LearnPage";
import PracticePage from "./PracticePage";

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ language: "en" }) }));

const first: Task = { id: "first", kind: "number", level: 1, prompt: "First task", answer: 4, solution: "Four", skill: "skill" };
const variants: Task[] = [
  { id: "current", kind: "number", level: 2, prompt: "Number task", answer: 9, solution: "Nine" },
  { id: "current", kind: "text", level: 2, prompt: "Text task", answer: "nine", solution: "Nine" },
  { id: "current", kind: "choice", level: 2, prompt: "Choice task", options: ["Wrong choice", "Right choice", "Another choice"], answer: 1, solution: "Nine" },
  { id: "current", kind: "open", level: 2, prompt: "Notebook task", solution: "Nine" },
];
let topic: Topic;
let home: LearnerHome;
let client: QueryClient;
let post: MockInstance<typeof api.post>;
const chat: ChatView = {
  chat: { id: 7, subject: "math", title: "Scratch chat", topic_id: "scratch", task_id: "current", parent_test: false, messages: 2, created_at: "", updated_at: "" },
  messages: [{ id: 1, role: "assistant", text: "Scratch Foxy reply", images: [], created_at: "" }],
  can_send: true,
};

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Tests must not use a real server or AI"); }));
  Element.prototype.scrollIntoView = vi.fn();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() });
  topic = { id: "scratch", version: 1, subject: "math", grade: 5, title: "Scratch topic", intro: "", tasks: [], study: { sections: [{ title: "Notes", text: "Scratch notes" }], goals: ["Scratch goal"] } };
  home = {
    learner: { id: 1, name: "Scratch learner", avatar: "", color: "", grade: 5 }, owner: true, lang: "en",
    tutor: { configured: true, enabled: true, daily_limit: 20, left_today: 20 }, chats: [],
    topics: [{ ...topic, tasks: 2, learn: 0, levels: [1, 2], extras: 0, challenge: 2, cards: 0, goals: 1, skills: 1, for: [], has_parent_card: false, video: 0, oral: 0, runs: 0, finished: 0, last: null, challenge_state: { tasks: 2, unlocked: true, cleared: false }, study_state: null }],
  };
  vi.spyOn(api, "get").mockImplementation(async (path) => {
    if (path.includes("/home?")) return structuredClone(home);
    if (path.endsWith("/topics/scratch")) return structuredClone(topic);
    if (path.endsWith("/chats/7")) return chat;
    throw new Error(`Unexpected test GET: ${path}`);
  });
  post = vi.spyOn(api, "post").mockImplementation(async (path) => {
    if (path.includes("/chats")) return chat;
    if (path.endsWith("/runs")) return {};
    throw new Error(`Unexpected test POST: ${path}`);
  });
  vi.spyOn(api, "put").mockResolvedValue({});
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
});

afterEach(() => { cleanup(); client.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function Location() { const l = useLocation(); return <output data-testid="location">{l.pathname}{l.search}</output>; }
function mount(path: string) {
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <Location /><Routes>
      <Route path="/l/:lid/practice/:tid" element={<PracticePage />} />
      <Route path="/l/:lid/learn/:tid" element={<LearnPage />} />
      <Route path="/l/:lid/chat/:cid" element={<ChatPage />} />
      <Route path="/l/:lid" element={<p>Classroom</p>} />
    </Routes>
  </MemoryRouter></QueryClientProvider>);
}
const click = (name: string | RegExp) => fireEvent.click(screen.getByRole("button", { name }));
const input = () => screen.getByRole("textbox", { name: "Your answer" }) as HTMLInputElement;
const answer = (value: string) => { fireEvent.change(input(), { target: { value } }); click("Check"); };
async function prepare(task = variants[0], suffix = "") {
  const current = { ...task, hints: ["Scratch hint", "Second hint"], skill: "skill" };
  topic.tasks = [first, current]; topic.challenge = topic.tasks;
  // Skill-filtered practice must not accidentally reset or switch to the unfiltered queue.
  if (suffix.includes("skill")) topic.tasks = [...topic.tasks, { ...first, id: "excluded", skill: "other" }];
  mount(`/l/1/practice/scratch${suffix}`);
  if (suffix.includes("challenge")) fireEvent.click(await screen.findByRole("button", { name: "Take the challenge" }));
  await screen.findByRole("heading", { name: first.prompt });
  answer("4"); click("Next");
  await screen.findByRole("heading", { name: current.prompt });
  click(/Hint 1/);
  if (task.kind === "open") click("Show the solution");
  else if (task.kind === "choice") { click("Wrong choice"); click("Check"); click("Right choice"); }
  else answer("incorrect draft");
}
async function openHelp() {
  const opener = screen.getByRole("button", { name: "Ask Foxy about this" });
  opener.focus(); fireEvent.click(opener);
  return screen.findByRole("dialog", { name: "Foxy" });
}
async function closeHelp(escape = false) {
  const dialog = screen.getByRole("dialog", { name: "Foxy" });
  if (escape) fireEvent.keyDown(dialog, { key: "Escape", code: "Escape" });
  else fireEvent.click(within(dialog).getByRole("button", { name: "Back" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
}

describe("Ask Foxy keeps the mounted exercise", () => {
  for (const suffix of ["", "?challenge=1", "?skill=skill"]) {
    for (const task of variants) {
      it(`preserves ${task.kind} answers, progress and mistakes after repeated help visits (${suffix || "practice"})`, async () => {
        await prepare(task, suffix);
        const originalInput = task.kind === "number" || task.kind === "text" ? input() : null;
        const choiceOrder = task.kind === "choice" ? screen.getAllByRole("button").filter((el) => el.hasAttribute("aria-pressed")) : [];
        for (let i = 0; i < 3; i++) {
          await openHelp();
          expect(screen.getByTestId("location").textContent).toBe(`/l/1/practice/scratch${suffix}`);
          expect(post).not.toHaveBeenCalled(); // Opening help must not prematurely save/end the run.
          await closeHelp(i === 1);
          expect(screen.getByText("Task 2 of 2")).toBeTruthy();
          expect(screen.getByText("Scratch hint")).toBeTruthy();
          expect(document.activeElement).toBe(screen.getByRole("button", { name: "Ask Foxy about this" }));
          if (originalInput) { expect(input()).toBe(originalInput); expect(input().value).toBe("incorrect draft"); }
          if (task.kind === "choice") {
            expect((screen.getByRole("button", { name: "Wrong choice" }) as HTMLButtonElement).disabled).toBe(true);
            expect(screen.getByRole("button", { name: "Right choice" }).getAttribute("aria-pressed")).toBe("true");
            expect(screen.getAllByRole("button").filter((el) => el.hasAttribute("aria-pressed"))).toEqual(choiceOrder);
          }
          if (task.kind === "open") expect(screen.getByText("Nine")).toBeTruthy();
        }
        if (task.kind === "open") click("I've got it");
        else { if (task.kind === "choice") click("Check"); else answer(task.kind === "text" ? "nine" : "9"); click("Next"); }
        await waitFor(() => expect(post).toHaveBeenCalledWith("/api/learners/1/topics/scratch/runs", expect.objectContaining({
          finished: true, challenge: suffix.includes("challenge"),
          results: {
            first: { first: true, tries: 1, hints: 0, shown: false, wrong: [] },
            current: task.kind === "open"
              ? { first: true, tries: 0, hints: 1, shown: true, wrong: [], got_it: true }
              : { first: false, tries: 2, hints: 1, shown: false, wrong: [task.kind === "choice" ? "Wrong choice" : "incorrect draft"] },
          },
        })));
        if (task.kind !== "open") {
          click("Practise these again");
          expect(screen.getByText("Task 1 of 1")).toBeTruthy();
          expect(screen.queryByText("Scratch hint")).toBeNull();
          if (originalInput) expect(input().value).toBe("");
        }
      });
    }
  }

  it("sending the first chat message stays on the exercise, even when the daily quota runs out", async () => {
    await prepare();
    const dialog = await openHelp();
    home.tutor.left_today = 0;
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "Help with this task" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Send" }));
    await screen.findByText("Scratch Foxy reply");
    expect(post).toHaveBeenCalledWith("/api/learners/1/chats", expect.objectContaining({ text: "Help with this task", images: [], topic_id: "scratch", task_id: "current" }));
    expect(screen.getByTestId("location").textContent).toBe("/l/1/practice/scratch");
    await closeHelp();
    expect(input().value).toBe("incorrect draft");
    expect(screen.getByText("Task 2 of 2")).toBeTruthy();
    expect(post.mock.calls.filter(([path]) => path.endsWith("/runs"))).toHaveLength(0);
  });

  it("closing help while a reply is pending cannot navigate away when it arrives", async () => {
    await prepare();
    let resolve!: (value: ChatView) => void;
    post.mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    const dialog = await openHelp();
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "Please help" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Send" }));
    await closeHelp();
    await act(async () => { resolve(chat); });
    expect(screen.getByTestId("location").textContent).toBe("/l/1/practice/scratch");
    expect(input().value).toBe("incorrect draft");
    await openHelp(); await closeHelp();
    expect(input().value).toBe("incorrect draft");
  });

  it("study help also returns to the same study screen", async () => {
    mount("/l/1/learn/scratch");
    await screen.findByText("Scratch notes");
    const notes = screen.getByText("Scratch notes");
    for (let i = 0; i < 2; i++) {
      await openHelp(); await closeHelp();
      expect(screen.getByText("Scratch notes")).toBe(notes);
      expect(screen.getByTestId("location").textContent).toBe("/l/1/learn/scratch");
    }
  });

  it("standalone chat still gets its own address and closes to the classroom", async () => {
    mount("/l/1/chat/new?topic=scratch&task=current");
    const box = await screen.findByRole("textbox");
    fireEvent.change(box, { target: { value: "Standalone question" } });
    click("Send");
    await waitFor(() => expect(screen.getByTestId("location").textContent).toBe("/l/1/chat/7"));
    click("Back");
    expect(screen.getByText("Classroom")).toBeTruthy();
  });
});
