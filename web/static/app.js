let currentUser = null;

let previousPhase = null;


function escapeHtml(value) {

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function pad(value) {

    return String(value)
        .padStart(2, "0");
}


function filenamePlaceholder() {

    const now = new Date();

    return (
        `${pad(now.getDate())}-` +
        `${pad(now.getMonth() + 1)}-` +
        `${now.getFullYear()}_` +
        `${pad(now.getHours())}-` +
        `${pad(now.getMinutes())}`
    );
}


function setFilenamePlaceholder() {

    document
        .getElementById("documentName")
        .placeholder =
            `Ej. ${filenamePlaceholder()}`;
}


async function api(
    url,
    options={}
) {

    const response =
        await fetch(
            url,
            {
                cache: "no-store",
                ...options
            }
        );

    if (response.status === 401) {

        showLogin();

        throw new Error(
            "No autenticado"
        );
    }

    return response;
}


function showLogin() {

    currentUser = null;

    document
        .getElementById("loginView")
        .classList.remove("hidden");

    document
        .getElementById("appView")
        .classList.add("hidden");
}


async function showApp(user) {

    currentUser = user;

    document
        .getElementById("loginView")
        .classList.add("hidden");

    document
        .getElementById("appView")
        .classList.remove("hidden");

    document
        .getElementById("currentUser")
        .textContent =
            user.display_name;

    if (user.is_admin) {

        document
            .getElementById("adminCard")
            .classList.remove("hidden");

        loadUsers();

    } else {

        document
            .getElementById("adminCard")
            .classList.add("hidden");
    }

    setFilenamePlaceholder();

    await loadFolders();

    await loadDocuments();

    await updateStatus();
}


async function checkSession() {

    const response =
        await fetch(
            "/api/me",
            {
                cache: "no-store"
            }
        );

    if (!response.ok) {

        showLogin();

        return;
    }

    const user =
        await response.json();

    showApp(user);
}


async function login() {

    const username =
        document
        .getElementById("loginUsername")
        .value;

    const password =
        document
        .getElementById("loginPassword")
        .value;

    const response =
        await fetch(
            "/api/login",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    username,
                    password
                })
            }
        );

    if (!response.ok) {

        const data =
            await response.json();

        document
            .getElementById("loginError")
            .textContent =
                data.detail
                ||
                "No se pudo iniciar sesión";

        return;
    }

    const data =
        await response.json();

    document
        .getElementById("loginPassword")
        .value = "";

    document
        .getElementById("loginError")
        .textContent = "";

    showApp(
        data.user
    );
}


async function logout() {

    await fetch(
        "/api/logout",
        {
            method: "POST"
        }
    );

    showLogin();
}


async function loadFolders(
    selected=null
) {

    const response =
        await api(
            "/api/folders"
        );

    const folders =
        await response.json();

    const destination =
        document
        .getElementById("folder");

    const parent =
        document
        .getElementById("folderParent");

    destination.innerHTML = "";
    parent.innerHTML = "";

    folders.forEach(
        item => {

            const option1 =
                document
                .createElement("option");

            option1.value =
                item.value;

            option1.textContent =
                "📁 " +
                item.label;

            destination.appendChild(
                option1
            );

            const option2 =
                document
                .createElement("option");

            option2.value =
                item.value;

            option2.textContent =
                "📁 " +
                item.label;

            parent.appendChild(
                option2
            );
        }
    );

    if (
        selected !== null
    ) {

        destination.value =
            selected;

    } else if (
        folders.some(
            f =>
                f.value ===
                "Documentos"
        )
    ) {

        destination.value =
            "Documentos";
    }
}


async function createFolder() {

    const parent =
        document
        .getElementById(
            "folderParent"
        ).value;

    const name =
        document
        .getElementById(
            "newFolderName"
        ).value.trim();

    if (!name) {

        alert(
            "Introduce un nombre de carpeta"
        );

        return;
    }

    const response =
        await api(
            "/api/folders",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    parent,
                    name
                })
            }
        );

    if (!response.ok) {

        const data =
            await response.json();

        alert(
            data.detail
        );

        return;
    }

    const data =
        await response.json();

    document
        .getElementById(
            "newFolderName"
        )
        .value = "";

    await loadFolders(
        data.folder
    );
}


async function startScan() {

    const body = {

        name:
            document
            .getElementById(
                "documentName"
            ).value,

        folder:
            document
            .getElementById(
                "folder"
            ).value,

        mode:
            document
            .getElementById(
                "mode"
            ).value,

        dpi:
            Number(
                document
                .getElementById(
                    "dpi"
                ).value
            ),

        ocr:
            document
            .getElementById(
                "ocr"
            ).checked,

        // El servidor registra el modo dúplex antes de iniciar el ADF.
        duplex:
            document.getElementById("duplex-enabled")?.checked === true
    };

    const response =
        await api(
            "/api/session/start",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(
                        body
                    )
            }
        );

    if (!response.ok) {

        const data =
            await response.json();

        alert(
            data.detail
        );

        return;
    }

    updateStatus();
}


async function addPages() {

    const response =
        await api(
            "/api/session/add",
            {
                method: "POST"
            }
        );

    if (!response.ok) {

        const data =
            await response.json();

        alert(
            data.detail
        );
    }

    updateStatus();
}


async function finalizeDocument() {

    const response =
        await api(
            "/api/session/finalize",
            {
                method: "POST"
            }
        );

    if (!response.ok) {

        const data =
            await response.json();

        alert(
            data.detail
        );
    }

    updateStatus();
}


async function cancelDocument() {

    if (
        !confirm(
            "¿Cancelar este documento? " +
            "Las páginas escaneadas se eliminarán."
        )
    ) {
        return;
    }

    const response =
        await api(
            "/api/session/cancel",
            {
                method: "POST"
            }
        );

    if (!response.ok) {

        const data =
            await response.json();

        alert(
            data.detail
        );
    }

    updateStatus();
}


function phaseName(phase) {

    const names = {

        ready:
            "Preparado",

        starting:
            "Preparando escáner",

        scanning:
            "Escaneando",

        waiting_more:
            "Lote terminado",

        pdf:
            "Generando PDF",

        ocr:
            "Procesando OCR",

        saving:
            "Guardando",

        finished:
            "✓ Documento disponible",

        busy:
            "Escáner ocupado",

        error:
            "⚠ Error"
    };

    return (
        names[phase]
        ||
        phase
    );
}


function formatSeconds(seconds) {

    if (!seconds)
        return "";

    if (seconds < 60)
        return `≈ ${seconds} s`;

    return (
        `≈ ${Math.floor(seconds / 60)} min ` +
        `${seconds % 60} s`
    );
}


async function updateStatus() {

    if (!currentUser)
        return;

    try {

        const response =
            await api(
                "/api/status"
            );

        const s =
            await response.json();

        const active = (
            s.running
            ||
            s.phase === "starting"
            ||
            s.phase === "scanning"
            ||
            s.phase === "waiting_more"
            ||
            s.phase === "pdf"
            ||
            s.phase === "ocr"
            ||
            s.phase === "saving"
            ||
            s.phase === "busy"
        );

        /*
         * Si la sesión pertenece al usuario actual,
         * no presentamos visualmente el botón como
         * si pudiera empezar otro documento.
         */
        const mainScanButton =
            document.getElementById(
                "scanButton"
            );

        if (mainScanButton) {

            if (
                active
                &&
                s.owned
            ) {

                if (
                    !mainScanButton.dataset
                        .normalText
                ) {

                    mainScanButton.dataset
                        .normalText =
                            mainScanButton
                                .textContent;
                }

                mainScanButton.textContent =
                    "Documento en curso";

            } else if (
                mainScanButton.dataset
                    .normalText
            ) {

                mainScanButton.textContent =
                    mainScanButton.dataset
                        .normalText;
            }
        }


        [
            "scanButton",
            "documentName",
            "folder",
            "mode",
            "dpi",
            "ocr"
        ].forEach(
            id => {

                document
                    .getElementById(id)
                    .disabled =
                        active;
            }
        );

        document
            .getElementById(
                "statusTitle"
            )
            .textContent =
                phaseName(
                    s.phase
                );

        document
            .getElementById(
                "statusMessage"
            )
            .textContent =
                s.message
                ||
                "";

        document
            .getElementById(
                "statusFile"
            )
            .textContent =
                s.filename
                ?
                `Archivo: ${s.filename}`
                :
                "";

        const bar =
            document
            .getElementById(
                "progressBar"
            );

        if (s.indeterminate) {

            bar.classList.add(
                "indeterminate"
            );

        } else {

            bar.classList.remove(
                "indeterminate"
            );

            bar.style.width =
                `${
                    s.phase_progress
                    ||
                    0
                }%`;
        }

        const progressText =
            document
            .getElementById(
                "progressText"
            );

        if (
            s.phase ===
            "scanning"
        ) {

            progressText.textContent =
                `Página ${
                    s.current_page || 1
                } · ${
                    Math.round(
                        s.phase_progress
                        ||
                        0
                    )
                } %`;

        } else if (
            s.phase ===
            "waiting_more"
        ) {

            progressText.textContent =
                `${s.pages || 0} páginas acumuladas`;

        } else if (
            s.phase ===
            "ocr"
        ) {

            progressText.textContent =
                `OCR · ${
                    Math.round(
                        s.phase_progress
                        ||
                        0
                    )
                } %`;

        } else if (
            s.phase ===
            "finished"
        ) {

            progressText.textContent =
                "100 %";

        } else {

            progressText.textContent =
                s.indeterminate
                ?
                "Procesando…"
                :
                `${
                    Math.round(
                        s.phase_progress
                        ||
                        0
                    )
                } %`;
        }

        document
            .getElementById("eta")
            .textContent =
                formatSeconds(
                    s.eta_seconds
                );

        const continueBox =
            document
            .getElementById(
                "continueBox"
            );

        if (
            s.phase ===
                "waiting_more"
            &&
            s.owned
        ) {

            continueBox.style.display =
                "block";

            const total =
                s.pages || 0;

            document
                .getElementById(
                    "pageTotal"
                )
                .textContent =
                    `${total} página${
                        total === 1
                        ?
                        ""
                        :
                        "s"
                    }`;

            document
                .getElementById(
                    "finishButton"
                )
                .disabled =
                    total === 0;

        } else {

            continueBox.style.display =
                "none";
        }

        if (
            previousPhase !==
                "finished"
            &&
            s.phase ===
                "finished"
        ) {

            loadDocuments();

            document
                .getElementById(
                    "documentName"
                )
                .value = "";

            setFilenamePlaceholder();
        }

        previousPhase =
            s.phase;

    } catch(error) {

        console.error(
            error
        );
    }
}


async function loadDocuments() {

    if (!currentUser)
        return;

    const response =
        await api(
            "/api/documents"
        );

    const docs =
        await response.json();

    const container =
        document
        .getElementById(
            "documents"
        );

    if (!docs.length) {

        container.innerHTML =
            "Todavía no tienes documentos.";

        return;
    }

    container.innerHTML = "";

    docs.forEach(
        doc => {

            const row =
                document
                .createElement(
                    "div"
                );

            row.className =
                "document";

            const date =
                new Date(
                    doc.timestamp
                    *
                    1000
                )
                .toLocaleString();

            row.innerHTML = `

                <div>

                    <div class="document-name">
                        📄 ${escapeHtml(doc.name)}
                    </div>

                    <div class="document-info">
                        📁 ${escapeHtml(doc.folder)}
                        ·
                        ${escapeHtml(date)}
                        ·
                        ${doc.size} MB
                    </div>

                </div>

                <a
                    class="download"
                    href="${doc.url}"
                    target="_blank"
                >
                    Abrir
                </a>
            `;

            container.appendChild(
                row
            );
        }
    );
}


async function loadUsers() {

    if (
        !currentUser
        ||
        !currentUser.is_admin
    ) {
        return;
    }

    const response =
        await api(
            "/api/admin/users"
        );

    const users =
        await response.json();

    const container =
        document
        .getElementById(
            "usersList"
        );

    container.innerHTML = "";

    users.forEach(
        user => {

            const row =
                document
                .createElement(
                    "div"
                );

            row.className =
                "admin-user";

            row.innerHTML = `

                <div>

                    <strong>
                        ${escapeHtml(user.display_name)}
                    </strong>

                    <div class="help">
                        ${escapeHtml(user.username)}
                        ${user.is_admin ? " · Administrador" : ""}
                        ${user.enabled ? "" : " · DESACTIVADO"}
                    </div>

                </div>

                <div class="admin-actions">

                    <button
                        class="secondary"
                        data-action="reset-password" data-user-id="${user.id}"
                    >
                        Cambiar clave
                    </button>

                    <button
                        class="${user.enabled ? "danger" : "success"}"
                        data-action="set-enabled" data-user-id="${user.id}" data-enabled="${user.enabled ? "false" : "true"}"
                    >
                        ${
                            user.enabled
                            ?
                            "Desactivar"
                            :
                            "Activar"
                        }
                    </button>

                </div>
            `;

            container.appendChild(
                row
            );
        }
    );
}


async function createUser() {

    const username =
        document
        .getElementById(
            "adminUsername"
        ).value;

    const display_name =
        document
        .getElementById(
            "adminDisplayName"
        ).value;

    const password =
        document
        .getElementById(
            "adminPassword"
        ).value;

    const is_admin =
        document
        .getElementById(
            "adminIsAdmin"
        ).value === "true";

    const response =
        await api(
            "/api/admin/users",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    username,
                    display_name,
                    password,
                    is_admin
                })
            }
        );

    if (!response.ok) {

        const data =
            await response.json();

        alert(
            data.detail
        );

        return;
    }

    document
        .getElementById(
            "adminUsername"
        ).value = "";

    document
        .getElementById(
            "adminDisplayName"
        ).value = "";

    document
        .getElementById(
            "adminPassword"
        ).value = "";

    loadUsers();
}


async function resetPassword(
    userId
) {

    const password =
        prompt(
            "Nueva contraseña (mínimo 12 caracteres):"
        );

    if (!password)
        return;

    const response =
        await api(
            `/api/admin/users/${userId}/password`,
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    password
                })
            }
        );

    if (!response.ok) {

        const data =
            await response.json();

        alert(
            data.detail
        );

        return;
    }

    alert(
        "Contraseña actualizada"
    );
}


async function setUserEnabled(
    userId,
    enabled
) {

    const response =
        await api(
            `/api/admin/users/${userId}/enabled`,
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    enabled
                })
            }
        );

    if (!response.ok) {

        const data =
            await response.json();

        alert(
            data.detail
        );

        return;
    }

    loadUsers();
}


document
    .getElementById(
        "loginPassword"
    )
    .addEventListener(
        "keydown",
        event => {

            if (
                event.key ===
                "Enter"
            ) {

                login();
            }
        }
    );


setFilenamePlaceholder();

checkSession();


setInterval(
    () => {

        if (currentUser) {
            updateStatus();
        }

    },
    750
);

document
    .getElementById("loginButton")
    ?.addEventListener(
        "click",
        login
    );

document
    .getElementById("logoutButton")
    ?.addEventListener(
        "click",
        logout
    );

document
    .getElementById("createFolderButton")
    ?.addEventListener(
        "click",
        createFolder
    );

document
    .getElementById("scanButton")
    ?.addEventListener(
        "click",
        startScan
    );

document
    .getElementById("addButton")
    ?.addEventListener(
        "click",
        addPages
    );

document
    .getElementById("finishButton")
    ?.addEventListener(
        "click",
        finalizeDocument
    );

document
    .getElementById("cancelButton")
    ?.addEventListener(
        "click",
        cancelDocument
    );

document
    .getElementById("createUserButton")
    ?.addEventListener(
        "click",
        createUser
    );


document
    .getElementById("usersList")
    ?.addEventListener(
        "click",
        event => {

            const button =
                event.target.closest(
                    "button[data-action]"
                );

            if (!button) {
                return;
            }

            const userId =
                Number(
                    button.dataset.userId
                );

            if (
                button.dataset.action
                === "reset-password"
            ) {

                resetPassword(
                    userId
                );

            }

            else if (
                button.dataset.action
                === "set-enabled"
            ) {

                setUserEnabled(
                    userId,
                    button.dataset.enabled
                    === "true"
                );

            }
        }
    );


/* ============================================================
   DUPLEX_MANUAL_V1
   ============================================================ */

(() => {

    const nativeFetch =
        window.fetch.bind(window);

    let duplexInfo = null;


    function findButton(regex) {

        return [
            ...document.querySelectorAll(
                "button"
            )
        ].find(
            button =>
                regex.test(
                    button.textContent || ""
                )
        );
    }


    function createDuplexPanel() {

        if (
            document.getElementById(
                "duplex-panel"
            )
        ) {
            return;
        }

        const panel =
            document.createElement("div");

        panel.id = "duplex-panel";

        panel.style.cssText = `
            margin: 14px 0;
            padding: 0;
            border: 0;
            background: transparent;
        `;

        panel.innerHTML = `
            <div style="
                display:flex;
                align-items:flex-start;
                gap:12px;
            ">
                <input
                    type="checkbox"
                    id="duplex-enabled"
                    style="
                        margin-top:4px;
                        width:20px;
                        height:20px;
                        flex:0 0 auto;
                    "
                >

                <label
                    for="duplex-enabled"
                    style="
                        cursor:pointer;
                        display:block;
                        line-height:1.25;
                    "
                >
                    <div style="
                        font-weight:700;
                        font-size:1rem;
                    ">
                        Escaneo a doble cara
                    </div>

                    <div style="
                        margin-top:4px;
                        font-size:.82rem;
                        color:#777;
                        font-weight:400;
                    ">
                        Escanea anverso y reverso por lotes.
                    </div>
                </label>
            </div>

            <div
                id="duplex-options"
                style="
                    display:none;
                    margin-top:14px;
                    margin-left:32px;
                    padding:12px 14px;
                    border-radius:10px;
                    background:rgba(120,120,120,.06);
                "
            >
                <label style="
                    display:flex;
                    gap:9px;
                    align-items:flex-start;
                    font-size:.9rem;
                    cursor:pointer;
                ">
                    <input
                        type="checkbox"
                        id="duplex-reverse"
                        checked
                        disabled
                        style="
                            margin-top:2px;
                        "
                    >

                    <span>
                        El orden de las caras pares se invierte
                        automáticamente
                    </span>
                </label>

                <div
                    id="duplex-state"
                    style="
                        margin-top:12px;
                        font-size:.9rem;
                    "
                ></div>

                <button
                    type="button"
                    id="duplex-even-button"
                    style="
                        display:none;
                        margin-top:12px;
                        width:100%;
                    "
                >
                    🔄 Ya he girado el taco · Escanear caras pares
                </button>
            </div>
        `;

        const startButton =
            findButton(
                /escanear|iniciar/i
            );

        if (
            startButton &&
            startButton.parentElement
        ) {

            startButton
                .parentElement
                .insertBefore(
                    panel,
                    startButton
                );

        } else {

            const main =
                document.querySelector(
                    "main"
                );

            (
                main ||
                document.body
            ).prepend(panel);
        }


        const enabled =
            document.getElementById(
                "duplex-enabled"
            );

        const options =
            document.getElementById(
                "duplex-options"
            );

        enabled.addEventListener(
            "change",
            () => {

                options.style.display =
                    enabled.checked
                        ? "block"
                        : "none";
            }
        );


        document
            .getElementById(
                "duplex-even-button"
            )
            .addEventListener(
                "click",
                startEvenPass
            );
    }


    async function startEvenPass() {

        const ok = window.confirm(
            "Gira ahora TODO el taco como un bloque " +
            "y colócalo de nuevo en el alimentador.\n\n" +
            "Al aceptar comenzará inmediatamente " +
            "el escaneo de las caras pares."
        );

        if (!ok) {
            return;
        }

        const response =
            await nativeFetch(
                "/api/session/duplex/even",
                {
                    method: "POST"
                }
            );

        if (!response.ok) {

            let message =
                "No se puede iniciar " +
                "la segunda pasada";

            try {

                const data =
                    await response.json();

                message =
                    data.detail ||
                    message;

            } catch (_) {}

            alert(message);
            return;
        }

        await refreshDuplexInfo();
    }


    async function refreshDuplexInfo() {

        try {

            const response =
                await nativeFetch(
                    "/api/session/duplex/info",
                    {
                        cache: "no-store"
                    }
                );

            if (!response.ok) {
                return;
            }

            duplexInfo =
                await response.json();

            renderDuplexInfo();

        } catch (_) {}
    }


    function renderDuplexInfo() {

        const panel =
            document.getElementById(
                "duplex-panel"
            );

        if (!panel) {
            return;
        }

        const enabled =
            document.getElementById(
                "duplex-enabled"
            );

        const options =
            document.getElementById(
                "duplex-options"
            );

        const state =
            document.getElementById(
                "duplex-state"
            );

        const evenButton =
            document.getElementById(
                "duplex-even-button"
            );

        const reverse =
            document.getElementById(
                "duplex-reverse"
            );

        const addButton =
            findButton(
                /he añadido|añadir más/i
            );

        const finishButton =
            findButton(
                /finalizar documento|finalizar/i
            );


        if (
            duplexInfo &&
            duplexInfo.enabled
        ) {

            enabled.checked = true;
            enabled.disabled = true;

            options.style.display =
                "block";

            reverse.checked =
                duplexInfo.reverse_even
                !== false;

            // La segunda pasada se invierte siempre.
            reverse.disabled = true;


            if (
                duplexInfo.side === "odd"
            ) {

                state.innerHTML =
                    "🟦 <b>Caras impares</b>" +
                    "<br>" +
                    duplexInfo.odd_pages +
                    " cara(s) escaneada(s)" +
                    "<br><small>" +
                    "Puedes añadir más caras " +
                    "impares o pasar a las pares." +
                    "</small>";

                evenButton.style.display =
                    (
                        !duplexInfo.running &&
                        duplexInfo.odd_pages > 0
                    )
                    ? "block"
                    : "none";


                if (addButton) {

                    addButton.textContent =
                        "➕ He añadido más caras impares";
                }

            } else {

                state.innerHTML =
                    "🟨 <b>Caras pares</b>" +
                    "<br>" +
                    "Impares: " +
                    duplexInfo.odd_pages +
                    " · Pares: " +
                    duplexInfo.even_pages;

                evenButton.style.display =
                    "none";


                if (addButton) {

                    addButton.textContent =
                        "➕ He añadido más caras pares";
                }
            }


            if (finishButton) {

                finishButton.disabled =
                    !duplexInfo
                        .ready_to_finalize;
            }

        } else {

            enabled.disabled = false;

            if (finishButton) {
                finishButton.disabled = false;
            }
        }
    }


    function initDuplex() {

        createDuplexPanel();

        refreshDuplexInfo();

        setInterval(
            refreshDuplexInfo,
            2500
        );
    }


    if (
        document.readyState ===
        "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            initDuplex
        );

    } else {

        initDuplex();
    }

})();


/* ============================================================
   SESSION_RESTORE_V1
   Restaurar sesión real después de F5 / reload / pageshow
   ============================================================ */

(() => {

    let restoreTimer = null;
    let attempts = 0;


    async function restoreRealSession() {

        attempts++;

        /*
         * Después de un F5, /api/me puede no haber terminado
         * todavía cuando se ejecuta este código.
         *
         * Esperamos hasta que la aplicación haya recuperado
         * currentUser.
         */
        if (!currentUser) {

            if (attempts < 80) {

                restoreTimer =
                    setTimeout(
                        restoreRealSession,
                        250
                    );
            }

            return;
        }


        try {

            /*
             * updateStatus() consulta /api/status.
             *
             * El servidor es siempre la fuente de verdad:
             * no localStorage, no variables del navegador.
             */
            await updateStatus();


            /*
             * Una segunda actualización ligeramente posterior
             * permite que el panel dúplex ya haya terminado
             * también su inicialización.
             */
            setTimeout(
                () => {
                    updateStatus();
                },
                400
            );


            /*
             * Tercera comprobación para páginas restauradas
             * desde cache/back-forward cache.
             */
            setTimeout(
                () => {
                    updateStatus();
                },
                1200
            );

        } catch (error) {

            console.error(
                "No se pudo restaurar la sesión:",
                error
            );
        }
    }


    function startSessionRestore() {

        if (restoreTimer) {
            clearTimeout(
                restoreTimer
            );
        }

        attempts = 0;

        restoreRealSession();
    }


    /*
     * Carga normal
     */
    if (
        document.readyState ===
        "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            startSessionRestore
        );

    } else {

        startSessionRestore();
    }


    /*
     * F5, atrás/adelante, BFCache, móvil, etc.
     */
    window.addEventListener(
        "pageshow",
        startSessionRestore
    );


    /*
     * Si se vuelve a la pestaña después de haberla
     * dejado abierta, recuperamos también el estado
     * real del servidor.
     */
    document.addEventListener(
        "visibilitychange",
        () => {

            if (
                document.visibilityState ===
                "visible"
                &&
                currentUser
            ) {

                updateStatus();
            }
        }
    );

})();


/* === SCANSERVER_HISTORY_PAGER_V2 === */

(() => {
    "use strict";

    const STORAGE_KEY = "scanserver_history_rows";
    const SIZES = [10, 25, 50, 100];

    let pageSize = 25;
    let currentPage = 1;
    let scheduled = false;

    try {
        const saved = Number(
            localStorage.getItem(STORAGE_KEY)
        );

        if (SIZES.includes(saved)) {
            pageSize = saved;
        }
    } catch (_) {}


    function install() {
        const container =
            document.getElementById("documents");

        if (!container) {
            return false;
        }

        if (
            document.getElementById(
                "scan-history-pager"
            )
        ) {
            return true;
        }

        const style = document.createElement("style");

        style.textContent = `
            #documents > .document {
                min-height: 0 !important;
                padding: 8px 12px !important;
                margin: 0 0 5px !important;
                gap: 8px !important;
                border-radius: 8px !important;
                line-height: 1.3;
            }

            #documents > .document.ss-hidden {
                display: none !important;
            }

            #scan-history-pager {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 12px;
                margin: 12px 0;
                padding: 12px;
                border: 1px solid
                    rgba(128,128,128,.22);
                border-radius: 10px;
            }

            #scan-history-pager[hidden] {
                display: none !important;
            }

            #scan-history-pager label {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: .9rem;
            }

            #scan-history-pager select {
                width: auto;
                min-width: 72px;
                padding: 6px 8px;
                border-radius: 7px;
            }

            .ss-history-navigation {
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .ss-history-navigation button {
                width: auto;
                min-width: 0;
                padding: 7px 11px;
                border-radius: 7px;
            }

            .ss-history-count,
            .ss-history-page {
                font-size: .85rem;
                opacity: .8;
            }

            @media(max-width: 650px) {
                #scan-history-pager {
                    flex-direction: column;
                    align-items: stretch;
                }

                .ss-history-navigation {
                    justify-content: space-between;
                }

                #scan-history-pager label {
                    justify-content: center;
                }

                .ss-history-count {
                    text-align: center;
                }

                #documents > .document {
                    padding: 9px !important;
                }
            }
        `;

        document.head.appendChild(style);

        const panel = document.createElement("div");
        panel.id = "scan-history-pager";

        panel.innerHTML = `
            <label>
                Mostrar
                <select id="ss-history-size">
                    <option value="10">10</option>
                    <option value="25">25</option>
                    <option value="50">50</option>
                    <option value="100">100</option>
                </select>
                registros
            </label>

            <span
                class="ss-history-count"
                id="ss-history-count"
            ></span>

            <div class="ss-history-navigation">
                <button
                    type="button"
                    id="ss-history-prev"
                >
                    Anterior
                </button>

                <span
                    class="ss-history-page"
                    id="ss-history-page"
                ></span>

                <button
                    type="button"
                    id="ss-history-next"
                >
                    Siguiente
                </button>
            </div>
        `;

        container.parentNode.insertBefore(
            panel,
            container
        );

        const selector =
            panel.querySelector("#ss-history-size");

        const countLabel =
            panel.querySelector("#ss-history-count");

        const pageLabel =
            panel.querySelector("#ss-history-page");

        const prevButton =
            panel.querySelector("#ss-history-prev");

        const nextButton =
            panel.querySelector("#ss-history-next");

        selector.value = String(pageSize);


        function getRows() {
            return Array.from(
                container.children
            ).filter(
                el => el.classList.contains("document")
            );
        }


        function render() {
            const rows = getRows();
            const total = rows.length;

            panel.hidden = total === 0;

            const totalPages = Math.max(
                1,
                Math.ceil(total / pageSize)
            );

            currentPage = Math.min(
                Math.max(currentPage, 1),
                totalPages
            );

            const start =
                (currentPage - 1) * pageSize;

            const end = Math.min(
                start + pageSize,
                total
            );

            rows.forEach((row, index) => {
                row.classList.toggle(
                    "ss-hidden",
                    index < start || index >= end
                );
            });

            countLabel.textContent = total
                ? `Mostrando ${start + 1}-${end} de ${total}`
                : "";

            pageLabel.textContent =
                `${currentPage} / ${totalPages}`;

            prevButton.disabled = currentPage <= 1;
            nextButton.disabled =
                currentPage >= totalPages;
        }


        function scheduleRender() {
            if (scheduled) return;

            scheduled = true;

            requestAnimationFrame(() => {
                scheduled = false;
                render();
            });
        }


        selector.addEventListener("change", () => {
            const selected = Number(selector.value);

            if (!SIZES.includes(selected)) {
                return;
            }

            pageSize = selected;
            currentPage = 1;

            try {
                localStorage.setItem(
                    STORAGE_KEY,
                    String(pageSize)
                );
            } catch (_) {}

            render();
        });


        prevButton.addEventListener("click", () => {
            if (currentPage > 1) {
                currentPage--;
                render();

                panel.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            }
        });


        nextButton.addEventListener("click", () => {
            const totalPages = Math.max(
                1,
                Math.ceil(getRows().length / pageSize)
            );

            if (currentPage < totalPages) {
                currentPage++;
                render();

                panel.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });
            }
        });


        // Se actualiza automáticamente cuando
        // ScanServer carga o recarga documentos.
        new MutationObserver(
            scheduleRender
        ).observe(container, {
            childList: true
        });

        render();

        console.info(
            "ScanServer: histórico paginado V2 activo"
        );

        return true;
    }


    function initialize() {
        if (install()) return;

        // Compatible con interfaces que crean
        // el contenedor de documentos dinámicamente.
        const observer = new MutationObserver(() => {
            if (install()) {
                observer.disconnect();
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }


    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initialize,
            {once: true}
        );
    } else {
        initialize();
    }
})();
