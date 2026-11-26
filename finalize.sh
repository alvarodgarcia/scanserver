#!/bin/bash
set -euo pipefail

DIR="$1"
FINAL="$2"
OCR="$3"

shopt -s nullglob

PAGES=("$DIR"/pagina-*.png)
COUNT=${#PAGES[@]}

if [ "$COUNT" -eq 0 ]; then
    echo "SCANSTATE|0|error|No existen páginas para generar el documento"
    exit 1
fi

ORDERED=("${PAGES[@]}")

# ============================================================
# DÚPLEX MANUAL
# ============================================================

if [ -f "$DIR/.duplex_split" ]; then

    SPLIT=$(
        cat "$DIR/.duplex_split"
    )

    if ! [[ "$SPLIT" =~ ^[0-9]+$ ]]; then
        echo "SCANSTATE|0|error|Estado dúplex no válido"
        exit 2
    fi

    ODD=(
        "${PAGES[@]:0:SPLIT}"
    )

    EVEN=(
        "${PAGES[@]:SPLIT}"
    )

    ODD_COUNT=${#ODD[@]}
    EVEN_COUNT=${#EVEN[@]}

    # Permitimos:
    #   mismas caras impares y pares
    #   una impar adicional = última hoja sin reverso

    if [ "$EVEN_COUNT" -gt "$ODD_COUNT" ] || \
       [ $((ODD_COUNT - EVEN_COUNT)) -gt 1 ]; then

        echo \
        "SCANSTATE|0|error|Dúplex incompleto: ${ODD_COUNT} caras impares y ${EVEN_COUNT} caras pares"

        exit 3
    fi

    REVERSE=1

    if [ -f "$DIR/.duplex_reverse_even" ]; then
        REVERSE=$(
            cat "$DIR/.duplex_reverse_even"
        )
    fi

    if [ "$REVERSE" = "1" ]; then

        REVERSED=()

        for ((
            i=EVEN_COUNT-1;
            i>=0;
            i--
        )); do

            REVERSED+=(
                "${EVEN[$i]}"
            )

        done

        EVEN=(
            "${REVERSED[@]}"
        )
    fi

    ORDERED=()

    # Intercalar todas las parejas completas
    for ((
        i=0;
        i<EVEN_COUNT;
        i++
    )); do

        ORDERED+=(
            "${ODD[$i]}"
        )

        ORDERED+=(
            "${EVEN[$i]}"
        )

    done

    # Si queda una cara impar, es la última página
    # de una hoja que no tiene reverso.
    if [ "$ODD_COUNT" -eq $((EVEN_COUNT + 1)) ]; then

        ORDERED+=(
            "${ODD[$((ODD_COUNT - 1))]}"
        )

        echo \
        "SCANSTATE|57|pdf|Última hoja sin reverso · añadiendo página final"

    fi

    COUNT=${#ORDERED[@]}

    echo \
    "SCANSTATE|55|pdf|Ordenando ${COUNT} páginas a doble cara"
fi


# ============================================================
# CREAR PDF
# ============================================================

echo \
"SCANSTATE|60|pdf|Generando PDF de ${COUNT} páginas"

img2pdf \
    "${ORDERED[@]}" \
    -o "$DIR/original.pdf"


# ============================================================
# OCR
# ============================================================

if [ "$OCR" = "true" ]; then

    echo \
    "SCANSTATE|70|ocr|OCR rápido · ${COUNT} páginas"

    CPU=$(nproc)

    if [ "$CPU" -ge 2 ]; then
        JOBS=2
    else
        JOBS=1
    fi

    OCR_LANG="${SCANSERVER_OCR_LANG:-spa}"

    export OMP_THREAD_LIMIT=1

    /usr/bin/ocrmypdf \
        --plugin /opt/scanserver/ocr_progress.py \
        -l "$OCR_LANG" \
        --output-type pdf \
        --optimize 0 \
        --jobs "$JOBS" \
        --tesseract-timeout 45 \
        "$DIR/original.pdf" \
        "$FINAL"

else

    echo \
    "SCANSTATE|95|saving|Guardando PDF"

    mv \
        "$DIR/original.pdf" \
        "$FINAL"
fi

echo \
"SCANSTATE|100|finished|Documento disponible"
