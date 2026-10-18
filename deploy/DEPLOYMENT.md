# BrightFox — production deployment

**https://brightfox.si** (www.brightfox.si redirects there) runs BrightFox in Docker on the netcup
VPS `152.53.191.32` (Ubuntu 24.04), next to PitchDriven (`/opt/football7676`) and MerchFocus
(`/opt/merchfocus`). PitchDriven's compose owns the only Caddy, which serves all three sites.

## Architecture

```
Internet ──► :80/:443  PitchDriven's caddy  (HTTPS via Let's Encrypt, security headers, 25 MB body limit)
                         │  Docker network "edge" (shared, not reachable from outside)
                         ▼
                   ucilnica :8000  (FastAPI API + built web app, no published port)
                         │
                   /opt/ucilnica/data  (ucilnica.db, files/ = homework photos, backups/)
```

* The site block lives in PitchDriven's `deploy/Caddyfile` (Football App 7676 folder), because one Caddy
  serves every domain. Its text is in [`caddy-site.txt`](caddy-site.txt). Caddy reaches BrightFox by the
  network alias `ucilnica`. The compose service is not called `app`: on PitchDriven's network that name
  means the PitchDriven container.
* The container runs as `footballadmin` (uid/gid from `.env`), all Linux capabilities dropped,
  `no-new-privileges`, 512 MB memory limit, logs rotated (5 × 10 MB).
* **Sign-in is required** for every `/api` route except health, sign-in, status and sign-out, and for
  `/docs` and `/openapi.json`. Session cookies are Secure, HttpOnly, SameSite=Strict.
* Every family sees only its own learners: another family's learner answers 404, the same as an id that
  doesn't exist. `smoke-test.ps1` checks this on the live site with the QA family.
* The microphone and camera are blocked for the whole site (`Permissions-Policy`); the oral exam is typed.
* Search engines are told not to index the site (`X-Robots-Tag`, `robots.txt`).

## Files on the server (`/opt/ucilnica`, owned by footballadmin)

| Path | What |
|---|---|
| `compose.yaml` | the stack (copied from `src/deploy/` on each update) |
| `.env` | `APP_UID` / `APP_GID` (mode 600, written by `update.sh`) |
| `secrets.env` | `ANTHROPIC_API_KEY` (mode 600, written by `scripts/set-anthropic-key.sh`); empty at first |
| `src/` | the source the current image was built from (`src.old`, `src.failed` after an update or rollback) |
| `data/` (mode 700) | **all persistent data**: `ucilnica.db`, `files/<family>/<learner>/`, `backups/` |
| `scripts/` | `update.sh`, `backup.sh`, `set-anthropic-key.sh` |
| `backup.log` | output of the scheduled backups |

## First install (in this order)

Unlock the SSH key first: `Start-Service ssh-agent; ssh-add "$env:USERPROFILE\.ssh\football7676_final"`
(you type the passphrase). Run the PowerShell lines from the `Ucilnica` folder.

1. **Check the server has room** (RAM and disk aren't documented anywhere yet):
   `ssh footballadmin@152.53.191.32 "free -h; df -h /; docker stats --no-stream"`.
   BrightFox needs up to 512 MB of RAM and about 1 GB of disk for the images and build cache.
2. **DNS** (at the brightfox.si registrar): two **A records**, host `@` and host `www`, both
   `152.53.191.32`. Check them with `nslookup brightfox.si` and `nslookup www.brightfox.si` before step 7.
3. **Make the folder** (once; you type the sudo password):
   `ssh -t footballadmin@152.53.191.32 sudo install -d -o footballadmin -g footballadmin -m 755 /opt/ucilnica`
4. **Deploy**: `powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1`. It creates `.env`, an empty
   `secrets.env` and the `edge` network if needed, builds the image and waits until the app is healthy.
   The site isn't reachable from the internet yet (no Caddy block).
5. **QA family** (with the parent's OK, it creates accounts on the live site):
   `powershell -ExecutionPolicy Bypass -File deploy\create-qa-family.ps1`. See "The QA family" below.
6. **Foxy's key**: `powershell -ExecutionPolicy Bypass -File deploy\set-anthropic-key.ps1`, then paste the key
   in the hidden prompt. Without it BrightFox works and Foxy shows "not set up"; nothing is sent anywhere.
   Suggestion: a separate Anthropic Console workspace with a monthly spend limit, just for BrightFox.
7. **Caddy block**: once DNS answers with `152.53.191.32`, paste the block from `caddy-site.txt` at the end
   of `Football App 7676\deploy\Caddyfile` (keep the other blocks) and run **PitchDriven's**
   `deploy\deploy.ps1`. PitchDriven restarts briefly; run PitchDriven's `deploy\smoke-test.ps1` after it.
8. **Check**: `powershell -ExecutionPolicy Bypass -File deploy\smoke-test.ps1` (must end with 0 failed).
9. **Backups**: install the crontab lines and do one restore test (both below).

The real family and its logins (the parent's and Erik's and Alan's) are part of the cut-over in
`docs/roadmap.md`: the parent chooses those passwords; they are never typed by Claude.

## Updates

```powershell
powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1
powershell -ExecutionPolicy Bypass -File deploy\smoke-test.ps1
```

`deploy.ps1` packs an explicit list of folders (`backend` without `.venv`, `__pycache__`, `data` and
`evals/results`; `frontend` without `node_modules` and `dist`; `deploy`; `docs`), so local data and keys
are never shipped. On the server, `update.sh` from the new upload then:

1. makes a backup (`*-preupdate.zip`, keeps 5) if BrightFox is running;
2. unpacks the new source next to the old one and tags the running image `ucilnica-app:previous`;
3. builds the new image (`docker compose build --pull`); if the build fails nothing changes;
4. restarts and waits up to 2 minutes for the health check (`/api/health`); if it isn't healthy, it rolls
   back to the previous image and source (the failed source stays in `src.failed`).

Database migrations run when the app starts. After the first production deploy they only add tables or
columns (see `CLAUDE.md`), so a rollback still works with the migrated database.

`bash /opt/ucilnica/scripts/update.sh start` (on the server) only restarts, without building.

## Everyday tasks

On the server (`ssh -t footballadmin@152.53.191.32`), inside `/opt/ucilnica`:

| Task | Command |
|---|---|
| Status | `docker compose ps` |
| Logs | `docker compose logs -f --tail 100 ucilnica` |
| Restart | `docker compose restart ucilnica` |
| Families | `docker compose exec ucilnica python -m app.manage list-families` |
| Logins | `docker compose exec ucilnica python -m app.manage list-users` |
| New login / new password (prompts, hidden) | `docker compose exec ucilnica python -m app.manage set-password <user> --family <slug> [--learner <name>]` |
| Backup now | `scripts/backup.sh daily` |

Parents can also manage their family's accounts in the app.

## Backups

`scripts/backup.sh` runs `python -m app.manage backup --label <label> --keep <n>` inside the container.
Each backup is one zip in `data/backups/` (mode 600): `ucilnica.db` (a consistent copy made with SQLite's
online backup API, safe while the app runs), every homework photo under `files/`, and `manifest.json`
(row count per table, number of photos).

| When | Label | Kept |
|---|---|---|
| Every night 04:15 | `daily` | 14 |
| Sundays 04:30 | `weekly` | 8 |
| Before every update | `preupdate` | 5 |

**Crontab** (not installed by any script). On the server run `crontab -e` and add these two lines, keeping
PitchDriven's and MerchFocus's lines (03:15–04:00):

```
15 4 * * * /opt/ucilnica/scripts/backup.sh daily >> /opt/ucilnica/backup.log 2>&1
30 4 * * 0 /opt/ucilnica/scripts/backup.sh weekly >> /opt/ucilnica/backup.log 2>&1
```

Cron uses the server's time zone (`timedatectl` shows it). Check the next morning with
`tail /opt/ucilnica/backup.log` and `ls -l /opt/ucilnica/data/backups`.

**Off-site copy** (backups on the same server don't protect against losing the server):
`powershell -ExecutionPolicy Bypass -File deploy\pull-backup.ps1` downloads the newest weekly and daily
zips to `Documents\Ucilnica-backups`. They hold the kids' chats and photos: keep that folder private.

### Restore test (do it once after the first backups, and after big changes)

On the server, inside `/opt/ucilnica`. This only unpacks a copy into a scratch folder; `data/` is not
touched.

```bash
B=$(ls -1t data/backups/ucilnica-backup-*.zip | head -n 1); echo "$B"
rm -rf restore-test && mkdir -m 700 restore-test
python3 -m zipfile -e "$B" restore-test/
python3 - <<'PY'
import json, sqlite3
m = json.load(open("restore-test/manifest.json"))
con = sqlite3.connect("restore-test/ucilnica.db")
print("integrity:", con.execute("PRAGMA integrity_check").fetchone()[0])
for table, n in m["counts"].items():
    got = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    print("OK  " if got == n else "DIFF", table, got, n)
PY
echo "photos: $(find restore-test/files -type f 2>/dev/null | wc -l)  (manifest: $(grep -o '"files": [0-9]*' restore-test/manifest.json))"
docker run --rm --network none --user "$(id -u):$(id -g)" -v "$PWD/restore-test:/data" ucilnica-app:latest \
  python -m app.manage list-users
rm -rf restore-test
```

It passes when integrity is `ok`, every table says `OK`, the photo count matches and the accounts are listed.

### Real restore

```bash
cd /opt/ucilnica
B=data/backups/ucilnica-backup-YYYYmmdd-HHMMSS-daily.zip          # the backup to restore
docker compose exec -T ucilnica python -m app.manage backup --label prerestore </dev/null
docker compose stop ucilnica
OLD="data/replaced-$(date +%Y%m%d-%H%M%S)"; mkdir -m 700 "$OLD"
mv data/ucilnica.db* "$OLD"/; [ -d data/files ] && mv data/files "$OLD"/
python3 -m zipfile -e "$B" data/ && rm data/manifest.json
docker compose start ucilnica
```

Then run `deploy\smoke-test.ps1` and check the app. Delete the `replaced-…` folder once all is well.

## The QA family

`deploy\create-qa-family.ps1` creates the family `qa` (name "QA") with the learners "QA Learner" and
"QA Sibling" and two accounts: `qa-parent` (parent of the QA family only) and `qa-learner` ("QA Learner").
The random passwords are written only to `Documents\Ucilnica-qa-login.txt`. Run it again to renew both
passwords. It uses `python -m app.manage create-family / add-learner / set-password --stdin` over SSH.

`deploy\smoke-test.ps1` signs in only with these accounts, never with the children's or the parent's own
logins, and never calls Foxy. It checks the HTTPS redirect, the security headers (including
`Permissions-Policy` with `microphone=()`), robots, that anonymous requests get 401, and then the family
isolation on the live site: the QA parent sees only the QA learners and gets 404 for every other learner id
from 1 to 50; the QA learner gets 404 for the family settings, the sibling's home and every other id; after
signing out, the old cookies are refused. Without the login file the QA checks are reported as SKIP.

To switch the QA family off: `docker compose exec -T ucilnica python -m app.manage suspend-family qa`
(`activate-family qa` brings it back).

## Another address later

1. Point its A records at `152.53.191.32`.
2. Add it to `x-hosts` at the top of `deploy/compose.yaml` (comma-separated) and run `deploy\deploy.ps1`.
3. Add a site block (or a redirect block) for it in PitchDriven's `deploy/Caddyfile` and in
   `caddy-site.txt`, then run PitchDriven's `deploy\deploy.ps1`.
4. Run the smoke test with the new address: `deploy\smoke-test.ps1 -Base https://<address>`.

## Local development on this PC

* `setup.bat` makes `backend\.venv`; use `backend\.venv\Scripts\python.exe` by full path (the bare
  `python`/`py` is the Microsoft Store alias here and hangs).
* **Smart App Control** blocks SQLAlchemy's freshly installed compiled modules (`*_cy.*.pyd`) on this PC,
  so `setup.bat` deletes them and SQLAlchemy runs its pure-Python version. Never switch Smart App Control
  off. This is a Windows-only quirk: the Linux image on the server keeps the compiled modules.
* Tests and UI checks use scratch data only (`UCILNICA_DATA_DIR` in a temp folder), never the live site's
  logins and never the real `data/`.
