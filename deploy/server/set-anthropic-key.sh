#!/usr/bin/env bash
# Store (or replace) the Anthropic API key for Foxy in /opt/ucilnica/secrets.env (mode 600), then recreate
# the Učilnica container so it picks the key up. Run by deploy/set-anthropic-key.ps1 in an interactive SSH
# session: the key is typed here (hidden), never shown, logged or passed as an argument.
set -euo pipefail
cd /opt/ucilnica
read -rsp "Paste the Anthropic API key for Ucilnica (starts with sk-ant-), then press Enter: " key
echo
key="$(printf '%s' "$key" | tr -d '[:space:]')"
case "$key" in
  "") echo "Nothing entered - nothing changed."; exit 1 ;;
  sk-ant-*) ;;
  *) echo "That doesn't look like an Anthropic API key (sk-ant-...). Nothing changed."; exit 1 ;;
esac
if ! [[ "$key" =~ ^sk-ant-[A-Za-z0-9_-]+$ ]]; then
  echo "The key contains unexpected characters. Nothing changed."
  exit 1
fi
umask 077
{ grep -v '^ANTHROPIC_API_KEY=' secrets.env 2>/dev/null || true; printf 'ANTHROPIC_API_KEY=%s\n' "$key"; } > secrets.env.new
unset key
chmod 600 secrets.env.new
mv secrets.env.new secrets.env
if [ ! -f compose.yaml ]; then
  echo "Saved. Ucilnica isn't installed yet; the first deploy will use the key."
  exit 0
fi
echo "Saved. Recreating BrightFox so Foxy can use it..."
docker compose up -d --force-recreate ucilnica </dev/null >/dev/null
for _ in $(seq 1 45); do
  state="$(docker inspect --format '{{.State.Health.Status}}' "$(docker compose ps -q ucilnica)" 2>/dev/null || echo unknown)"
  if [ "$state" = healthy ]; then
    echo "Done. In BrightFox, Foxy should no longer say 'not set up'."
    exit 0
  fi
  sleep 2
done
echo "The key is saved, but Ucilnica isn't healthy yet. Check: cd /opt/ucilnica && docker compose logs --tail 60 ucilnica"
exit 1
