# Angleščina

Open the learner's classroom and choose **Angleščina** (`/l/:lid/english`).
It reuses the science collection's header, navigation, hero and responsive styles via
`StudyHub.tsx`. Science still uses those same shared components.

The collection reads existing authorized learner APIs. Topics use `subject: english`;
mocks and scheduled exams join by subject or a reference to an accessible English topic.
There is no separate registry or copied question bank. The classroom omits those individual
English cards and links to the collection. Other subjects keep their entries.

Existing lessons, videos, notes, flashcards, goals, practice, challenges, oral exercises, mock results,
exam plans and readiness use the original components, IDs, endpoints and scoring. Closing
an English lesson or test returns to the collection. Parent studio previews keep their
original return destination. New English content is included automatically after normal
visibility/approval rules permit it.

## Existing authored material checked

- `2026-10-17-erik-english-people`: People are people, 25 tasks and 11 challenge tasks.
- `2026-10-17-erik-english-days`: Days, dates & hello, 20 tasks and 11 challenge tasks.
- `2026-10-18-erik-english-people-mock`: the existing 30-minute, 28-point mock.
- Scheduled exams are read dynamically from the learner API, including their plans.

All ten canonical educational JSON files were hash-compared before and after the collection change
and are byte-for-byte identical. No content version, task ID, scoring function, persistence
endpoint, or database schema changed. No household database was opened for testing.

The later GitHub integration preserves upstream commit `d41d050` and its v6 English video
lessons unchanged. Their video buttons appear inside the collection, and video exit returns here.

## Verification

76 backend tests and 55 frontend tests pass, including seven collection regressions; TypeScript
and the production build pass. Scratch-account browser checks cover the classroom grouping,
both lessons and the mock, original lesson/mock screens, return navigation, and desktop
(1280px) / mobile (390px) layouts. The automated checks cover existing progress display,
future standalone English tests, related-topic classification, and list-fetch errors.

This is a local code change; no production deployment was performed.
