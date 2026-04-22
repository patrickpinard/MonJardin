#!/usr/bin/env bash
# ============================================================
#  MonJardin — Script de mise à jour sur Raspberry Pi
#  Usage : bash update_pi.sh [--branch v2.0] [--restart]
# ============================================================
set -euo pipefail

# ── Paramètres ──────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BRANCH="${BRANCH:-v2.0}"
APP_DIR="$REPO_DIR/garden_manager"
VENV="$APP_DIR/venv"
LOG_DIR="$APP_DIR/logs"
SERVICE_NAME="monjardin"
AUTO_RESTART=false

for arg in "$@"; do
  case $arg in
    --branch=*) BRANCH="${arg#*=}" ;;
    --restart)  AUTO_RESTART=true ;;
  esac
done

# ── Couleurs ────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[OK]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[!!]${NC}  $*"; }
error()   { echo -e "${RED}[ERR]${NC} $*"; exit 1; }
section() { echo -e "\n${GREEN}══${NC} $* ${GREEN}══${NC}"; }

# ── Vérifications préalables ────────────────────────────────
section "Vérifications"
[[ -d "$REPO_DIR/.git" ]] || error "Pas de dépôt git dans $REPO_DIR"
command -v git  >/dev/null 2>&1 || error "git non installé"
command -v python3 >/dev/null 2>&1 || error "python3 non installé"
info "Répertoire : $REPO_DIR"
info "Branche cible : $BRANCH"

# ── Sauvegarder la base de données ──────────────────────────
section "Sauvegarde base de données"
DB_SRC="$APP_DIR/data/garden.db"
if [[ -f "$DB_SRC" ]]; then
  BACKUP="$APP_DIR/data/garden_$(date +%Y%m%d_%H%M%S).db"
  cp "$DB_SRC" "$BACKUP"
  info "Backup créé : $BACKUP"
  # Garder uniquement les 5 derniers backups
  ls -t "$APP_DIR/data/garden_"*.db 2>/dev/null | tail -n +6 | xargs -r rm --
  info "Anciens backups nettoyés (conservation des 5 derniers)"
else
  warn "Aucune base de données trouvée — premier démarrage ?"
fi

# ── Récupérer les mises à jour GitHub ───────────────────────
section "Mise à jour depuis GitHub (branche $BRANCH)"
cd "$REPO_DIR"

# Stash les modifications locales non commitées (ex. .env local)
if ! git diff --quiet || ! git diff --cached --quiet; then
  warn "Modifications locales détectées — mise en attente (git stash)"
  git stash push -m "update_pi auto-stash $(date +%Y%m%d_%H%M%S)"
fi

git fetch origin
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [[ "$LOCAL" == "$REMOTE" ]]; then
  info "Déjà à jour — commit : ${LOCAL:0:8}"
else
  info "Mise à jour : ${LOCAL:0:8} → ${REMOTE:0:8}"
  git checkout "$BRANCH"
  git pull origin "$BRANCH"
  info "Code mis à jour"
fi

# ── Mise à jour des dépendances Python ──────────────────────
section "Dépendances Python"
if [[ ! -d "$VENV" ]]; then
  warn "Environnement virtuel absent — création…"
  python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "$APP_DIR/requirements.txt"
info "Dépendances à jour"

# ── Création du dossier logs ─────────────────────────────────
mkdir -p "$LOG_DIR"

# ── Afficher le résumé des commits récents ──────────────────
section "Derniers commits"
git log --oneline -5

# ── Redémarrage ─────────────────────────────────────────────
section "Redémarrage de l'application"

restart_systemd() {
  if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    info "Service systemd '$SERVICE_NAME' détecté — redémarrage…"
    sudo systemctl restart "$SERVICE_NAME"
    sleep 3
    if systemctl is-active --quiet "$SERVICE_NAME"; then
      info "Service redémarré avec succès"
      sudo systemctl status "$SERVICE_NAME" --no-pager -l | tail -6
    else
      error "Le service n'a pas démarré — vérifiez : sudo journalctl -u $SERVICE_NAME -n 30"
    fi
    return 0
  fi
  return 1
}

restart_manual() {
  info "Arrêt du processus Python en cours…"
  pkill -f "python run.py" 2>/dev/null && sleep 2 || true
  pkill -f "python3 run.py" 2>/dev/null && sleep 1 || true
  info "Démarrage de l'application…"
  cd "$APP_DIR"
  nohup python run.py > "$LOG_DIR/app.log" 2>&1 &
  NEW_PID=$!
  sleep 3
  if kill -0 "$NEW_PID" 2>/dev/null; then
    info "Application démarrée — PID $NEW_PID"
    info "Logs : tail -f $LOG_DIR/app.log"
  else
    error "L'application n'a pas démarré — vérifiez $LOG_DIR/app.log"
  fi
}

if [[ "$AUTO_RESTART" == true ]]; then
  restart_systemd || restart_manual
else
  echo ""
  echo -e "  Pour redémarrer manuellement :"
  echo -e "    ${YELLOW}sudo systemctl restart $SERVICE_NAME${NC}   (si service systemd)"
  echo -e "    ${YELLOW}cd $APP_DIR && python run.py${NC}   (si démarrage manuel)"
  echo ""
  read -rp "  Redémarrer maintenant ? [o/N] " REPLY
  if [[ "${REPLY,,}" =~ ^(o|oui|y|yes)$ ]]; then
    restart_systemd || restart_manual
  else
    warn "Redémarrage ignoré — relancez l'app manuellement pour appliquer les changements"
  fi
fi

section "Mise à jour terminée"
info "Version : $(git log --oneline -1)"
