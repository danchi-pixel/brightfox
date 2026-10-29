# Setting up a new PC with Codex

Open Codex on the new PC (in any folder, e.g. the Desktop), copy everything in the box below, paste it as
the first message and send it. Codex asks before it runs commands: approve them. Click **Yes** on Windows
prompts, sign in to GitHub in the browser when asked, and type the passwords yourself.

```
Hi Codex. Please set up the BrightFox project on this Windows PC so I can work on it with you. I'm not a
programmer: explain each step in one simple sentence, ask before installing anything, and answer in the
language I write in.

1. Check whether Git, Node.js and Python 3.12 are installed. Never run bare `python`, `py` or
   `where python`: on Windows they can be the Microsoft Store alias, which hangs. Look for Python at
   %LOCALAPPDATA%\Programs\Python\Python312\python.exe instead. Install whatever is missing with winget:
   Git.Git, OpenJS.NodeJS.LTS, Python.Python.3.12. I'll click Yes on the Windows prompts. Don't change any
   Windows security setting (for example Smart App Control).
2. Ask me for my name and my GitHub account's email, then set them with
   `git config --global user.name` and `git config --global user.email`.
3. Clone https://github.com/danchi-pixel/brightfox.git into my Desktop, in a folder called BrightFox.
   A "Connect to GitHub" window will open: tell me to choose "Sign in with your browser" and to sign in
   with my own GitHub account.
4. Read BrightFox\AGENTS.md completely. It holds the project's rules; follow them from now on.
5. Run `setup.bat --no-pause` in that folder and check that it ends with "Setup complete".
6. Use start.bat to prepare the local danijel household with Alan and Erik. Preserve any existing
   profiles, settings, progress and parent account. Do not create demo learners or duplicate content.
   If this is a fresh database, give me the app.manage set-password commands for a local parent and
   the two children's local accounts; I type passwords myself in the hidden prompts.
7. Start the app with start.bat, check that http://localhost:7686 opens, and tell me how to sign in.
8. Finally, explain in five short points how we work from now on: `git pull` first; you make the change
   and run the tests; I check it on localhost:7686; you commit and push; then I tell Danijel, who deploys it
   to brightfox.si. Never deploy from this PC.
```

The same steps, written out for people, are in [new-pc-setup.md](new-pc-setup.md).
