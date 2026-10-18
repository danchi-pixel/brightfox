# Working on BrightFox from another PC (e.g. Daniela's, with Codex)

BrightFox's code lives in this folder. When two people change it from two PCs, they need a shared, versioned
copy of the code, or one person's deploy silently overwrites the other's work. That shared copy is a
**private GitHub repository**.

## Once: put the code on GitHub (on Danijel's PC)

1. Install Git: `winget install Git.Git`, then open a new terminal.
2. In this folder:
   ```
   git init -b main
   git add .
   git commit -m "BrightFox as deployed on 18 Oct 2026"
   ```
   `.gitignore` keeps `data/` (database, photos, backups), `.venv` and `node_modules` out. Check
   `git status` before the first commit: no `data/`, no zip bundles, no passwords.
3. On github.com, create a **private** repository (e.g. `brightfox`) with no README, then:
   ```
   git remote add origin https://github.com/<account>/brightfox.git
   git push -u origin main
   ```
4. Invite Daniela as a collaborator (repository → Settings → Collaborators).

## Once: set up Daniela's PC

1. Install Git (`winget install Git.Git`), Node.js LTS (https://nodejs.org) and Python 3.12
   (`winget install Python.Python.3.12`, or python.org; it must land in `%LOCALAPPDATA%\Programs\Python\Python312`).
2. Clone the repository: `git clone https://github.com/<account>/brightfox.git` (into e.g. `Desktop\BrightFox`).
3. Run `setup.bat` once. Then `start.bat` opens a local copy at http://localhost:7686, with an empty local
   database that has nothing to do with the real site.
4. Make a local test family to sign in with. In a terminal in the `backend` folder:
   ```
   .venv\Scripts\python.exe -m app.manage create-family test --name "Test family"
   .venv\Scripts\python.exe -m app.manage add-learner test Tina --grade 5
   .venv\Scripts\python.exe -m app.manage set-password testparent --family test
   .venv\Scripts\python.exe -m app.manage set-password tina --family test --learner Tina
   ```
   Each password is typed in a hidden prompt. Use made-up names like these, never the kids' real logins.
5. Install Codex and open the BrightFox folder in it. Codex reads `AGENTS.md` at the top of the folder by
   itself: rules, layout, commands, deploy steps and pitfalls.

## Every time you work on it

1. `git pull` first, so you have the other person's changes.
2. Ask Codex (or Claude) for the change. Before calling it done, the tests must pass (`AGENTS.md`, section 4).
3. `git add`, `git commit -m "<what changed>"`, then `git push`.
4. Deploy **only from an up-to-date copy** (`git pull` just before). `deploy\deploy.ps1` uploads *your
   folder* and replaces what is on the server.

## New topics from photos

- Keep the photos **outside** the code folder (e.g. `Documents\BrightFox photos\`). Textbook pages and the
  kids' work never go on GitHub.
- Ask the AI to make a topic from them for Erik or Alan. It writes the JSON under
  `backend/app/content/data/families/danijel/` and runs the content checker.
- Commit, push and deploy, then approve the topic in the app (Topics page).

## Deploying from Daniela's PC (optional, later)

Deploying needs an SSH key that the server accepts. Danijel deploys from his PC already. Until Daniela
needs to deploy herself, she pushes to GitHub and Danijel pulls and deploys.

If she should deploy herself:
1. On her PC: `ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\brightfox_daniela"` (pick a passphrase).
2. She sends Danijel the **public** file `brightfox_daniela.pub`. Never the other one.
3. It is added to `footballadmin`'s `~/.ssh/authorized_keys` on the server. Note: that account also runs
   PitchDriven and MerchFocus, so the key reaches them too. Remove the line to revoke it.
4. She deploys with `deploy\deploy.ps1 -Key "$env:USERPROFILE\.ssh\brightfox_daniela"`.

## What stays with Danijel

- The Anthropic API key (`deploy\set-anthropic-key.ps1`) and the server itself.
- The real data: database, photos and backups live only on the server, and `deploy\pull-backup.ps1` copies
  the backups to the PC.
