export type Mode = "oral" | "mock" | "quiz" | "images" | "cards";
export type Rating = "know" | "practice" | "again";
export type SourceGroup = "notebook" | "textbook" | "review";
export interface Source { id: string; group?: SourceGroup; file: string; label: string; width: number; height: number; rotate: number; review: string }
export interface Picture { source: string; box: [number, number, number, number]; alt: string }
export interface Lesson { id: string; title: string; icon: string; summary: string; notes: string[]; vocabulary: Record<string, string>; sources: string[] }
export interface Question {
  id: string; topic: string; kind: "oral" | "choice" | "boolean" | "fill" | "match" | "sort" | "sequence" | "label";
  prompt: string; answer: string; points: string[]; hints: string[]; sources: string[]; difficulty: number;
  options?: string[]; correct?: string[]; items?: string[]; image?: Picture; card?: boolean;
  followup?: string; followup_answer?: string;
}
export interface Bank { title: string; lessons: Lesson[]; questions: Question[]; sources: Source[]; review_notes: string[] }
export interface Session { mode: Mode; queue: string[]; index: number; ratings: Record<string, Rating> }
export interface Recall { rating: Rating; attempts: number; due: string; interval: number; updated: string }
export interface Progress { revision: number; answers: Record<string, Recall>; session: Session | null }
export interface Availability { enabled_lessons: string[]; active_questions: string[]; question_groups: Record<string, SourceGroup>; can_manage: boolean }
export const labels: Record<Rating, string> = { know: "Znam", practice: "Še vadim", again: "Ne znam še" };
export const modes: Record<Mode, string> = { oral: "Ustno spraševanje", mock: "Poskusno ustno ocenjevanje", quiz: "Hitri kviz", images: "Učenje s slikami", cards: "Kartice za ponavljanje" };
