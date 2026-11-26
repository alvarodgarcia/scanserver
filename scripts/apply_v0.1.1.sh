#!/usr/bin/env bash
# ScanServer v0.1.1 candidate - conservative, pinned-code upgrade for Debian LXC
# Does not touch users, PDFs, Samba configuration or OS credentials.
set -Eeuo pipefail
umask 077

REPO='alvarodgarcia/scanserver'
PINNED_COMMIT='1f8f44ec756e1aae0ec428649bebbdbe98c283c9'
APP_ROOT='/opt/scanserver'
SESSIONS='/srv/scans/sessions'
BACKUP_ROOT='/var/backups'
SERVICE=''
ARCHIVE=''
HEALTH_URL='http://127.0.0.1:8080/api/me'
CHECK_ONLY=0
BACKUP=''
STOPPED=0
SUCCESS=0
TMPDIR_PATCH=''

FILES=('web/app.py' 'web/static/app.js' 'web/static/index.html')
declare -A BLOBS=(
  ['web/app.py']='d24ee6e173fb3849dfbba3ef6c5e16d8c8263904'
  ['web/static/app.js']='15c46727e9d0bfa2ab499dfbf0e738d34b83c6f9'
  ['web/static/index.html']='776e957efe2f4c623b76b76b8f2520341e03c18d'
)

usage() {
  cat <<'HELP'
Uso (como root):
  bash apply_v0.1.1.sh --check-only [--service scanserver-web.service]
  bash apply_v0.1.1.sh [--service scanserver-web.service] [--health-url http://127.0.0.1:8080/api/me] [--archive /root/scanserver-commit.tar.gz]

No se instalará nada si hay sesiones de escaneo pendientes o si las variables
SCANSERVER_SECRET (32+ caracteres), SCANSERVER_SANE_DEVICE y
SCANSERVER_SCANNER_STATUS_URL no están presentes en el servicio en ejecución.
El archivo --archive permite instalar sin Internet en el LXC, pero debe
proceder del commit fijado; los 3 blobs se verifican antes de cualquier cambio.
HELP
}
log() { printf '[ScanServer] %s\n' "$*"; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

while (( $# )); do
  case "$1" in
    --service) [[ $# -ge 2 ]] || die 'Falta --service'; SERVICE="$2"; shift 2 ;;
    --archive) [[ $# -ge 2 ]] || die 'Falta --archive'; ARCHIVE="$2"; shift 2 ;;
    --health-url) [[ $# -ge 2 ]] || die 'Falta --health-url'; HEALTH_URL="$2"; shift 2 ;;
    --check-only) CHECK_ONLY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "Argumento desconocido: $1" ;;
  esac
done

(( EUID == 0 )) || die 'Ejecuta como root dentro del LXC.'
for command in systemctl python3 tar awk sha1sum curl flock pgrep find tr grep wc cp chmod chown mv; do
  command -v "$command" >/dev/null || die "Falta el comando $command"
done
exec 9>/run/lock/scanserver-v011-deploy.lock
flock -n 9 || die 'Ya se está ejecutando otro despliegue.'

if [[ -z "$SERVICE" ]]; then
  mapfile -t found < <(systemctl list-unit-files --no-legend 'scanserver*.service' 2>/dev/null | awk '{print $1}' | sort -u)
  (( ${#found[@]} == 1 )) || die 'Indica --service NOMBRE.service. Consulta systemctl list-unit-files | grep -i scanserver'
  SERVICE="${found[0]}"
fi
[[ "$SERVICE" == *.service ]] || SERVICE="${SERVICE}.service"
systemctl show "$SERVICE" --property=LoadState --value | grep -Fxq loaded || die "No se encuentra $SERVICE"
systemctl is-active --quiet "$SERVICE" || die "$SERVICE no está activo. No es seguro asumir cómo está instalado."

workdir=$(systemctl show "$SERVICE" --property=WorkingDirectory --value)
execstr=$(systemctl show "$SERVICE" --property=ExecStart --value)
if [[ "$workdir" != "$APP_ROOT" && "$execstr" != *"$APP_ROOT"* ]]; then
  die "No puedo vincular $SERVICE de forma segura con $APP_ROOT; revisa WorkingDirectory/ExecStart."
fi
pid=$(systemctl show "$SERVICE" --property=MainPID --value)
[[ "$pid" =~ ^[1-9][0-9]*$ && -r "/proc/$pid/environ" ]] || die 'No puedo inspeccionar el entorno real del proceso activo.'

# Solo se comprueban longitudes/presencia: NO se imprimen credenciales.
check_env() {
  local key="$1" minimum="$2" length
  length=$(tr '\0' '\n' <"/proc/$pid/environ" | awk -v key="$key" '
    index($0,key"=")==1 { print length(substr($0,length(key)+2)); found=1; exit }
    END { if (!found) print 0 }
  ')
  [[ "$length" =~ ^[0-9]+$ && "$length" -ge "$minimum" ]] ||
    die "El proceso no tiene $key con la longitud mínima. Configura su EnvironmentFile antes del parche."
}
check_env SCANSERVER_SECRET 32
# Los scripts originales pueden tener el escáner integrado. No los sustituimos:
# solo la nueva app necesita el secreto de firma de sesión.

for rel in "${FILES[@]}"; do
  [[ -f "$APP_ROOT/$rel" && ! -L "$APP_ROOT/$rel" ]] || die "Falta $APP_ROOT/$rel o es un enlace simbólico."
done
[[ -d "$SESSIONS" ]] || die "No encuentro $SESSIONS. Revisar instalación antes de modificar."

no_active_jobs() {
  local active
  active=$(find "$SESSIONS" -mindepth 1 -maxdepth 1 -type d -print -quit)
  [[ -z "$active" ]] || die "Sesiones sin finalizar en $SESSIONS. Finaliza/cancela desde la interfaz; no borres estos datos a ciegas."
  for proc in scanimage ocrmypdf img2pdf; do
    if pgrep -x "$proc" >/dev/null 2>&1; then
      die "Hay un proceso $proc en ejecución. Finaliza su trabajo antes de aplicar el parche."
    fi
  done
}
no_active_jobs
log "Servicio: $SERVICE. Proceso en ejecución identificado, SCANSERVER_SECRET presente."
log 'No se han encontrado directorios de sesión ni procesos de escaneo/OCR activos.'
log "Código fijado al commit $PINNED_COMMIT. Solo se reemplazarán los 3 archivos web de ScanServer."
if (( CHECK_ONLY )); then
  log 'PRECHECK OK: no se ha detenido ningún servicio ni modificado ningún archivo.'
  exit 0
fi

TMPDIR_PATCH=$(mktemp -d /tmp/scanserver-v011.XXXXXXXX)
cleanup() {
  local rc=$?
  trap - EXIT
  if (( STOPPED && ! SUCCESS )); then
    printf '[ALERTA] Despliegue incompleto. Restaurando los archivos originales...\n' >&2
    if [[ -n "$BACKUP" ]]; then
      for rel in "${FILES[@]}"; do
        cp -a -- "$BACKUP/$rel" "$APP_ROOT/$rel" || true
      done
    fi
    systemctl stop "$SERVICE" || true
    systemctl start "$SERVICE" || true
    printf '[ALERTA] Revisar systemctl status %s y journalctl -u %s. Backup: %s\n' "$SERVICE" "$SERVICE" "$BACKUP" >&2
  fi
  [[ -z "$TMPDIR_PATCH" ]] || rm -rf -- "$TMPDIR_PATCH"
  exit "$rc"
}
trap cleanup EXIT

if [[ -z "$ARCHIVE" ]]; then
  ARCHIVE="$TMPDIR_PATCH/source.tar.gz"
  log 'Descargando commit público exacto de GitHub por HTTPS (sin desactivar TLS)...'
  curl --fail --location --show-error --silent --retry 2 --connect-timeout 8 --max-time 80 --proto '=https' --proto-redir '=https' \
    "https://github.com/$REPO/archive/$PINNED_COMMIT.tar.gz" -o "$ARCHIVE" ||
    die 'Descarga fallida. Puedes transferir el archive desde Windows y usar --archive.'
else
  [[ -f "$ARCHIVE" ]] || die "No existe el archivo offline: $ARCHIVE"
fi

first=$(tar -tzf "$ARCHIVE" | sed -n '1p') || die 'Tarball inválido.'
[[ "$first" == scanserver-*/ ]] || die 'Formato de archive GitHub no reconocido.'
prefix=${first%%/*}
mkdir -p "$TMPDIR_PATCH/stage/web/static"
for rel in "${FILES[@]}"; do
  tar -xzOf "$ARCHIVE" "$prefix/$rel" >"$TMPDIR_PATCH/stage/$rel" || die "Falta $rel en la descarga"
  size=$(wc -c <"$TMPDIR_PATCH/stage/$rel")
  actual=$({ printf 'blob %s\0' "$size"; cat "$TMPDIR_PATCH/stage/$rel"; } | sha1sum | awk '{print $1}')
  [[ "$actual" == "${BLOBS[$rel]}" ]] || die "Integridad incorrecta: $rel (el parche no se aplicará)."
done
python3 -m py_compile "$TMPDIR_PATCH/stage/web/app.py" || die 'Sintaxis Python inválida'
if command -v node >/dev/null 2>&1; then
  node --check "$TMPDIR_PATCH/stage/web/static/app.js" || die 'Sintaxis JavaScript inválida'
fi
log 'Contenido verificado contra los hashes Git blob publicados. Sintaxis validada.'

# Revalidar justo antes de detener: bloquear si alguien inició una sesión.
no_active_jobs
BACKUP="$BACKUP_ROOT/scanserver-v0.1.1-$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -m 700 -p "$BACKUP/web/static"
printf '%s\n' "$SERVICE" >"$BACKUP/service.txt"
printf '%s\n' "$PINNED_COMMIT" >"$BACKUP/new-commit.txt"
log "Copia de seguridad privada: $BACKUP"
for rel in "${FILES[@]}"; do
  cp -a -- "$APP_ROOT/$rel" "$BACKUP/$rel" || die "No se pudo respaldar $rel"
done
log 'Deteniendo el servicio para respaldar SQLite de forma consistente...'
STOPPED=1
systemctl stop "$SERVICE" || die 'No se pudo detener el servicio.'
if [[ -d "$APP_ROOT/data" ]]; then
  cp -a -- "$APP_ROOT/data" "$BACKUP/data" || die 'Falló la copia de la base de datos.'
fi

for rel in "${FILES[@]}"; do
  tmp="$APP_ROOT/$rel.v011.tmp.$$"
  cp -- "$TMPDIR_PATCH/stage/$rel" "$tmp" || die "Error copiando $rel"
  chown --reference="$APP_ROOT/$rel" "$tmp"
  chmod --reference="$APP_ROOT/$rel" "$tmp"
  mv -f -- "$tmp" "$APP_ROOT/$rel"
done
log 'Archivos aplicados. Iniciando servicio...'
systemctl start "$SERVICE" || die 'El servicio no ha podido iniciarse.'

healthy=0
for i in {1..20}; do
  if systemctl is-active --quiet "$SERVICE"; then
    http=$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 2 "$HEALTH_URL" || true)
    if [[ "$http" == 401 || "$http" == 200 ]]; then
      healthy=1
      break
    fi
  fi
  sleep 1
done
(( healthy == 1 )) || die "No se validó la API (GET $HEALTH_URL debe responder 401/200)."
SUCCESS=1
log 'PARCHE APLICADO. Servicio activo y API verificada.'
log "Reinicia sesión en la web. Backup: $BACKUP"
log "Para revertir: bash rollback_v0.1.1.sh --backup '$BACKUP' --service '$SERVICE' --health-url '$HEALTH_URL'"
