# Working on BrightFox from another PC (e.g. Daniela's, with Codex)

BrightFox's code lives in this folder. When two people change it from two PCs, they need a shared, versioned
copy of the code, or one person's deploy silently overwrites the other's work. That shared copy is a
**private GitHub repository**.

The repository is **https://github.com/danchi-pixel/brightfox** (private, owned by Danijel; Daniela is a
collaborator). Done on 18 Oct 2026, so the next section is only a record of how it was set up.

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

Shortcut: install Codex first, then paste the prompt from [codex-setup-prompt.md](codex-setup-prompt.md)
and Codex does the steps below with her.

1. Install Git (`winget install Git.Git`), Node.js LTS (https://nodejs.org) and Python 3.12
   (`winget install Python.Python.3.12`, or python.org; it must land in `%LOCALAPPDATA%\Programs\Python\Python312`).
2. Clone the repository in a new terminal, from the Desktop: `git clone https://github.com/danchi-pixel/brightfox.git BrightFox`.
   The first time, a "Connect to GitHub" window opens. Choose "Sign in with your browser" and sign in with
   **her own** GitHub account.
3. Run `setup.bat` once. Then `start.bat` opens the current source at http://localhost:7686. It uses
   this checkout's `data/ucilnica.db`, separate from production, and prepares the `danijel` household
   with exactly Alan and Erik. Existing profiles and progress are preserved; demo data is backed up
   and kept in an inactive family, never copied into the children's histories.
4. On a fresh PC, the person sets local passwords in a terminal in the `backend` folder:
   ```
   .venv\Scripts\python.exe -m app.manage set-password localparent --family danijel
   .venv\Scripts\python.exe -m app.manage set-password localalan --family danijel --learner Alan
   .venv\Scripts\python.exe -m app.manage set-password localerik --family danijel --learner Erik
   ```
   Each password is typed by the person in a hidden prompt, never by an agent. On an already configured
   PC the existing parent sign-in continues to work; do not reset it or create duplicate profiles.
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
- Set `for` to Alan, Erik, or both. Refresh localhost: the content registry picks up the file and its
  newest version automatically. Root `content/` is an old export bundle, not a second registry.
- For production: commit, push and deploy, then approve the topic in the app (Topics page).

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
