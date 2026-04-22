#!/usr/bin/env bash
# Wrapper — délègue au script principal dans le repo.
REPO="${HOME}/MonJardin"
SCRIPT="$REPO/update_pi.sh"

if [[ ! -f "$SCRIPT" ]]; then
  echo "Premier lancement — téléchargement initial..."
  git -C "$REPO" pull origin v2.0 2>/dev/null || git clone -b v2.0 https://github.com/patrickpinard/MonJardin.git "$REPO"
fi

exec bash "$SCRIPT" "$@"
