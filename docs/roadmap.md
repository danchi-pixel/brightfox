# BrightFox: the standalone study app

## Context
Study grew inside PitchDriven (Foxy tutor, topics with 📖 Uči se / ✏️ Vaja / 🏆 Liga prvakov, the parent studio). It has outgrown a football app. The user wants:
- its own app and domain, with a clear **admin** (parent) overview and a separate space for each kid (Erik, Alan);
- a design that stays open to **selling to other families** later;
- the best ideas from Astra AI's reviews and screenshots;
- cheaper LLM options that still get maths right.

**Decisions made by the user (18 Oct):**
- Name **BrightFox**.
- **Readiness + mastery, no streaks.**
- **Content is still written by Claude Code** from photos.
- **Move Study out of PitchDriven** (migrate Erik and Alan's data, then link from PitchDriven).

## Defaults I chose (change any before approving)
- **Address until a domain is bought:** `brightfox.si`. You add one DNS A record.
  - Name check: Slovenian schools already say "spletna učilnica" for Arnes/Moodle, and `ucilnica.si` is likely taken. Worth checking before you buy.
- **Language:** parent screens in English first (as today), kid screens in Slovene. A Slovene parent UI comes later, for selling.
- **Mock exam:** the kid sees points and "what to repeat". The grade estimate is shown to the parent only.
- **Chats not migrated:** your own Foxy test chats.
- **Logins:** each kid has their own login; no PIN kid mode on a parent's device.
- **Microphone:** stays off. The oral exam starts **typed**: Foxy reads the questions aloud, the kid types the answers. Voice input is a later, explicit privacy decision, because browser recognition sends audio to Google or Apple.

## Architecture
- **New folder `C:\Users\danij\Desktop\Ucilnica`** (git), on the same stack as today: FastAPI + SQLAlchemy 2 + Alembic/SQLite, React 19 + Vite + TanStack Query + Tailwind v4, vitest. It has a `CLAUDE.md` with the house rules:
  - venv python by full path;
  - gender-neutral Slovene toward the child;
  - scratch data only in tests;
  - migrations only add tables or columns after the first production deploy.
- **What carries over:**
  - Copied with little change from PitchDriven:
    - `backend/app/auth.py`: scrypt, sessions, limiter, middleware.
    - `db.py` and `migrate.py`.
    - `frontend/src/components/ui/*`, `lib/api.ts`, `lib/utils.ts`, `lib/dates.ts`.
    - `features/study/answers.ts`, `image.ts` and `speech.ts`. Add Slovene voices to `speech.ts`.
    - The `ChoiceTile`, `Feedback` and `Prompt` components and the `useMindLang` and `formatDate` helpers. These come from `mindlab/ui.tsx` and `mindlab/i18n.ts`, trimmed down.
  - Adapted: `study/content.py` → `content/checker.py` (format v2, old files stay valid), plus `PracticePlayer`, `LearnPage` and `ChatPage`.
  - Rewritten with family scope: `routers/study.py` → `routers/{studio,learner,tutor,exams,review,mock,oral,family}.py`, and `ParentStudy`/`KidStudy` → new parent and learner pages.
  - Dropped: players, everything football, Mind Lab, Tactical, ffmpeg/media, and the "sign-in off = admin" mode. Sign-in is always on; local dev uses a seeded scratch family.
- **Multiple families from day one** (fresh Alembic baseline):
  - Core tables:
    - `families(slug, name, timezone, language, status, settings)`;
    - `users(family_id, role admin|learner, learner_id)`;
    - `learners(family_id, name, grade, language, interests, tutor settings, rhythm)`. This replaces players and study_profiles.
  - Every learner-owned table has a composite FK `(family_id, learner_id)`, so the database itself refuses cross-family rows.
  - Study tables:
    - `content_access`: a proper join table per learner and version, replacing the JSON `player_ids`.
    - `practice_runs` and `task_results`: one row per task, so mastery, gaps and review can be computed.
    - `topic_progress`: goals keyed by id, not list index.
    - `tutor_chats`, `tutor_messages`, and `attachments` (multi-photo).
    - `llm_calls`: one cost ledger for everything AI.
    - `llm_routes` and `imports`.
  - Later migrations add only new tables: `exams`, `exam_scope`, `review_items` (Phase 4) and `oral_sessions`, `oral_turns` (Phase 5).
- **Access rules:**
  - Admins work under `/api/family/*` and `/api/studio/*`.
  - Kids work under `/api/learners/{lid}/*`, checked by a `learner_in_scope` dependency. Another family's learner returns 404.
  - Kid writes require `is_self`, so a parent's preview is never saved.
  - Accounts and families are created from the command line only (`manage.py create-family`, `set-password --stdin`). There is no public sign-up yet.
- **Content:**
  - JSON files live in `content/data/families/<slug>/` (private to one family) or `content/data/global/` (each family approves it per kid).
  - The `ContentSource` interface means files today and a database later, which keeps in-app generation possible for selling.
  - **Format v2 additions** (optional):
    - `skills` (tasks, cards, goals and sections reference them);
    - goal ids;
    - `traps` (known wrong answers with an explanation);
    - `parent` (helper card: how school teaches it, typical mistakes, 5 car questions);
    - `oral` questions with key points;
    - `terms`.
  - **Mock tests** are their own content kind: `mocks/<id>.json` with minutes, points and sections.

## LLM layer (`backend/app/llm/`)
- **A provider-neutral interface** (`Provider.complete`) with neutral errors. The Anthropic provider is today's `tutor.ask()` code: effort is always explicit, caching on, and server fallback only where the model supports it.
- **Model routing per job** (`tutor_chat`, `oral_grading`, `open_feedback`). It resolves family setting → code default. The default stays Opus 5.5 / medium, which is today's behaviour.
- **Parent screen "Foxy in AI":** model per job, monthly AI budget, this month's spend, and cost per 100 messages from the family's own ledger.
- **Prices per MTok, input / output:**

  | Model | Input | Output | Cache read |
  |---|---|---|---|
  | Opus 5.5 | $4 | $20 | $0.20 |
  | Sonnet 5.5 | $2 | $10 | $0.10 |
  | Haiku 5.5 (prompts ≤100K) | $0.10 | $0.50 | $0.01 |

- **Eval before trusting a cheaper model:** `backend/evals/run_eval.py --job --models --cases --max-usd`.
  - It uses the production prompt builder on synthetic Slovenian school cases, never real chats.
  - Automatic checks: decimal comma, gender-neutral, doesn't give the answer on the first ask, stays in Slovene.
  - An Opus judge scores each reply.
  - A model is offered for a job only after it passes (`approved_models.json`).
  - Running it spends real money, so I ask you first and give the cost.
- Other providers (OpenAI/Gemini) can plug into the same interface later. Not now.

## Features
**Parity:** everything Study does today.
- Foxy: hints first, parents read the chats, daily limit.
- Topics with Uči se, Vaja and Liga prvakov.
- Approve per version per kid; "How the kids did" with typed wrong answers; parent preview of the kid view.

**New, from the Astra research:**
1. **Testi:**
   - The parent enters a date, what's on the test and a target grade.
   - The kid sees a countdown, **readiness ≈ 70 %**, and a **daily step-by-step plan** grounded in the topic. The plan is recomputed daily, weakest skill first, follows the kid's study days, and puts the mock on the second-to-last day.
   - Readiness formula, per skill: Vaja right first time 40 %, mock 25 %, Liga 15 %, cards 10 %, goals 10 %.
     - Results older than 28 days count half.
     - Self-reported progress only (cards and goals, no tasks) is capped at 60 %.
     - The parent sees the full breakdown (`docs/readiness.md`).
2. **Mastery per topic and skill:** **Znam / Skoraj / Še ne / Ni začeto**.
3. **Knowledge gaps:** critical / needs attention / minor, each with the reason, the typed wrong answers and a "fix it" link.
4. **Moje napake:**
   - Spaced review at 1, 3, 7 and 14 days, max 10 a day, pulled forward 3 days before a test.
   - Corrected mistakes go to a "popravljeno" collection.
5. **Poskusni test (written mock):**
   - Timed, no hints, no Foxy, points at the end.
   - Written by me from a photo of an old test, in the teacher's format.
6. **Ustno spraševanje (oral exam, typed):** Foxy asks aloud, the kid types the answer, and Foxy grades it right / partly / not yet with one sentence of feedback.
7. **Foxy grounded in the topic:**
   - "Vprašaj Foxyja" on a topic or task opens a chat with the topic's notes and terms, so Foxy uses the book's method.
   - Up to 4 photos per message.
8. **Parent helper card** per topic, printable.
9. **Trophies** (collected, never lost) and a **weekly rhythm** (this week's dots reset each Monday; nothing to "break").

**Later (Phase 6):**
- voice input;
- a "podcast" read-through of notes;
- in-app generation from uploads;
- Slovene parent UI;
- selling: sign-up, billing, privacy policy and DPA, per-family export and delete.

## Moving the data from PitchDriven
- **Before anything else:** make a safety tar of `/opt/football7676/data/study`. Chat photos are in no backup today.
- **Export:** `scripts/export_pitchdriven_study.py` (stdlib only).
  - Runs inside the PitchDriven container on an online-backup snapshot.
  - Produces a zip with a manifest and checksums.
  - Contains **no password hashes**.
- **Import:** `python -m app.importers.pitchdriven <zip> --family <slug> --learners Erik,Alan --dry-run`, then for real. The exact server commands are in [import.md](import.md).
  - Maps player_ids to `content_access`, attempts to runs and task rows, goal indexes to ids, chats and photos with checksums.
  - Records the import, so it can't run twice.
- **Content:** the 3 sets are copied byte for byte (same ids and versions), so your approvals stay valid.
- **Accounts:** you create your admin login and Erik's and Alan's logins and choose the passwords. Nothing is copied.
- **Order:**
  1. Deploy BrightFox and smoke-test it.
  2. Make PitchDriven's Study read-only ("moving to BrightFox").
  3. Export.
  4. Dry-run the import into a scratch copy on the VPS.
  5. Real import.
  6. You check it.
  7. PitchDriven's Study becomes a link card.
  8. About 4 weeks later, remove the Study code and tables from PitchDriven.

## Deploy (same VPS, MerchFocus pattern)
- **The stack:** `/opt/ucilnica`.
  - Service alias `ucilnica` on the `edge` network, no ports, `mem_limit 512m`.
  - `secrets.env` holds `ANTHROPIC_API_KEY`, set with `set-anthropic-key.ps1` (hidden prompt; I never type it).
  - `HEALTHCHECK /api/health`.
  - `update.sh` does backup → build → health → rollback.
- **Backups:** database + photos, daily at 04:15 (keep 14) and weekly on Sundays at 04:30 (keep 8). `pull-backup.ps1` copies them to the PC. One restore test.
- **Caddy:** a site block in PitchDriven's `deploy/Caddyfile` with security headers, `microphone=()` and a 25 MB body limit. Rolled out with PitchDriven's deploy, which briefly restarts PitchDriven.
- **Before deploying:** check the VPS's RAM and disk (not documented).
- **`smoke-test.ps1`:**
  - read-only, never calls the AI;
  - uses a separate `qa` family only;
  - probes that one family can't see another's learners.
- **Suggestion:** a separate Anthropic Console workspace and key with a spend limit for BrightFox.

## Phases
| Phase | What | Notes |
|---|---|---|
| 0 | Skeleton: repo, git, CLAUDE.md, venv, health endpoint, Vite shell | sequential |
| 1 | Foundation: models baseline, auth + family scoping, `manage.py` family/account commands, content registry + checker v2, `docs/api.md` | sequential trunk |
| 2 | Parity, in 5 parts once Phase 1 is in: **A** studio/learner API · **B** frontend port · **C** deploy stack + QA family + smoke test · **D** export/import tool · **E** LLM layer + tutor + ledger + eval harness | A–E can run as parallel sessions in their own worktrees; one owner for model changes |
| 3 | Cut-over with you (order above) | strictly in order, needs you for DNS, key and logins |
| 4 | Migration 0002 + `skills` added to the existing topics (re-approve) → readiness/mastery/plan/gaps, Testi screens, Moje napake, trophies + weekly rhythm | the formulas are pure functions, unit-tested |
| 5 | Migration 0003 → mock test, topic-grounded Foxy + multi-photo, helper card, typed oral exam, eval for grading jobs → cheaper models per job only if they pass | parallel after the migration |
| 3b | Remove Study from PitchDriven (~4 weeks after cut-over) | independent |

## Verification
- **Backend pytest:**
  - ported Study tests;
  - `test_tenancy`: a route audit (every `/api` route has exactly one access dependency) and a family-A/B isolation sweep;
  - table-driven tests for the readiness, plan, gaps and review formulas;
  - an import round-trip on a synthetic PitchDriven database;
  - a fake LLM provider, so tests never call the API.
- **Frontend:** vitest + `tsc -b`.
- **UI checks:** on a scratch server with scratch families and the in-app browser at phone width. Never the kids' real logins.
- **After each deploy:**
  - `smoke-test.ps1` for BrightFox;
  - PitchDriven's 77 checks, which must stay green while Study is moved out.
- **Cut-over:** imported counts match the manifest, photos open, and Erik and Alan see their approved topics.
- **Eval:** a report committed to `backend/evals/results/`, run only after you approve the cost.
