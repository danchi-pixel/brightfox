# BrightFox: rules for working on this project

BrightFox is a family study app: topics (📖 Uči se → ✏️ Vaja → 🏆 Liga prvakov), tests with readiness,
Moje napake, mock and oral exams, and Foxy, the homework tutor on the Claude API. It started as the Study
section of PitchDriven (`C:\Users\danij\Desktop\Football App 7676`) and was moved here in October 2026.
The plan lives in `docs/roadmap.md`. Live at https://brightfox.si. The code name is still `ucilnica` (folder,
`/opt/ucilnica`, `UCILNICA_*` env vars, the Docker service): users never see it, so it stays.
Foxy is masculine in Slovene ("Vprašaj Foxyja", "s Foxyjem", "Foxy je pripravljen"); the kid is still
addressed gender-neutrally.

## People and roles
- **Admins** are parents. They see everything in their own family, approve content and read the chats.
- **Learners** are the kids (today: Erik and Alan, at a Slovenian school). A learner sees only their own space.
- Built for **many families** from day one (so it can be sold later). Every learner-owned row carries
  `family_id`, and every `/api` route has exactly one access dependency (`tests/test_tenancy.py` checks this).

## Hard rules
- **Never call bare `python`, `py` or `where python`** on this PC (the Store alias hangs). Use
  `backend\.venv\Scripts\python.exe` by full path. To make a venv:
  `C:\Users\danij\AppData\Local\Programs\Python\Python312\python.exe -m venv backend\.venv`.
- **Kid-facing Slovene is gender-neutral** toward the child: imperatives and present tense ("Izračunaj",
  "Zapiši"), never l-participles or adjectives about "you" ("Si naredil?", "pripravljen").
- **No streaks** and nothing that punishes a missed day. Readiness and mastery are fine; trophies are
  collected and never lost.
- **Tests and UI checks use scratch data only** (`UCILNICA_DATA_DIR` in a temp folder, scratch families).
  Never the kids' real logins, never the real `data/`.
- **The AI is never called from tests.** Use the fake provider. An eval that calls the API costs money:
  ask the user first, with the expected cost, and pass `--max-usd`.
- **Never type passwords or API keys** for the user. Keys go in with `deploy\set-anthropic-key.ps1`
  (hidden prompt on the server).
- **Migrations:** after the first production deploy only add tables or columns. Never let Alembic batch-
  recreate a table that others reference (SQLite + `foreign_keys=ON` cascade-deletes the children).
- **Content** (topics and mocks) is written by Claude Code from photos the parent provides, as JSON in
  `backend/app/content/data/`, checked with `backend\.venv\Scripts\python.exe -m app.content.checker`.
  Any change to a file = `version` + 1, and the parent approves it again. Format: `docs/content-format.md`.

## Commands
- Backend tests: `backend\.venv\Scripts\python.exe -m pytest -q` (from `backend`).
- Frontend: `npx tsc -b` and `npx vitest run` (from `frontend`).
- Local app: `start.bat` (web 7686, API 7687; PitchDriven uses 7676/7677).
- Deploy: `deploy\deploy.ps1`, then `deploy\smoke-test.ps1` (see `deploy/DEPLOYMENT.md`).
