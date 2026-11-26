import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid

from collections import deque
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from starlette.middleware.sessions import SessionMiddleware



# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE = Path("/opt/scanserver")

DB_PATH = BASE / "data/scanserver.db"

USERS_ROOT = Path("/srv/scans/usuarios")

SESSIONS_ROOT = Path("/srv/scans/sessions")

STATIC = BASE / "web/static"

SCAN_SCRIPT = BASE / "scan_batch.sh"

FINALIZE_SCRIPT = BASE / "finalize.sh"

SMB_HELPER = Path(
    "/usr/local/sbin/scanserver-smb-user"
)


USERS_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

SESSIONS_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

DB_PATH.parent.mkdir(
    parents=True,
    exist_ok=True
)


SECRET = os.environ.get("SCANSERVER_SECRET", "")
if len(SECRET) < 32:
    raise RuntimeError(
        "SCANSERVER_SECRET debe contener al menos 32 caracteres aleatorios. "
        "Configúralo antes de iniciar ScanServer."
    )

HTTPS_ONLY = (
    os.environ.get(
        "SCANSERVER_HTTPS",
        "0"
    )
    == "1"
)


app = FastAPI(
    title="ScanServer",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET,
    session_cookie="scanserver_session",
    max_age=28800,
    same_site="strict",
    https_only=HTTPS_ONLY,
)



PASSWORD_HASHER = PasswordHasher()


# ============================================================
# BASE DE DATOS
# ============================================================

def db_connection():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=10
    )

    conn.row_factory = (
        sqlite3.Row
    )

    return conn


def init_db():

    with db_connection() as conn:

        conn.execute(
            """
            PRAGMA journal_mode=WAL
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.commit()


init_db()


# ============================================================
# USUARIOS
# ============================================================

def user_by_id(user_id):

    with db_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (user_id,)
        ).fetchone()


def user_by_username(username):

    with db_connection() as conn:

        return conn.execute(
            """
            SELECT *
            FROM users
            WHERE lower(username) = lower(?)
            """,
            (username,)
        ).fetchone()


def public_user(user):

    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "is_admin": bool(
            user["is_admin"]
        ),
        "enabled": bool(
            user["enabled"]
        ),
    }


def require_user(request: Request):

    user_id = request.session.get(
        "user_id"
    )

    if not user_id:

        raise HTTPException(
            status_code=401,
            detail="No autenticado"
        )

    user = user_by_id(
        user_id
    )

    if (
        not user
        or not user["enabled"]
    ):

        request.session.clear()

        raise HTTPException(
            status_code=401,
            detail="Sesión no válida"
        )

    return user


def require_admin(request: Request):

    user = require_user(
        request
    )

    if not user["is_admin"]:

        raise HTTPException(
            status_code=403,
            detail="Se requieren permisos de administrador"
        )

    return user


def validate_username(username):

    username = (
        username
        .strip()
        .lower()
    )

    if not re.fullmatch(
        r"[a-z0-9._-]{3,32}",
        username
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "El usuario debe tener entre "
                "3 y 32 caracteres y utilizar "
                "solo letras, números, punto, "
                "guion o guion bajo"
            )
        )

    return username


def create_user_storage(username):

    root = (
        USERS_ROOT /
        username
    )

    root.mkdir(
        parents=True,
        exist_ok=True
    )

    (
        root /
        "Documentos"
    ).mkdir(
        exist_ok=True
    )


def smb_account(
    action,
    username,
    password=None
):

    command = [
        str(SMB_HELPER),
        action,
        username,
    ]

    input_data = None

    if password is not None:
        input_data = password + "\n"

    try:

        result = subprocess.run(
            command,
            input=input_data,
            text=True,
            capture_output=True,
            timeout=30,
        )

    except Exception as exc:

        raise HTTPException(
            500,
            f"Error gestionando SMB: {exc}"
        )

    if result.returncode != 0:

        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "Error desconocido"
        )

        raise HTTPException(
            500,
            f"Error gestionando SMB: {message}"
        )


def user_root(user):

    root = (
        USERS_ROOT /
        user["username"]
    )

    root.mkdir(
        parents=True,
        exist_ok=True
    )

    return root


# ============================================================
# RUTAS SEGURAS
# ============================================================

def relative_path(value):

    if not value:
        return Path()

    value = value.strip()

    if (
        not value
        or value == "."
    ):
        return Path()

    pure = PurePosixPath(
        value
    )

    if pure.is_absolute():

        raise HTTPException(
            400,
            "Ruta no válida"
        )

    for part in pure.parts:

        if part in (
            "",
            ".",
            ".."
        ):

            raise HTTPException(
                400,
                "Ruta no válida"
            )

    return Path(
        *pure.parts
    )


def safe_user_path(
    root,
    relative,
    must_exist=False
):

    rel = relative_path(
        relative
    )

    root_resolved = (
        root.resolve()
    )

    target = (
        root /
        rel
    ).resolve()

    if (
        target != root_resolved
        and root_resolved
        not in target.parents
    ):

        raise HTTPException(
            400,
            "Ruta no permitida"
        )

    if (
        must_exist
        and not target.exists()
    ):

        raise HTTPException(
            404,
            "Carpeta no encontrada"
        )

    return target


def validate_folder_name(name):

    name = (
        name or ""
    ).strip()

    if (
        not name
        or name in (
            ".",
            ".."
        )
    ):

        raise HTTPException(
            400,
            "Nombre de carpeta no válido"
        )

    if re.search(
        r'[\\/:*?"<>|\x00-\x1f]',
        name
    ):

        raise HTTPException(
            400,
            "El nombre contiene caracteres no permitidos"
        )

    return name[:100]


# ============================================================
# NOMBRE DE DOCUMENTO
# ============================================================

def sanitize_filename(name):

    if name:
        name = name.strip()

    if not name:

        name = datetime.now().strftime(
            "%d-%m-%Y_%H-%M"
        )

    if name.lower().endswith(
        ".pdf"
    ):
        name = name[:-4]

    name = re.sub(
        r'[\\/:*?"<>|]+',
        "-",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    )

    name = (
        name
        .strip()
        .strip(".")
    )

    if not name:

        name = datetime.now().strftime(
            "%d-%m-%Y_%H-%M"
        )

    return name[:150]


def unique_destination(
    directory,
    name
):

    destination = (
        directory /
        f"{name}.pdf"
    )

    number = 2

    while destination.exists():

        destination = (
            directory /
            f"{name}_{number}.pdf"
        )

        number += 1

    return destination


# ============================================================
# ESTADO ESCÁNER
# ============================================================

lock = threading.Lock()

current_session = None


def initial_status():

    return {
        "owner_id": None,

        "running": False,

        "phase": "ready",

        "message":
            "Preparado para escanear",

        "phase_progress": 0,

        "indeterminate": False,

        "current_page": None,

        "pages": 0,

        "mode": None,

        "dpi": None,

        "ocr": None,

        "filename": None,

        "folder": None,

        "last_file": None,

        "eta_seconds": None,
    }


status = initial_status()


def update_status(**kwargs):

    with lock:
        status.update(
            kwargs
        )


def count_pages(directory):

    return len(
        list(
            directory.glob(
                "pagina-*.png"
            )
        )
    )


def require_owned_session(user):

    if not current_session:

        raise HTTPException(
            409,
            "No existe una sesión activa"
        )

    if (
        current_session["owner_id"]
        != user["id"]
    ):

        raise HTTPException(
            403,
            "El escaneo pertenece a otro usuario"
        )

    return current_session


# ============================================================
# MODELOS API
# ============================================================

class LoginRequest(BaseModel):

    username: str
    password: str


class ScanRequest(BaseModel):

    name: str | None = None

    folder: str = "Documentos"

    mode: Literal[
        "Gray",
        "Color"
    ] = "Gray"

    dpi: Literal[
        200,
        300,
        600
    ] = 300

    ocr: bool = True


class FolderCreateRequest(BaseModel):

    parent: str = ""
    name: str


class UserCreateRequest(BaseModel):

    username: str
    display_name: str
    password: str
    is_admin: bool = False


class PasswordRequest(BaseModel):

    password: str


class EnabledRequest(BaseModel):

    enabled: bool


# ============================================================
# ESCANEO
# ============================================================

def scan_worker():

    global current_session

    session = current_session

    if not session:
        return

    directory = session["session_dir"]

    old_pages = count_pages(
        directory
    )

    start_page = (
        old_pages + 1
    )

    update_status(
        running=True,
        phase="scanning",
        message=(
            f"Escaneando página "
            f"{start_page}"
        ),
        phase_progress=0,
        indeterminate=False,
        current_page=start_page,
        eta_seconds=None,
    )

    command = [
        str(SCAN_SCRIPT),
        str(directory),
        str(start_page),
        session["mode"],
        str(session["dpi"]),
    ]

    logs = deque(
        maxlen=30
    )

    current_page = (
        start_page
    )

    try:

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert (
            process.stdout
            is not None
        )

        for raw_line in process.stdout:

            line = (
                raw_line.strip()
            )

            if not line:
                continue

            logs.append(
                line
            )

            page_match = re.search(
                r"Scanning\s+page\s+(\d+)",
                line,
                re.IGNORECASE,
            )

            if page_match:

                raw_page = int(
                    page_match.group(1)
                )

                if (
                    start_page > 1
                    and raw_page < start_page
                ):

                    current_page = (
                        start_page
                        + raw_page
                        - 1
                    )

                else:

                    current_page = (
                        raw_page
                    )

                update_status(
                    current_page=current_page,
                    message=(
                        f"Escaneando página "
                        f"{current_page}"
                    ),
                    phase_progress=0,
                )

                continue

            progress_match = re.search(
                r"Progress:\s*([0-9.]+)%",
                line,
                re.IGNORECASE,
            )

            if progress_match:

                percent = float(
                    progress_match.group(1)
                )

                update_status(
                    phase_progress=round(
                        percent,
                        1
                    ),
                    message=(
                        f"Escaneando página "
                        f"{current_page} · "
                        f"{percent:.0f}%"
                    ),
                )

        process.wait()

        process_rc = process.returncode

        new_total = count_pages(
            directory
        )

        added = (
            new_total
            - old_pages
        )

        # El script comunica el resultado REAL mediante:
        # BATCHDONE|total|rc
        #
        # scan_batch.sh termina siempre con exit 0 para que podamos
        # procesar correctamente el resultado y distinguir:
        #   - páginas escaneadas
        #   - ADF vacío
        #   - error técnico real
        batch_rc = None
        batch_total = None

        for log_line in logs:

            match = re.fullmatch(
                r"BATCHDONE\|(\d+)\|(-?\d+)",
                log_line,
            )

            if match:

                batch_total = int(
                    match.group(1)
                )

                batch_rc = int(
                    match.group(2)
                )

        output_text = "\n".join(
            logs
        )

        output_lower = (
            output_text.lower()
        )

        feeder_empty = any(
            text in output_lower
            for text in (
                "out of documents",
                "no documents",
                "document feeder empty",
                "feeder empty",
                "adf empty",
                "no paper",
                "no pages",
            )
        )

        print(
            "SCAN_DEBUG "
            f"mode={session['mode']} "
            f"dpi={session['dpi']} "
            f"start={start_page} "
            f"process_rc={process_rc} "
            f"batch_rc={batch_rc} "
            f"batch_total={batch_total} "
            f"old_pages={old_pages} "
            f"new_total={new_total} "
            f"added={added} "
            f"logs={list(logs)!r}",
            flush=True,
        )

        useful_logs = [
            line
            for line in logs
            if not line.startswith("SCANSTATE|")
            and not line.startswith("BATCHDONE|")
            and "Progress:" not in line
            and line.strip()
        ]

        detail = (
            useful_logs[-1]
            if useful_logs
            else (
                f"scanimage rc="
                f"{batch_rc if batch_rc is not None else process_rc}"
            )
        )

        error_detected = (
            batch_rc not in (None, 0)
            or process_rc not in (None, 0)
        )

        jam_detected = any(
            text in output_lower
            for text in (
                "document feeder jammed",
                "feeder jammed",
                "paper jam",
                "adf jam",
                "jammed",
                "paper jammed",
            )
        )

        feeder_problem = any(
            text in output_lower
            for text in (
                "cover open",
                "feeder cover",
                "document feeder",
                "error during device i/o",
                "invalid argument",
                "device busy",
                "i/o error",
            )
        )

        #
        # IMPORTANTE:
        # Todos los problemas durante el escaneo dejan la sesión
        # abierta en waiting_more.
        #
        # De esta forma el usuario puede corregir un atasco,
        # recolocar las hojas o esperar a que el escáner vuelva
        # a estar disponible y continuar con /api/session/add.
        #

        if added > 0:

            if error_detected:

                if jam_detected:
                    warning = (
                        " Se detectó un atasco después de estas páginas. "
                        f"Error real: {detail}. "
                        "Corrige el atasco y pulsa "
                        "«He añadido más hojas» para continuar."
                    )

                elif feeder_problem:
                    warning = (
                        " El alimentador informó de un problema. "
                        f"Error real: {detail}. "
                        "Corrige el problema y pulsa "
                        "«He añadido más hojas» para continuar."
                    )

                else:
                    warning = (
                        " El escáner devolvió un error al terminar el lote. "
                        f"Error real: {detail}. "
                        "Puedes corregirlo y continuar."
                    )

            else:
                warning = ""

            message = (
                f"{added} página"
                f"{'s' if added != 1 else ''} "
                f"añadida"
                f"{'s' if added != 1 else ''}. "
                f"Total: {new_total}."
                f"{warning}"
            )

            update_status(
                running=False,
                phase="waiting_more",
                message=message,
                phase_progress=100,
                indeterminate=False,
                pages=new_total,
                current_page=None,
            )

        elif feeder_empty:

            if new_total:

                message = (
                    "No se han detectado más hojas. "
                    f"El documento conserva {new_total} páginas. "
                    "Puedes añadir más hojas o finalizarlo."
                )

            else:

                message = (
                    "No se han detectado hojas en el alimentador. "
                    "Coloca las hojas y pulsa "
                    "«He añadido más hojas» para reintentar."
                )

            update_status(
                running=False,
                phase="waiting_more",
                message=message,
                phase_progress=(
                    100 if new_total else 0
                ),
                indeterminate=False,
                pages=new_total,
                current_page=None,
            )

        elif error_detected:

            if jam_detected:

                title = "Atasco detectado"

            elif feeder_problem:

                title = "Problema del alimentador"

            else:

                title = "Error del escáner"

            message = (
                f"⚠ {title}: {detail}. "
                "La sesión NO se ha cerrado. "
                "Corrige el problema y pulsa "
                "«He añadido más hojas» para continuar."
            )

            update_status(
                running=False,
                phase="waiting_more",
                message=message,
                phase_progress=(
                    100 if new_total else 0
                ),
                indeterminate=False,
                pages=new_total,
                current_page=None,
            )

        else:

            message = (
                "El escáner no ha generado ninguna página. "
                "La sesión continúa abierta. "
                "Revisa el alimentador y pulsa "
                "«He añadido más hojas» para reintentar."
            )

            update_status(
                running=False,
                phase="waiting_more",
                message=message,
                phase_progress=(
                    100 if new_total else 0
                ),
                indeterminate=False,
                pages=new_total,
                current_page=None,
            )

    except Exception as exc:

        update_status(
            running=False,
            phase="error",
            message=str(exc),
            indeterminate=False,
        )


def friendly_ocr_phase(desc):

    text = (
        desc or ""
    ).lower()

    if "ocr" in text:
        return "Reconociendo texto"

    if (
        "raster" in text
        or "image" in text
    ):
        return "Preparando páginas"

    if (
        "pdf/a" in text
        or "pdfa" in text
    ):
        return "Creando PDF/A"

    if "optimi" in text:
        return "Optimizando PDF"

    if desc:
        return desc

    return "Procesando OCR"


def finalize_worker():

    global current_session

    session = current_session

    if not session:
        return

    directory = (
        session["session_dir"]
    )

    destination = (
        session["destination"]
    )

    pages = count_pages(
        directory
    )

    update_status(
        running=True,
        phase="pdf",
        message=(
            f"Generando PDF de "
            f"{pages} páginas"
        ),
        phase_progress=0,
        indeterminate=True,
        eta_seconds=None,
    )

    command = [
        str(FINALIZE_SCRIPT),
        str(directory),
        str(destination),
        (
            "true"
            if session["ocr"]
            else "false"
        ),
    ]

    step_start = None
    step_desc = None

    try:

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert (
            process.stdout
            is not None
        )

        for raw_line in process.stdout:

            line = (
                raw_line.strip()
            )

            if not line:
                continue

            if line.startswith(
                "SCANSTATE|"
            ):

                parts = line.split(
                    "|",
                    4
                )

                if len(parts) < 4:
                    continue

                phase = parts[2]
                message = parts[3]

                if phase == "ocr":

                    step_start = (
                        time.time()
                    )

                    step_desc = None

                    update_status(
                        phase="ocr",
                        message=message,
                        phase_progress=0,
                        indeterminate=False,
                        eta_seconds=None,
                    )

                elif phase == "pdf":

                    update_status(
                        phase="pdf",
                        message=message,
                        phase_progress=0,
                        indeterminate=True,
                    )

                elif phase == "saving":

                    update_status(
                        phase="saving",
                        message=message,
                        phase_progress=95,
                        indeterminate=True,
                    )

                continue

            if line.startswith(
                "OCRPROGRESS|"
            ):

                parts = line.split(
                    "|",
                    5
                )

                if len(parts) < 5:
                    continue

                percent = float(
                    parts[1] or 0
                )

                desc = parts[2]

                now = time.time()

                if desc != step_desc:

                    step_desc = desc
                    step_start = now

                eta = None

                if (
                    step_start
                    and percent > 3
                    and percent < 100
                ):

                    elapsed = (
                        now
                        - step_start
                    )

                    eta = int(
                        elapsed
                        * (
                            100
                            - percent
                        )
                        / percent
                    )

                update_status(
                    phase="ocr",
                    message=(
                        friendly_ocr_phase(
                            desc
                        )
                    ),
                    phase_progress=round(
                        percent,
                        1
                    ),
                    indeterminate=False,
                    eta_seconds=eta,
                )

        rc = process.wait()

        if rc != 0:

            raise RuntimeError(
                "Error generando el PDF"
            )

        shutil.chown(
            destination,
            user=session["username"],
            group=session["username"],
        )

        os.chmod(
            destination,
            0o660
        )

        shutil.rmtree(
            directory,
            ignore_errors=True
        )

        update_status(
            running=False,
            phase="finished",
            message="Documento disponible",
            phase_progress=100,
            indeterminate=False,
            eta_seconds=0,
            last_file=destination.name,
            filename=destination.name,
        )

        current_session = None

    except Exception as exc:

        update_status(
            running=False,
            phase="error",
            message=str(exc),
            indeterminate=False,
            eta_seconds=None,
        )


# ============================================================
# AUTENTICACIÓN
# ============================================================

@app.post("/api/login")
def login(
    request: Request,
    data: LoginRequest
):

    user = user_by_username(
        data.username
    )

    if (
        not user
        or not user["enabled"]
    ):

        raise HTTPException(
            401,
            "Usuario o contraseña incorrectos"
        )

    try:

        PASSWORD_HASHER.verify(
            user["password_hash"],
            data.password
        )

    except VerifyMismatchError:

        raise HTTPException(
            401,
            "Usuario o contraseña incorrectos"
        )

    request.session.clear()

    request.session[
        "user_id"
    ] = user["id"]

    return {
        "ok": True,
        "user": public_user(
            user
        )
    }


@app.post("/api/logout")
def logout(
    request: Request
):

    request.session.clear()

    return {
        "ok": True
    }


@app.get("/api/me")
def me(
    request: Request
):

    user = require_user(
        request
    )

    return public_user(
        user
    )


# ============================================================
# CARPETAS
# ============================================================

@app.get("/api/folders")
def folders(
    request: Request
):

    user = require_user(
        request
    )

    root = user_root(
        user
    )

    result = [
        {
            "value": "",
            "label": "Inicio"
        }
    ]

    directories = sorted(
        [
            path
            for path
            in root.rglob("*")
            if path.is_dir()
        ],
        key=lambda p:
            str(p).lower()
    )

    for directory in directories:

        relative = (
            directory
            .relative_to(root)
            .as_posix()
        )

        result.append(
            {
                "value": relative,
                "label": relative
            }
        )

    return result


@app.post("/api/folders")
def create_folder(
    request: Request,
    data: FolderCreateRequest
):

    user = require_user(
        request
    )

    root = user_root(
        user
    )

    parent = safe_user_path(
        root,
        data.parent,
        must_exist=True
    )

    name = validate_folder_name(
        data.name
    )

    target = (
        parent /
        name
    ).resolve()

    root_resolved = (
        root.resolve()
    )

    if (
        target != root_resolved
        and root_resolved
        not in target.parents
    ):

        raise HTTPException(
            400,
            "Ruta no permitida"
        )

    if target.exists():

        raise HTTPException(
            409,
            "La carpeta ya existe"
        )

    target.mkdir()

    shutil.chown(
        target,
        user=user["username"],
        group=user["username"],
    )

    os.chmod(
        target,
        0o770
    )

    relative = (
        target
        .relative_to(root)
        .as_posix()
    )

    return {
        "ok": True,
        "folder": relative
    }


# ============================================================
# ESTADO
# ============================================================

@app.get("/api/status")
def get_status(
    request: Request
):

    user = require_user(
        request
    )

    with lock:

        snapshot = dict(
            status
        )

    owner_id = snapshot.get(
        "owner_id"
    )

    active_phases = {
        "starting",
        "scanning",
        "waiting_more",
        "pdf",
        "ocr",
        "saving",
    }

    if (
        owner_id
        and owner_id != user["id"]
    ):

        if (
            snapshot["phase"]
            in active_phases
        ):

            return {
                "running": True,
                "phase": "busy",
                "message":
                    "El escáner está siendo utilizado por otro usuario",
                "phase_progress": 0,
                "indeterminate": True,
                "current_page": None,
                "pages": 0,
                "filename": None,
                "folder": None,
                "last_file": None,
                "eta_seconds": None,
                "owned": False,
            }

        clean = initial_status()

        clean["owned"] = False

        return clean

    snapshot["owned"] = True

    return snapshot


# ============================================================
# SESIONES DE ESCANEO
# ============================================================

@app.post("/api/session/start")
def start_session(
    request: Request,
    data: ScanRequest
):

    global current_session

    user = require_user(
        request
    )

    with lock:

        if status["running"]:

            raise HTTPException(
                409,
                "El escáner está ocupado"
            )

        if (
            status["phase"]
            == "waiting_more"
        ):

            raise HTTPException(
                409,
                "Hay un documento pendiente de finalizar"
            )

    root = user_root(
        user
    )

    destination_folder = (
        safe_user_path(
            root,
            data.folder,
            must_exist=True
        )
    )

    if not destination_folder.is_dir():

        raise HTTPException(
            400,
            "El destino no es una carpeta"
        )

    name = sanitize_filename(
        data.name
    )

    destination = (
        unique_destination(
            destination_folder,
            name
        )
    )

    session_id = (
        uuid.uuid4().hex
    )

    session_directory = (
        SESSIONS_ROOT /
        session_id
    )

    session_directory.mkdir(
        parents=True
    )

    current_session = {
        "id": session_id,

        "owner_id":
            user["id"],

        "username":
            user["username"],

        "session_dir":
            session_directory,

        "destination":
            destination,

        "folder":
            data.folder,

        "mode":
            data.mode,

        "dpi":
            data.dpi,

        "ocr":
            data.ocr,
    }

    update_status(
        owner_id=user["id"],
        running=True,
        phase="starting",
        message="Iniciando escaneo",
        phase_progress=0,
        indeterminate=True,
        pages=0,
        current_page=None,
        filename=destination.name,
        folder=data.folder,
        last_file=None,
        mode=data.mode,
        dpi=data.dpi,
        ocr=data.ocr,
        eta_seconds=None,
    )

    threading.Thread(
        target=scan_worker,
        daemon=True,
    ).start()

    return {
        "ok": True,
        "filename":
            destination.name
    }


@app.post("/api/session/add")
def add_pages(
    request: Request
):

    user = require_user(
        request
    )

    require_owned_session(
        user
    )

    with lock:

        if status["running"]:

            raise HTTPException(
                409,
                "Hay un proceso en curso"
            )

        if (
            status["phase"]
            != "waiting_more"
        ):

            raise HTTPException(
                409,
                "No se pueden añadir hojas ahora"
            )

        status.update(
            {
                "running": True,
                "phase": "starting",
                "message":
                    "Preparando el siguiente lote",
                "phase_progress": 0,
                "indeterminate": True,
                "eta_seconds": None,
            }
        )

    threading.Thread(
        target=scan_worker,
        daemon=True,
    ).start()

    return {
        "ok": True
    }



# === DUPLEX MANUAL V1 ===

@app.post("/api/session/duplex/enable")
def duplex_enable(request: Request):

    user = require_user(request)
    session = require_owned_session(user)

    directory = session["session_dir"]

    (directory / ".duplex_enabled").write_text(
        "1\n"
    )

    # Si se reactiva antes de pasar a caras pares,
    # seguimos en la primera pasada.
    if not (directory / ".duplex_split").exists():

        session["duplex_side"] = "odd"

        update_status(
            duplex=True,
            duplex_side="odd",
        )

    return {
        "ok": True,
        "duplex": True,
        "side": session.get(
            "duplex_side",
            "odd"
        ),
    }


@app.get("/api/session/duplex/info")
def duplex_info(request: Request):

    user = require_user(request)

    session = current_session

    if (
        not session
        or session.get("owner_id") != user["id"]
    ):
        return {
            "enabled": False,
            "running": False,
        }

    directory = session["session_dir"]

    enabled = (
        directory / ".duplex_enabled"
    ).exists()

    if not enabled:
        return {
            "enabled": False,
            "running": status["running"],
        }

    total = count_pages(directory)

    split_file = (
        directory / ".duplex_split"
    )

    if split_file.exists():

        try:
            odd_pages = int(
                split_file
                .read_text()
                .strip()
            )
        except Exception:
            odd_pages = 0

        even_pages = max(
            0,
            total - odd_pages
        )

        side = "even"

    else:

        odd_pages = total
        even_pages = 0
        side = "odd"

    reverse_file = (
        directory /
        ".duplex_reverse_even"
    )

    reverse_even = True

    if reverse_file.exists():
        reverse_even = (
            reverse_file
            .read_text()
            .strip()
            != "0"
        )

    return {
        "enabled": True,
        "side": side,
        "odd_pages": odd_pages,
        "even_pages": even_pages,
        "total_raw": total,
        "running": status["running"],
        "phase": status["phase"],
        "reverse_even": reverse_even,
        "ready_to_finalize": (
            side == "even"
            and odd_pages > 0
            and even_pages in (
                odd_pages,
                odd_pages - 1,
            )
            and not status["running"]
        ),
        "last_page_single_sided": (
            odd_pages == even_pages + 1
        ),
    }


@app.post("/api/session/duplex/even")
def duplex_start_even(
    request: Request,
):

    user = require_user(request)
    session = require_owned_session(user)

    directory = session["session_dir"]

    if not (
        directory /
        ".duplex_enabled"
    ).exists():

        raise HTTPException(
            409,
            "Esta sesión no está en modo doble cara"
        )

    with lock:

        if status["running"]:

            raise HTTPException(
                409,
                "Hay un escaneo en curso"
            )

        if status["phase"] != "waiting_more":

            raise HTTPException(
                409,
                "Todavía no se puede iniciar la segunda cara"
            )

    split_file = (
        directory /
        ".duplex_split"
    )

    if split_file.exists():

        raise HTTPException(
            409,
            "Ya estás escaneando las caras pares"
        )

    odd_pages = count_pages(
        directory
    )

    if odd_pages <= 0:

        raise HTTPException(
            409,
            "Todavía no se ha escaneado ninguna cara impar"
        )

    split_file.write_text(
        f"{odd_pages}\n"
    )

    (
        directory /
        ".duplex_reverse_even"
    ).write_text(
        "1\n"
    )

    session["duplex_side"] = "even"

    update_status(
        running=True,
        phase="starting",
        message=(
            "Preparando escaneo de caras pares"
        ),
        phase_progress=0,
        indeterminate=True,
        duplex=True,
        duplex_side="even",
        eta_seconds=None,
    )

    # Al pulsar "Pasar a caras pares"
    # empieza directamente la segunda pasada.
    threading.Thread(
        target=scan_worker,
        daemon=True,
    ).start()

    return {
        "ok": True,
        "side": "even",
        "odd_pages": odd_pages,
        "reverse_even": True,
    }



@app.post("/api/session/finalize")
def finalize_session(
    request: Request
):

    user = require_user(
        request
    )

    session = (
        require_owned_session(
            user
        )
    )

    pages = count_pages(
        session["session_dir"]
    )

    duplex_enabled_file = (
        session["session_dir"] /
        ".duplex_enabled"
    )

    duplex_split_file = (
        session["session_dir"] /
        ".duplex_split"
    )

    if duplex_enabled_file.exists():

        if not duplex_split_file.exists():

            raise HTTPException(
                409,
                "Escaneo a doble cara: "
                "todavía faltan las caras pares"
            )

        try:
            odd_pages = int(
                duplex_split_file
                .read_text()
                .strip()
            )
        except Exception:

            raise HTTPException(
                500,
                "No se puede leer el estado "
                "del escaneo a doble cara"
            )

        even_pages = (
            pages - odd_pages
        )

        if even_pages not in (
            odd_pages,
            odd_pages - 1,
        ):

            raise HTTPException(
                409,
                "Dúplex incompleto: "
                f"{odd_pages} caras impares y "
                f"{even_pages} caras pares. "
                "Solo se permite una cara impar adicional "
                "cuando la última hoja no tiene reverso."
            )


    if pages == 0:

        raise HTTPException(
            409,
            "El documento todavía no contiene páginas"
        )

    with lock:

        if status["running"]:

            raise HTTPException(
                409,
                "Hay un proceso en curso"
            )

        if status["phase"] not in (
            "waiting_more",
            "error",
        ):

            raise HTTPException(
                409,
                "El documento no puede finalizarse ahora"
            )

        status.update(
            {
                "running": True,
                "phase": "pdf",
                "message":
                    f"Generando PDF de {pages} páginas",
                "phase_progress": 0,
                "indeterminate": True,
                "eta_seconds": None,
            }
        )

    threading.Thread(
        target=finalize_worker,
        daemon=True,
    ).start()

    return {
        "ok": True
    }


@app.post("/api/session/cancel")
def cancel_session(
    request: Request
):

    global current_session
    global status

    user = require_user(
        request
    )

    session = (
        require_owned_session(
            user
        )
    )

    with lock:

        if status["running"]:

            raise HTTPException(
                409,
                "No se puede cancelar mientras se está procesando"
            )

    shutil.rmtree(
        session["session_dir"],
        ignore_errors=True
    )

    current_session = None

    with lock:
        status = initial_status()

    return {
        "ok": True
    }


# ============================================================
# DOCUMENTOS
# ============================================================

@app.get("/api/documents")
def documents(
    request: Request
):

    user = require_user(
        request
    )

    root = user_root(
        user
    )

    pdfs = sorted(
        root.rglob("*.pdf"),
        key=lambda p:
            p.stat().st_mtime,
        reverse=True,
    )

    result = []

    for pdf in pdfs[:100]:

        stat = pdf.stat()

        relative = (
            pdf
            .relative_to(root)
        )

        folder = (
            relative.parent
            .as_posix()
        )

        if folder == ".":
            folder = "Inicio"

        result.append(
            {
                "name":
                    pdf.name,

                "folder":
                    folder,

                "size":
                    round(
                        stat.st_size
                        / 1024
                        / 1024,
                        2
                    ),

                "timestamp":
                    stat.st_mtime,

                "url":
                    "/documents/"
                    + quote(
                        relative.as_posix(),
                        safe="/"
                    ),
            }
        )

    return result


@app.get(
    "/documents/{file_path:path}"
)
def download_document(
    file_path: str,
    request: Request
):

    user = require_user(
        request
    )

    root = user_root(
        user
    )

    file = safe_user_path(
        root,
        file_path,
        must_exist=True
    )

    if (
        not file.is_file()
        or file.suffix.lower()
        != ".pdf"
    ):

        raise HTTPException(
            404,
            "Documento no encontrado"
        )

    return FileResponse(
        file,
        media_type="application/pdf",
        filename=file.name,
    )


# ============================================================
# ADMINISTRACIÓN
# ============================================================

@app.get("/api/admin/users")
def admin_users(
    request: Request
):

    require_admin(
        request
    )

    with db_connection() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM users
            ORDER BY username
            """
        ).fetchall()

    return [
        public_user(row)
        for row in rows
    ]


@app.post("/api/admin/users")
def admin_create_user(
    request: Request,
    data: UserCreateRequest
):

    require_admin(
        request
    )

    username = validate_username(
        data.username
    )

    display_name = (
        data.display_name
        or username
    ).strip()

    if len(data.password) < 12:

        raise HTTPException(
            400,
            "La contraseña debe tener al menos 12 caracteres"
        )

    smb_account(
        "create",
        username,
        data.password,
    )

    password_hash = (
        PASSWORD_HASHER.hash(
            data.password
        )
    )

    try:

        with db_connection() as conn:

            cursor = conn.execute(
                """
                INSERT INTO users (
                    username,
                    display_name,
                    password_hash,
                    is_admin,
                    enabled,
                    created_at
                )
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (
                    username,
                    display_name,
                    password_hash,
                    1 if data.is_admin else 0,
                    datetime.now().isoformat(),
                )
            )

            user_id = (
                cursor.lastrowid
            )

            conn.commit()

    except sqlite3.IntegrityError:

        raise HTTPException(
            409,
            "El usuario ya existe"
        )

    create_user_storage(
        username
    )

    user = user_by_id(
        user_id
    )

    return {
        "ok": True,
        "user":
            public_user(user)
    }


@app.post(
    "/api/admin/users/{user_id}/password"
)
def admin_change_password(
    user_id: int,
    request: Request,
    data: PasswordRequest
):

    require_admin(
        request
    )

    if len(data.password) < 12:

        raise HTTPException(
            400,
            "La contraseña debe tener al menos 12 caracteres"
        )

    user = user_by_id(
        user_id
    )

    if not user:

        raise HTTPException(
            404,
            "Usuario no encontrado"
        )

    smb_account(
        "password",
        user["username"],
        data.password,
    )

    password_hash = (
        PASSWORD_HASHER.hash(
            data.password
        )
    )

    with db_connection() as conn:

        conn.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
            """,
            (
                password_hash,
                user_id
            )
        )

        conn.commit()

    return {
        "ok": True
    }


@app.post(
    "/api/admin/users/{user_id}/enabled"
)
def admin_enable_user(
    user_id: int,
    request: Request,
    data: EnabledRequest
):

    admin = require_admin(
        request
    )

    if (
        admin["id"]
        == user_id
        and not data.enabled
    ):

        raise HTTPException(
            400,
            "No puedes desactivar tu propio usuario"
        )

    user = user_by_id(
        user_id
    )

    if not user:

        raise HTTPException(
            404,
            "Usuario no encontrado"
        )

    if data.enabled:

        smb_account(
            "enable",
            user["username"],
        )

    else:

        smb_account(
            "disable",
            user["username"],
        )

    with db_connection() as conn:

        conn.execute(
            """
            UPDATE users
            SET enabled = ?
            WHERE id = ?
            """,
            (
                1
                if data.enabled
                else 0,
                user_id,
            )
        )

        conn.commit()

    return {
        "ok": True
    }


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
def index():

    return FileResponse(
        STATIC / "index.html",
        headers={
            "Cache-Control":
                "no-store"
        }
    )


app.mount(
    "/static",
    StaticFiles(
        directory=STATIC
    ),
    name="static",
)
