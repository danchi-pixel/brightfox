import type { Exam, MockCard, Subject } from "./api";

export const englishPath = (lid: number) => `/l/${lid}/english`;
export const subjectHomePath = (lid: number, subject?: Subject) => subject === "english" ? englishPath(lid) : `/l/${lid}`;
// Use canonical subject metadata and references, never translated titles or a fixed ID list.
export function englishMock(mock: Pick<MockCard, "subject" | "topics">, topicIds: ReadonlySet<string>) {
  return mock.subject === "english" || mock.topics.some(id => topicIds.has(id));
}
export function englishExam(exam: Pick<Exam, "subject" | "scope">, topicIds: ReadonlySet<string>) {
  return exam.subject === "english" || exam.scope.some(s => topicIds.has(s.topic_id));
}
