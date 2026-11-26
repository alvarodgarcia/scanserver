#!/usr/bin/env bash
# Reverts ScanServer v0.1.1 code to the backup from apply_v0.1.1.sh.
# Leaves SQLite intact to preserve any new user activity; the added column is compatible.
set -Eeuo pipefail
umask 077

APP_ROOT='/opt/scanserver'
SESSIONS='/srv/scans/sessions'
BACKUP=''
SERVICE=''
HEALTH_URL='http://127.0.0.1:8080/api/me'
FILES=('web/app.py' 'web/static/app.js' 'web/static/index.html')

die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }
while (( $# )); do
  case "$1" in
    --backup) [[ $# -ge 2 ]] || die 'Falta --backup'; BACKUP="$2"; shift 2 ;;
    --service) [[ $# -ge 2 ]] || die 'Falta --service'; SERVICE="$2"; shift 2 ;;
    --health-url) [[ $# -ge 2 ]] || die 'Falta --health-url'; HEALTH_URL="$2"; shift 2 ;;
    -h|--help) echo 'Uso: bash rollback_v0.1.1.sh --backup /var/backups/scanserver-v0.1.1-... [--service nombre]'; exit 0 ;;
    *) die "Argumento inválido: $1" ;;
  esac
done
(( EUID == 0 )) || die 'Ejecuta como root.'
[[ "$BACKUP" == /var/backups/scanserver-v0.1.1-* ]] || die 'Indica una copia creada por apply_v0.1.1.sh bajo /var/backups.'
[[ -d "$BACKUP" && -f "$BACKUP/service.txt" ]] || die 'No encuentro la copia seleccionada.'
[[ -z "$SERVICE" ]] && SERVICE=$(cat "$BACKUP/service.txt")
[[ "$SERVICE" == *.service ]] || SERVICE="${SERVICE}.service"
for rel in "${FILES[@]}"; do
  [[ -f "$BACKUP/$rel" ]] || die "Falta copia de $rel"
done
if find "$SESSIONS" -mindepth 1 -maxdepth 1 -type d -print -quit | grep -q .; then
  die 'Hay sesiones sin finalizar. No se interrumpirá el trabajo del escáner.'
fi
exec 9>/run/lock/scanserver-v011-deploy.lock
flock -n 9 || die 'Hay otro proceso de despliegue/rollback.'
for proc in scanimage ocrmypdf img2pdf; do
  ! pgrep -x "$proc" >/dev/null 2>&1 || die "Proceso $proc en ejecución; no se revierte."
done
printf '[ScanServer] Deteniendo %s y restaurando tres archivos...\n' "$SERVICE"
systemctl stop "$SERVICE"
for rel in "${FILES[@]}"; do
  cp -a -- "$BACKUP/$rel" "$APP_ROOT/$rel"
done
systemctl start "$SERVICE"
healthy=0
for i in {1..20}; do
  if systemctl is-active --quiet "$SERVICE"; then
    http=$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 2 "$HEALTH_URL" || true)
    if [[ "$http" == 401 || "$http" == 200 ]]; then healthy=1; break; fi
  fi
  sleep 1
done
(( healthy == 1 )) || die "Servicio no verificado; revisa journalctl -u '$SERVICE' -n 60 --no-pager"
printf '[ScanServer] ROLLBACK COMPLETADO. SQLite no restaurada para evitar pérdida de usuarios recientes.\n'
printf '[ScanServer] Copia de seguridad preservada en %s\n' "$BACKUP"
