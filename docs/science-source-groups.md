# Naravoslovje: Zvezek and Učbenik

Erik's science collection opens on **Zvezek**, the school notebook and worksheets.
The original source register identifies p01–p14 as these materials and p15–p38 as
textbook pages. Source photos and the register were reviewed before assigning metadata.

- **Zvezek:** 25 existing questions, available immediately, across four lesson groups.
- **Učbenik:** 73 existing questions across ten lesson groups. Read-only until a parent
  activates the corresponding textbook lesson for this learner.
- **Za pregled:** `toplotni-poskus` cites both p01 and p16. Its original question, answer
  and both references remain intact. It stays out of practice even if the textbook heat
  lesson is activated. Resolve its provenance explicitly in a future content revision.

Some lessons span both sources. Each question appears in exactly one source group.
Shared lesson notes remain available in a clearly labelled disclosure; they are not
automatically used as notebook exercises. No questions were generated or duplicated.

## Parent controls

Sign in as a parent, open Erik's classroom → **Erikovo naravoslovje** → **Učbenik**,
open a topic and select **Aktiviraj temo**. **Prestavi za kasneje** pauses it again.
Activation is per learner, parent-controlled and saved independently of exercise progress.
Other families and sibling learner accounts cannot change it.

Inactive questions are excluded from oral practice, mock oral sessions, quizzes, picture
exercises, flashcards, weak-answer selection, resumable queues and current progress totals.
The server also rejects attempts to save an inactive question. The older direct practice
URLs, readiness, plans, study cards and mistake review use the same source policy through
explicit links to the existing question IDs. The classroom now has one science entry.

Previous answers, attempts, spacing dates and sessions stay stored. Resuming filters the
queue without resetting answer history. Re-activation makes the saved progress count again.
Completed historical achievements and parent history remain available.

## Data and rollout

The science JSON is version **5**. Only the version, source-group metadata and legacy
cross-references changed; all original educational text, IDs, answers and image/crop
references were compared with the pre-change document and remain identical.

Migration **0005** adds `lab_activations`; it does not alter or recreate existing tables.
Restart the backend after updating the code. Production requires the normal parent
approval of science v5. No deployment or household database reset is part of this change.
Private source photographs remain outside Git.

Missing or mixed source classifications fail closed into **Za pregled**. Parent activation
only enables questions unambiguously attributed to the textbook, not unresolved questions.

## Verification — 30 October 2026

80 backend tests and 60 frontend tests pass; content validation, TypeScript and the
production build pass. Scratch-account browser checks cover notebook defaults, disabled
textbook practice, parent activation/deactivation, and desktop/mobile layouts. Tests cover
all five exercise modes, stale sessions, saved textbook recall, legacy readiness and
mistake-review filtering, parent-only writes and cross-family isolation.
