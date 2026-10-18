# Moving Study data from PitchDriven

A one-off, done together with the parent in Phase 3 (the cut-over order is in [roadmap.md](roadmap.md)). It
moves Erik's and Alan's Study data from PitchDriven (`/opt/football7676`) to BrightFox (`/opt/ucilnica`).
Both apps run on the same VPS, so the data never leaves the server.

| Piece | Where | What it does |
|---|---|---|
| Exporter | `scripts/export_pitchdriven_study.py` | Runs inside the PitchDriven container (standard library only). It reads an online-backup snapshot of the database, so it never writes to PitchDriven. Writes a zip with `manifest.json` (schema revision, row counts, a sha256 for every table file and photo), the Study tables, the players they refer to, every account's username, role, player and language (**no password hashes, no sessions**), and the chat photos. Refuses a database older than revision 0013. |
| Importer | `python -m app.importers.pitchdriven` | Runs inside the BrightFox container. It checks every checksum, creates the learners, and writes approvals, runs (one row per task), progress, chats, the AI cost ledger and photos in one transaction. `--dry-run` writes nothing. The same bundle can't be imported twice. |

What is **not** moved:
- Accounts and passwords. The parent sets new ones.
- Your own Foxy test chats. Add `--include-parent-tests` to keep them.
- Anything football.

Tasks that are no longer in a topic file are skipped and counted.

## Before you start
- BrightFox is deployed and passes `deploy\smoke-test.ps1`.
- PitchDriven's Study is read-only, so nothing changes during the move.
- The family exists, with the parent's login. It has **no learners called Erik or Alan yet**, because the import creates them.
  - The family's slug must be `danijel`, because the English topics live in `content/data/families/danijel/`.
- All commands below run on the server: `ssh -t footballadmin@152.53.191.32`.
  - Unlock the key first, as in `deploy/DEPLOYMENT.md`.

Create the family and the parent's login if they don't exist yet. You type the password; Claude never does:

```bash
cd /opt/ucilnica
docker compose exec -T ucilnica python -m app.manage create-family danijel --name "<family name>" </dev/null
docker compose exec ucilnica python -m app.manage set-password <parent username> --family danijel
```

## 1. Safety copies (PitchDriven)

The chat photos are in no backup today.

```bash
cd /opt/football7676
scripts/backup.sh daily
tar -czf ~/pitchdriven-study-$(date +%Y%m%d).tar.gz -C data study && ls -l ~/pitchdriven-study-*.tar.gz
```

## 2. Export (PitchDriven)

From the PC, in the `Ucilnica` folder, copy the script to the server. `deploy.ps1` doesn't ship `scripts/`.

```powershell
scp scripts\export_pitchdriven_study.py footballadmin@152.53.191.32:/tmp/export_pitchdriven_study.py
```

Then, on the server:

```bash
cd /opt/football7676
docker compose exec -T app python - --db /data/football7676.db --data /data --out /data/tmp/study-export.zip < /tmp/export_pitchdriven_study.py
sha256sum data/tmp/study-export.zip
```

It prints the row count of each table, the number of photos and the zip's sha256. If a message names a photo that's no longer on disk, it prints a warning.

## 3. Hand the bundle to BrightFox

```bash
install -D -m 600 /opt/football7676/data/tmp/study-export.zip /opt/ucilnica/data/tmp/study-export.zip
sha256sum /opt/ucilnica/data/tmp/study-export.zip
```

The sha256 must match step 2.

## 4. Rehearse on a scratch copy (BrightFox)

First, a backup of the live database. The rehearsal restores that backup into `import-test/` and imports into it for real. The live `data/` is not touched.

```bash
cd /opt/ucilnica
docker compose exec -T ucilnica python -m app.manage backup --label preimport </dev/null
B=$(ls -1t data/backups/ucilnica-backup-*-preimport.zip | head -n 1); echo "$B"
rm -rf import-test && mkdir -m 700 import-test
python3 -m zipfile -e "$B" import-test/ && rm import-test/manifest.json
cp data/tmp/study-export.zip import-test/
docker run --rm --network none --user "$(id -u):$(id -g)" -v "$PWD/import-test:/data" ucilnica-app:latest \
  python -m app.importers.pitchdriven /data/study-export.zip --family danijel --learners Erik,Alan
docker run --rm --network none --user "$(id -u):$(id -g)" -v "$PWD/import-test:/data" ucilnica-app:latest \
  python -m app.manage list-families
rm -rf import-test
```

**Read the summary.** For each kind of row it shows:
- how many are in the bundle;
- what they became;
- what was skipped, and why.

It must end with **"Every bundle row is accounted for."** The usual skips are:
- PitchDriven players who weren't named, such as the parent's own player;
- the parent's test chats, with their messages and photos;
- tasks no longer in their topic.

## 5. The real import (BrightFox)

```bash
cd /opt/ucilnica
docker compose exec -T ucilnica python -m app.importers.pitchdriven /data/tmp/study-export.zip --family danijel --learners Erik,Alan --dry-run </dev/null
docker compose exec -T ucilnica python -m app.importers.pitchdriven /data/tmp/study-export.zip --family danijel --learners Erik,Alan </dev/null
```

The dry run must show the same counts as the rehearsal. The real run ends with "Imported (import #1)". If anything fails, nothing is written and the copied photos are removed. Fix the cause and run it again.

## 6. Logins and checks

Erik's and Alan's logins (you type the passwords):

```bash
docker compose exec ucilnica python -m app.manage set-password erik --family danijel --learner Erik
docker compose exec ucilnica python -m app.manage set-password alan --family danijel --learner Alan
```

Then check, signed in as the parent:
- **Topics:** each kid's approved topics are there.
- **Results:** "How the kids did" shows the old runs.
- **Chats:** they open, with their photos.
- **Foxy settings:** grade, daily limit and notes match PitchDriven.

Old AI costs are in the ledger as "imported". They don't count toward this month's budget.

## 7. Clean up

The bundle holds the kids' chats:

```bash
rm /opt/football7676/data/tmp/study-export.zip /opt/ucilnica/data/tmp/study-export.zip /tmp/export_pitchdriven_study.py
```

Keep `~/pitchdriven-study-*.tar.gz` until PitchDriven's Study code and tables are removed (about 4 weeks later, Phase 3b).

## Testing

`backend/tests/test_import.py` builds a synthetic PitchDriven database with the layout of its migrations 0011–0013, runs the exporter on stdin with `-I -S` as on the server, and imports the bundle into a scratch family.
- It never uses real data and never touches the server.
- It checks the counts, versions, task rows, goal ids, photo checksums, skipped parent tests, the dry run, refusing a second import, rolling back a failed import, and that no password hash is exported.
