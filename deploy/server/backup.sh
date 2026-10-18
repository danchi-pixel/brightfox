#!/usr/bin/env bash
# Učilnica backups on the server: database + homework photos in one zip, made by the app itself
# (python -m app.manage backup), into /opt/ucilnica/data/backups (mode 600).
#   backup.sh daily      keeps 14   cron, every night 04:15
#   backup.sh weekly     keeps 8    cron, Sundays 04:30
#   backup.sh preupdate  keeps 5    run by update.sh before every update
#
# Planned crontab of footballadmin (crontab -e; see deploy/DEPLOYMENT.md - not installed by any script):
#   15 4 * * * /opt/ucilnica/scripts/backup.sh daily >> /opt/ucilnica/backup.log 2>&1
#   30 4 * * 0 /opt/ucilnica/scripts/backup.sh weekly >> /opt/ucilnica/backup.log 2>&1
set -euo pipefail
cd /opt/ucilnica
mode="${1:-daily}"
case "$mode" in
  daily)     keep=14 ;;
  weekly)    keep=8 ;;
  preupdate) keep=5 ;;
  *) echo "usage: $0 daily|weekly|preupdate" >&2; exit 2 ;;
esac
if ! docker compose ps --status running --services 2>/dev/null | grep -qx ucilnica; then
  echo "$(date -Is) the ucilnica container is not running - backup skipped" >&2
  exit 1
fi
# </dev/null: exec -T would otherwise read (and swallow) the rest of a script piped into bash.
docker compose exec -T ucilnica python -m app.manage backup --label "$mode" --keep "$keep" </dev/null
echo "$(date -Is) $mode backup done"
