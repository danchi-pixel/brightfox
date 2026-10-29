/** BrightFox's API, typed as the server sends it (topic format: docs/content-format.md). */
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { todayISO } from "@/lib/dates";

export type Subject = "math" | "slovene" | "english" | "science" | "society" | "other";
export const SUBJECTS: Subject[] = ["math", "slovene", "english", "science", "society", "other"];

export interface LearnCard {
  title: string;
  text: string;
  example?: string;
}

export interface Task {
  id: string;
  /** 1 warm-up, 2 practice, 3 challenge. */
  level: 1 | 2 | 3;
  kind: "choice" | "number" | "text" | "open";
  prompt: string;
  options?: string[];
  /** choice: the right option (index); number: a number, "2,5", "3/4" or "1 3/4"; text: the word. */
  answer?: number | string;
  accept?: string[];
  exact?: boolean;
  unit?: string;
  hints?: string[];
  solution: string;
  extra?: boolean;
  /** English the browser reads aloud (dictation). */
  say?: string;
  skill?: string;
  /** Known wrong answers with the reason, shown when typed. */
  traps?: { answer: string; why: string }[];
}

export interface StudySection {
  title: string;
  text?: string;
  table?: { head: string[]; rows: string[][]; say?: number[] };
  examples?: string[];
  watch_out?: { wrong: string; right: string; why?: string }[];
  skill?: string;
}

export type Goal = string | { id: string; text: string; skill?: string };

export interface StudyPart {
  goals?: Goal[];
  sections: StudySection[];
  cards?: { front: string; back: string; skill?: string }[];
}

/** Goals as {id, text}: format-1 topics list plain texts, which get the ids g0, g1, ... (as on the server). */
export function goalList(study: StudyPart | undefined): { id: string; text: string }[] {
  return (study?.goals ?? []).map((g, i) => (typeof g === "string" ? { id: `g${i}`, text: g } : { id: g.id, text: g.text }));
}

export interface ParentCard {
  school_method?: string;
  typical_mistakes?: string[];
  car_questions?: { q: string; a: string }[];
  tips?: string[];
}

/** A video lesson's scenes (🎬). Slovene lines are captions, English ones are read aloud; "{name}" is the learner. */
export type VideoScene =
  | { type: "intro"; skill?: string; foxy?: string; title: string; sub?: string; emoji?: string }
  | { type: "rule"; skill?: string; foxy?: string; title: string; steps: { sl?: string; en?: string }[] }
  | { type: "pairs"; skill?: string; foxy?: string; title: string; pairs: [string, string][]; say?: (0 | 1)[] }
  | { type: "quiz"; skill?: string; foxy?: string; question: string; say?: string; options: string[]; answer: number; explain?: string }
  | { type: "recap"; skill?: string; foxy?: string; title: string; points: string[] };

export interface Video {
  title: string;
  scenes: VideoScene[];
}

export interface Topic {
  id: string;
  version: number;
  format?: 1 | 2;
  video?: Video;
  subject: Subject;
  grade: number;
  title: string;
  intro: string;
  source?: string;
  for?: string[];
  skills?: { id: string; title: string }[];
  learn?: LearnCard[];
  study?: StudyPart;
  tasks: Task[];
  challenge?: Task[];
  parent?: ParentCard;
  terms?: { term: string; meaning: string }[];
}

export interface TopicCard {
  has_lab?: boolean;
  id: string;
  version: number;
  subject: Subject;
  grade: number;
  title: string;
  intro: string;
  tasks: number;
  learn: number;
  levels: number[];
  extras: number;
  challenge: number;
  cards: number;
  goals: number;
  skills: number;
  for: string[];
  has_parent_card: boolean;
  /** Number of oral-exam questions. */
  oral: number;
  /** Number of scenes in the video lesson (0: none). */
  video: number;
}

export interface Runs {
  runs: number;
  finished: number;
  last: string | null;
}

export interface ChallengeState {
  tasks: number;
  unlocked: boolean;
  cleared: boolean;
}

export interface StudyState {
  cards: number;
  known: string[];
  goals: number;
  goal_ids: string[];
  ticked: string[];
}

export type LearnerTopicCard = TopicCard & Runs & { challenge_state: ChallengeState | null; study_state: StudyState | null };

export interface TaskResult {
  first: boolean;
  tries: number;
  hints: number;
  shown: boolean;
  got_it?: boolean | null;
  wrong?: string[];
}

export interface ChatCard {
  id: number;
  subject: Subject;
  title: string;
  topic_id: string | null;
  task_id: string | null;
  parent_test: boolean;
  messages: number;
  created_at: string;
  updated_at: string;
  cost_usd?: number;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
  images: string[];
  created_at: string;
}

export interface ChatView {
  chat: ChatCard;
  messages: ChatMessage[];
  can_send: boolean;
  left_today?: number;
}

export interface LearnerHome {
  learner: { id: number; name: string; avatar: string; color: string; grade: number | null };
  /** The learner themselves (false: a parent's preview, nothing is saved). */
  owner: boolean;
  lang: "sl" | "en";
  tutor: { configured: boolean; enabled: boolean; daily_limit: number; left_today: number };
  topics: LearnerTopicCard[];
  chats: ChatCard[];
}

/* ------------------------------------------------------------- parent side */

export interface StudioTopicCard extends TopicCard {
  scope: "global" | "family";
  learner_ids: number[];
  outdated_ids: number[];
  approved: boolean;
  progress: Record<string, Runs>;
}

export interface RunSummary {
  date: string;
  finished: boolean;
  done: number;
  total: number;
  first: number;
  tricky: { id: string; wrong: string[]; shown: boolean; hints: number }[];
}

export interface LearnerBrief {
  id: number;
  name: string;
  avatar: string;
  color: string;
}

export interface TopicResults {
  learners: (Runs & {
    learner: LearnerBrief;
    latest: RunSummary | null;
    challenge: (ChallengeState & { latest: RunSummary | null }) | null;
    study: StudyState | null;
    tasks: Record<string, { seen: number; first: number; shown: number; hints: number; not_yet: number; wrong: string[] }>;
  })[];
}

export interface Overview {
  family: { id: number; name: string };
  local_auto_assignment?: boolean;
  tutor: { configured: boolean; model: string; effort: string; month_calls: number; month_cost_usd: number; budget_usd: number | null };
  subjects: Subject[];
  learners: (LearnerBrief & {
    grade: number | null;
    tutor_enabled: boolean;
    tutor_daily_limit: number;
    today_messages: number;
    month_calls: number;
    month_cost_usd: number;
  })[];
}

export interface Learner extends LearnerBrief {
  grade: number | null;
  language: "sl" | "en";
  interests: string;
  tutor_enabled: boolean;
  tutor_daily_limit: number;
  tutor_notes: string;
  rhythm: { days: number[]; minutes: number } | null;
  archived: boolean;
  sort_order: number;
  username: string | null;
}

export interface FamilyView {
  id: number;
  slug: string;
  name: string;
  timezone: string;
  language: "sl" | "en";
  settings: Record<string, unknown>;
  learners: Learner[];
}

export interface Account {
  id: number;
  username: string;
  role: "admin" | "learner";
  learner_id: number | null;
  learner_name: string | null;
  created_at: string;
}

export interface AiSettings {
  jobs: {
    job: "tutor_chat" | "oral_grading" | "open_feedback";
    label: string;
    model: string;
    effort: string;
    options: { id: string; label: string; tier: string }[];
    month_calls: number;
    month_cost_usd: number;
    per_100_usd: number | null;
  }[];
  budget_usd: number | null;
}

/* ------------------------------------------------------------- tests, mastery, gaps, review */

export type MasteryLabel = "know" | "almost" | "not_yet" | "not_started";

export interface SkillMastery {
  skill_id: string;
  title: string;
  tasks: number;
  mastery: number | null;
  label: MasteryLabel;
  parts: Record<string, { done: number; total: number }>;
}

export interface Exam {
  id: number;
  subject: Subject;
  title: string;
  exam_date: string;
  kind: "written" | "oral";
  target_grade: number | null;
  notes: string;
  result_grade: number | null;
  days_left: number;
  scope: { topic_id: string; skill_id: string | null; topic_title: string | null }[];
  readiness: number | null;
  skills: (SkillMastery & { topic_id: string; topic_title: string | null })[];
}

export interface PlanStep {
  key: string;
  kind: "learn" | "cards" | "practice" | "challenge" | "review" | "mock";
  topic_id: string | null;
  skill_id: string | null;
  title: string;
  minutes: number;
  done: boolean;
}

export interface ExamDetail extends Exam {
  plan: { days: { date: string; minutes: number; steps: PlanStep[] }[]; too_little_time: boolean; remaining: number };
}

export interface Gap {
  severity: "critical" | "attention" | "minor";
  topic_id: string;
  topic_title: string;
  skill_id: string | null;
  title: string;
  reasons: string[];
  wrong: string[];
  action: "practice" | "learn" | "cards" | "review" | "goals";
}

export interface ReviewView {
  items: { id: number; topic_id: string; topic_title: string; box: number; wrong: string | null; task: Task }[];
  open: number;
  cleared: number;
}

export interface WeekView {
  days: { date: string; active: boolean; usual: boolean; today: boolean }[];
  trophies: { cups: number; corrected: number };
}

export interface ExamIn {
  subject: Subject;
  title: string;
  exam_date: string;
  kind?: "written" | "oral";
  target_grade?: number | null;
  notes?: string | null;
  result_grade?: number | null;
  scope: { topic_id: string; skill_id?: string | null }[];
}

/* ------------------------------------------------------------- mock tests */

export type MockTask = Task & { points: number; topic: string };

export interface Mock {
  id: string;
  version: number;
  subject: Subject;
  grade: number;
  title: string;
  intro: string;
  source?: string;
  for?: string[];
  minutes: number;
  topics: string[];
  sections: { title: string; tasks: MockTask[] }[];
}

export interface MockCard {
  id: string;
  version: number;
  subject: Subject;
  grade: number;
  title: string;
  intro: string;
  minutes: number;
  topics: string[];
  tasks: number;
  points: number;
  for: string[];
}

export interface MockResult {
  date: string;
  points: number;
  max: number;
  pct: number;
  minutes_used: number | null;
  missed: { id: string; prompt: string; wrong: string[]; points: number; max_points: number; topic_id: string; skill_id: string | null }[];
  /** Parents only. */
  grade_estimate?: number;
}

export interface StudioMockCard extends MockCard {
  learner_ids: number[];
  outdated_ids: number[];
  approved: boolean;
}

export interface MockAnswer {
  right: boolean;
  given?: string | null;
  got_it?: boolean | null;
}

/* ------------------------------------------------------------- oral exam */

export type Verdict = "right" | "partly" | "not_yet";

export interface OralSession {
  id: number;
  topic_id: string;
  topic_title: string | null;
  date: string;
  questions: { id: string; question: string }[];
  turns: { question_id: string; question: string; answer: string; verdict: Verdict; feedback: string; model_answer: string | null }[];
}

/* ------------------------------------------------------------- queries */

export const qk = {
  all: ["uc"] as const,
  home: (lid: number) => ["uc", "home", lid] as const,
  topic: (lid: number, tid: string) => ["uc", "topic", lid, tid] as const,
  chat: (lid: number, cid: number) => ["uc", "chat", lid, cid] as const,
  chats: (lid: number) => ["uc", "chats", lid] as const,
  overview: ["uc", "overview"] as const,
  studioTopics: ["uc", "studio-topics"] as const,
  studioTopic: (tid: string) => ["uc", "studio-topic", tid] as const,
  results: (tid: string) => ["uc", "results", tid] as const,
  family: ["uc", "family"] as const,
  accounts: ["uc", "accounts"] as const,
  ai: ["uc", "ai"] as const,
  exams: (lid: number) => ["uc", "exams", lid] as const,
  exam: (lid: number, eid: number) => ["uc", "exam", lid, eid] as const,
  mastery: (lid: number) => ["uc", "mastery", lid] as const,
  gaps: (lid: number) => ["uc", "gaps", lid] as const,
  review: (lid: number) => ["uc", "review", lid] as const,
  week: (lid: number) => ["uc", "week", lid] as const,
  mocks: (lid: number) => ["uc", "mocks", lid] as const,
  mock: (lid: number, mid: string) => ["uc", "mock", lid, mid] as const,
  studioMocks: ["uc", "studio-mocks"] as const,
  studioMock: (mid: string) => ["uc", "studio-mock", mid] as const,
};

export function useOralSessions(lid: number | null) {
  return useQuery({ queryKey: ["uc", "oral", lid ?? 0], queryFn: () => api.get<OralSession[]>(`/api/learners/${lid}/oral`), enabled: !!lid });
}

export function useLearnerMocks(lid: number | null) {
  return useQuery({ queryKey: qk.mocks(lid ?? 0), queryFn: () => api.get<(MockCard & { last: MockResult | null })[]>(`/api/learners/${lid}/mocks`), enabled: !!lid });
}

export function useLearnerMock(lid: number, mid: string, enabled = true) {
  return useQuery({ queryKey: qk.mock(lid, mid), queryFn: () => api.get<Mock>(`/api/learners/${lid}/mocks/${mid}`), enabled: enabled && lid > 0 && !!mid });
}

export function useStudioMocks() {
  return useQuery({ queryKey: qk.studioMocks, queryFn: () => api.get<{ mocks: StudioMockCard[] }>("/api/studio/mocks") });
}

export function useStudioMock(mid: string | null) {
  return useQuery({
    queryKey: qk.studioMock(mid ?? ""),
    queryFn: () =>
      api.get<StudioMockCard & { mock: Mock; results: (MockResult & { learner: LearnerBrief })[] }>(`/api/studio/mocks/${mid}`),
    enabled: !!mid,
  });
}

const today = () => `today=${todayISO()}`;

export function useExams(lid: number | null) {
  return useQuery({ queryKey: [...qk.exams(lid ?? 0), todayISO()], queryFn: () => api.get<Exam[]>(`/api/learners/${lid}/exams?${today()}`), enabled: !!lid });
}

export function useExam(lid: number, eid: number) {
  return useQuery({
    queryKey: [...qk.exam(lid, eid), todayISO()],
    queryFn: () => api.get<ExamDetail>(`/api/learners/${lid}/exams/${eid}?${today()}`),
    enabled: lid > 0 && eid > 0,
  });
}

export function useMastery(lid: number | null) {
  return useQuery({
    queryKey: [...qk.mastery(lid ?? 0), todayISO()],
    queryFn: () => api.get<{ topics: { topic_id: string; title: string; subject: Subject; readiness: number | null; skills: SkillMastery[] }[] }>(
      `/api/learners/${lid}/mastery?${today()}`,
    ),
    enabled: !!lid,
  });
}

export function useGaps(lid: number | null) {
  return useQuery({ queryKey: [...qk.gaps(lid ?? 0), todayISO()], queryFn: () => api.get<{ gaps: Gap[] }>(`/api/learners/${lid}/gaps?${today()}`), enabled: !!lid });
}

export function useReview(lid: number | null) {
  return useQuery({ queryKey: [...qk.review(lid ?? 0), todayISO()], queryFn: () => api.get<ReviewView>(`/api/learners/${lid}/review?${today()}`), enabled: !!lid });
}

export function useWeek(lid: number | null) {
  return useQuery({ queryKey: [...qk.week(lid ?? 0), todayISO()], queryFn: () => api.get<WeekView>(`/api/learners/${lid}/week?${today()}`), enabled: !!lid });
}

export function useLearnerHome(lid: number | null | undefined) {
  return useQuery({
    queryKey: [...qk.home(lid ?? 0), todayISO()],
    queryFn: () => api.get<LearnerHome>(`/api/learners/${lid}/home?today=${todayISO()}`),
    enabled: !!lid,
    retry: false,
    staleTime: 0,
  });
}

export function useLearnerTopic(lid: number, tid: string, enabled = true) {
  return useQuery({
    queryKey: qk.topic(lid, tid),
    queryFn: () => api.get<Topic>(`/api/learners/${lid}/topics/${tid}`),
    enabled: enabled && lid > 0 && !!tid,
    staleTime: 0,
  });
}

export function useChat(lid: number, cid: number | null) {
  return useQuery({
    queryKey: qk.chat(lid, cid ?? 0),
    queryFn: () => api.get<ChatView>(`/api/learners/${lid}/chats/${cid}`),
    enabled: lid > 0 && !!cid,
  });
}

export function useChats(lid: number | null) {
  return useQuery({ queryKey: qk.chats(lid ?? 0), queryFn: () => api.get<ChatCard[]>(`/api/learners/${lid}/chats`), enabled: !!lid });
}

export function useOverview() {
  return useQuery({ queryKey: qk.overview, queryFn: () => api.get<Overview>(`/api/studio/overview?today=${todayISO()}`) });
}

export function useStudioTopics() {
  return useQuery({ queryKey: qk.studioTopics, queryFn: () => api.get<{ topics: StudioTopicCard[] }>("/api/studio/topics") });
}

export function useStudioTopic(tid: string | null) {
  return useQuery({
    queryKey: qk.studioTopic(tid ?? ""),
    queryFn: () => api.get<StudioTopicCard & { topic: Topic }>(`/api/studio/topics/${tid}`),
    enabled: !!tid,
  });
}

export function useTopicResults(tid: string | null) {
  return useQuery({ queryKey: qk.results(tid ?? ""), queryFn: () => api.get<TopicResults>(`/api/studio/topics/${tid}/results`), enabled: !!tid });
}

export function useFamily(enabled = true) {
  return useQuery({ queryKey: qk.family, queryFn: () => api.get<FamilyView>("/api/family"), enabled });
}

export function useAccounts() {
  return useQuery({ queryKey: qk.accounts, queryFn: () => api.get<Account[]>("/api/family/accounts") });
}

export function useAiSettings() {
  return useQuery({ queryKey: qk.ai, queryFn: () => api.get<AiSettings>(`/api/family/ai?today=${todayISO()}`) });
}

export const ucApi = {
  newChat: (lid: number, body: { subject?: Subject; topic_id?: string; task_id?: string; text: string; images: string[] }) =>
    api.post<ChatView>(`/api/learners/${lid}/chats`, { ...body, today: todayISO() }),
  send: (lid: number, cid: number, body: { text: string; images: string[] }) =>
    api.post<ChatView>(`/api/learners/${lid}/chats/${cid}/messages`, { ...body, today: todayISO() }),
  deleteChat: (lid: number, cid: number) => api.del(`/api/learners/${lid}/chats/${cid}`),
  run: (lid: number, tid: string, results: Record<string, TaskResult>, finished: boolean, challenge = false) =>
    api.post<{ id: number }>(`/api/learners/${lid}/topics/${tid}/runs`, { results, finished, challenge, today: todayISO() }),
  saveProgress: (lid: number, tid: string, known: string[], goals: string[]) =>
    api.put<StudyState>(`/api/learners/${lid}/topics/${tid}/progress`, { known, goals }),
  approve: (tid: string, version: number, learnerIds: number[]) => api.put(`/api/studio/topics/${tid}/access`, { version, learner_ids: learnerIds }),
  unapprove: (tid: string) => api.del(`/api/studio/topics/${tid}/access`),
  addLearner: (body: Partial<Learner>) => api.post<Learner>("/api/family/learners", body),
  patchLearner: (lid: number, body: Partial<Learner>) => api.patch<Learner>(`/api/family/learners/${lid}`, body),
  patchFamily: (body: { name?: string; language?: "sl" | "en"; timezone?: string }) => api.patch("/api/family", body),
  addAccount: (body: { username: string; password: string; role: "admin" | "learner"; learner_id?: number | null }) =>
    api.post<Account>("/api/family/accounts", body),
  setAccountPassword: (uid: number, password: string) => api.patch<Account>(`/api/family/accounts/${uid}`, { password }),
  deleteAccount: (uid: number) => api.del(`/api/family/accounts/${uid}`),
  setAi: (body: { routes?: { job: string; model: string; effort?: string | null }[]; budget_usd?: number | null }) =>
    api.put<AiSettings>("/api/family/ai", body),
  changePassword: (current_password: string, new_password: string) => api.post("/api/auth/change-password", { current_password, new_password }),
  addExam: (lid: number, body: ExamIn) => api.post<Exam>(`/api/learners/${lid}/exams`, body),
  updateExam: (lid: number, eid: number, body: ExamIn) => api.put<Exam>(`/api/learners/${lid}/exams/${eid}`, body),
  deleteExam: (lid: number, eid: number) => api.del(`/api/learners/${lid}/exams/${eid}`),
  startOral: (lid: number, topicId: string) => api.post<OralSession>(`/api/learners/${lid}/oral`, { topic_id: topicId, today: todayISO() }),
  answerOral: (lid: number, sid: number, questionId: string, answer: string) =>
    api.post<{ verdict: Verdict; feedback: string; model_answer: string; left_today: number }>(`/api/learners/${lid}/oral/${sid}/answers`, {
      question_id: questionId,
      answer,
      today: todayISO(),
    }),
  submitMock: (lid: number, mid: string, answers: Record<string, MockAnswer>, minutesUsed: number) =>
    api.post<MockResult>(`/api/learners/${lid}/mocks/${mid}/runs`, { answers, minutes_used: minutesUsed, today: todayISO() }),
  approveMock: (mid: string, version: number, learnerIds: number[]) => api.put(`/api/studio/mocks/${mid}/access`, { version, learner_ids: learnerIds }),
  unapproveMock: (mid: string) => api.del(`/api/studio/mocks/${mid}/access`),
  answerReview: (lid: number, results: Record<string, TaskResult>) =>
    api.post<{ answered: number; cleared: number }>(`/api/learners/${lid}/review/answers`, { results, today: todayISO() }),
};
