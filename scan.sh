#!/bin/bash
set -euo pipefail

DEVICE="${SCANSERVER_SANE_DEVICE:?Define SCANSERVER_SANE_DEVICE}"

MODE="${1:-Gray}"
DPI="${2:-300}"
OCR="${3:-true}"

DEST="/srv/scans/documentos"
TMPBASE="/srv/scans/tmp"

case "$MODE" in
    Gray|Color) ;;
    *) echo "Modo no válido"; exit 1 ;;
esac

case "$DPI" in
    200|300|600) ;;
    *) echo "Resolución no válida"; exit 1 ;;
esac

case "$OCR" in
    true|false) ;;
    *) echo "OCR no válido"; exit 1 ;;
esac

FECHA=$(date '+%Y-%m-%d_%H-%M-%S')
TMP="${TMPBASE}/${FECHA}"
FINAL="${DEST}/${FECHA}.pdf"

mkdir -p "$TMP" "$DEST"

cleanup() {
    rm -rf "$TMP"
}

trap cleanup EXIT

emit() {
    printf 'SCANSTATE|%s|%s|%s|%s\n' \
        "$1" "$2" "$3" "${4:-}"
}

emit 5 preparing "Preparando el escáner" ""

echo "Configuración: $MODE / ${DPI} dpi / OCR=$OCR"

emit 10 scanning "Escaneando documentos" ""

#
# El ADF normalmente termina devolviendo "sin documentos".
# No damos por fallido el trabajo si ya se han obtenido páginas.
#
set +e

scanimage \
    -d "$DEVICE" \
    --source ADF \
    --resolution "$DPI" \
    --mode "$MODE" \
    --scan-intent Document \
    -x 210 \
    -y 297 \
    --format=png \
    --progress \
    --batch="${TMP}/pagina-%03d.png" 2>&1

SCAN_RC=$?

set -e

PAGES=$(find "$TMP" -maxdepth 1 -name 'pagina-*.png' -type f | wc -l)

if [ "$PAGES" -eq 0 ]; then
    emit 0 error "No se ha escaneado ninguna página" ""
    exit 1
fi

emit 60 pdf "Generando PDF de ${PAGES} páginas" "$PAGES"

img2pdf \
    "${TMP}"/pagina-*.png \
    -o "${TMP}/original.pdf"

if [ "$OCR" = "true" ]; then

    emit 70 ocr "Aplicando OCR a ${PAGES} páginas" "$PAGES"

    ocrmypdf \
        --plugin /opt/scanserver/ocr_progress.py \
        -l spa+eng \
        --rotate-pages \
        --deskew \
        --optimize 1 \
        "${TMP}/original.pdf" \
        "$FINAL"

else

    emit 95 saving "Guardando PDF" "$PAGES"

    mv "${TMP}/original.pdf" "$FINAL"

fi

emit 98 saving "Finalizando documento" "$PAGES"

FILENAME=$(basename "$FINAL")

emit 100 finished "PDF disponible" "$FILENAME"
