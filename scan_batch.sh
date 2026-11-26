#!/bin/bash
set -u

DEVICE="${SCANSERVER_SANE_DEVICE:?Define SCANSERVER_SANE_DEVICE}"
STATUS_URL="${SCANSERVER_SCANNER_STATUS_URL:?Define SCANSERVER_SCANNER_STATUS_URL}"

DIR="$1"
START="$2"
MODE="$3"
DPI="$4"

MAX_OPEN_RETRIES=3
MAX_AUTO_ROUNDS=20

mkdir -p "$DIR"


page_count() {
    find "$DIR" \
        -maxdepth 1 \
        -name 'pagina-*.png' \
        -type f 2>/dev/null \
        | wc -l
}


# ------------------------------------------------------------
# Estado REAL del ADF vía eSCL
#
# Devuelve:
#   OverallState|AdfState
#
# Ejemplo:
#   Idle|ScannerAdfLoaded
# ------------------------------------------------------------

escl_status() {

    local XML
    local STATE
    local ADF

    XML=$(
        curl -ksS \
            --connect-timeout 2 \
            --max-time 3 \
            "$STATUS_URL" \
            2>/dev/null
    ) || {
        echo "Unknown|Unknown"
        return
    }

    XML=$(
        printf '%s' "$XML" |
        tr '\n' ' '
    )

    STATE=$(
        printf '%s' "$XML" |
        grep -oE \
            '<([^>:]+:)?State>[^<]+' |
        head -1 |
        sed -E 's/.*>//'
    )

    ADF=$(
        printf '%s' "$XML" |
        grep -oE \
            '<([^>:]+:)?AdfState>[^<]+' |
        head -1 |
        sed -E 's/.*>//'
    )

    echo "${STATE:-Unknown}|${ADF:-Unknown}"
}


# ------------------------------------------------------------
# Esperar hasta conocer el estado REAL del alimentador
#
# return 0  -> realmente vacío
# return 10 -> todavía quedan hojas: continuar automáticamente
# return 20+ -> problema del ADF
# ------------------------------------------------------------

wait_real_adf_state() {

    local EMPTY_COUNT=0
    local UNKNOWN_COUNT=0
    local VALUE
    local STATE
    local ADF

    # Evita leer el estado justo en la transición
    # de la última página descargada.
    sleep 1

    for ((i=1; i<=40; i++)); do

        VALUE=$(escl_status)

        STATE="${VALUE%%|*}"
        ADF="${VALUE#*|}"

        echo \
        "ADFSTATUS|${STATE}|${ADF}"

        case "$ADF" in

            ScannerAdfJam)

                echo \
                "scanimage: Document feeder jammed (ScannerAdfJam)"

                return 20
                ;;


            ScannerAdfMispick)

                echo \
                "scanimage: Document feeder mispick (ScannerAdfMispick)"

                return 21
                ;;


            ScannerAdfHatchOpen|ScannerAdfDoorOpen)

                echo \
                "scanimage: Document feeder cover open (${ADF})"

                return 22
                ;;


            ScannerAdfMultipickDetected)

                echo \
                "scanimage: Document feeder multiple sheets detected"

                return 23
                ;;


            ScannerAdfInputTrayOverloaded)

                echo \
                "scanimage: Document feeder overloaded"

                return 24
                ;;


            ScannerAdfInputTrayFailed)

                echo \
                "scanimage: Document feeder failure"

                return 25
                ;;


            ScannerAdfLoaded)

                EMPTY_COUNT=0

                # Esperamos a que termine cualquier actividad
                # previa antes de abrir un nuevo ScanJob.
                if [ "$STATE" = "Idle" ]; then
                    return 10
                fi
                ;;


            ScannerAdfProcessing)

                EMPTY_COUNT=0
                ;;


            ScannerAdfEmpty)

                # Nunca consideramos vacío mientras
                # el escáner continúe Processing.
                if [ "$STATE" = "Processing" ]; then

                    EMPTY_COUNT=0

                elif [ "$STATE" = "Idle" ]; then

                    EMPTY_COUNT=$((EMPTY_COUNT + 1))

                    # Exigimos tres lecturas consecutivas
                    # Idle + Empty para evitar falsos vacíos.
                    if [ "$EMPTY_COUNT" -ge 3 ]; then
                        return 0
                    fi
                fi
                ;;


            *)

                UNKNOWN_COUNT=$((UNKNOWN_COUNT + 1))
                ;;

        esac

        echo \
        "SCANSTATE|95|scanning|Comprobando el alimentador…"

        sleep 0.5
    done


    # Si no hemos podido determinarlo, conservamos el
    # comportamiento anterior en lugar de bloquear la sesión.
    echo \
    "ADFSTATUS|TIMEOUT|No se pudo confirmar el estado del alimentador"

    return 0
}


INITIAL_TOTAL=$(page_count)

NEXT_START="$START"

ROUND=1


echo \
"SCANSTATE|10|scanning|Escaneando documentos"


# ============================================================
# El mismo lote físico puede requerir más de un ScanJob eSCL.
#
# Mientras la impresora siga diciendo Loaded,
# continuamos automáticamente.
# ============================================================

while [ "$ROUND" -le "$MAX_AUTO_ROUNDS" ]; do

    ATTEMPT=1

    while [ "$ATTEMPT" -le "$MAX_OPEN_RETRIES" ]; do

        BEFORE=$(page_count)

        TMPLOG=$(mktemp)

        if [ "$ATTEMPT" -gt 1 ]; then

            echo \
            "SCANSTATE|10|scanning|Reintentando conexión con el escáner (${ATTEMPT}/${MAX_OPEN_RETRIES})"

            sleep 2
        fi


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
            --batch="${DIR}/pagina-%04d.png" \
            --batch-start="$NEXT_START" \
            2>&1 |
            tee "$TMPLOG"

        SCAN_RC=${PIPESTATUS[0]}

        set -e


        AFTER=$(page_count)

        CREATED=$((AFTER - BEFORE))


        # ----------------------------------------------------
        # Se han escaneado páginas
        # ----------------------------------------------------

        if [ "$CREATED" -gt 0 ]; then

            rm -f "$TMPLOG"

            NEXT_START=$((AFTER + 1))

            echo \
            "SCANSTATE|95|scanning|Verificando si quedan hojas…"

            set +e
            wait_real_adf_state
            ADF_RC=$?
            set -e


            # Todavía hay hojas en el alimentador:
            # NO pasamos a waiting_more.
            if [ "$ADF_RC" -eq 10 ]; then

                echo \
                "SCANSTATE|10|scanning|Quedan hojas · continuando automáticamente"

                ROUND=$((ROUND + 1))

                break
            fi


            # ADF realmente vacío.
            if [ "$ADF_RC" -eq 0 ]; then

                FINAL_TOTAL=$(page_count)

                echo \
                "BATCHDONE|${FINAL_TOTAL}|0"

                exit 0
            fi


            # Error físico real: atasco, tapa, multipick...
            FINAL_TOTAL=$(page_count)

            echo \
            "BATCHDONE|${FINAL_TOTAL}|${ADF_RC}"

            exit 0
        fi


        # ----------------------------------------------------
        # No ha generado páginas: reintentar solo errores
        # transitorios de apertura/comunicación.
        # ----------------------------------------------------

        if grep -Eqi \
            'Error during device I/O|Device busy|device.*busy|I/O error|Invalid argument' \
            "$TMPLOG"
        then

            rm -f "$TMPLOG"

            if [ "$ATTEMPT" -lt "$MAX_OPEN_RETRIES" ]; then

                ATTEMPT=$((ATTEMPT + 1))

                continue
            fi

        else

            rm -f "$TMPLOG"
        fi


        # Comprobar además el ADF antes de afirmar
        # que ya no hay documentos.
        set +e
        wait_real_adf_state
        ADF_RC=$?
        set -e


        if [ "$ADF_RC" -eq 10 ]; then

            echo \
            "SCANSTATE|10|scanning|El alimentador todavía contiene hojas · reintentando"

            ROUND=$((ROUND + 1))

            break
        fi


        FINAL_TOTAL=$(page_count)


        if [ "$ADF_RC" -eq 0 ]; then

            echo \
            "scanimage: Document feeder empty"

            echo \
            "BATCHDONE|${FINAL_TOTAL}|7"

        else

            echo \
            "BATCHDONE|${FINAL_TOTAL}|${ADF_RC}"
        fi

        exit 0

    done

done


FINAL_TOTAL=$(page_count)

echo \
"scanimage: límite de continuaciones automáticas alcanzado"

echo \
"BATCHDONE|${FINAL_TOTAL}|1"

exit 0
