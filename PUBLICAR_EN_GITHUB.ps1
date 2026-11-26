# ScanServer v0.1.0 - publicaciÃ³n completa y segura en GitHub.
# Ejecutar desde Windows, DESPUES de extraer todo el ZIP.
# Necesita Git for Windows y GitHub CLI (gh). No incorpora contraseÃ±as ni tokens.

$ErrorActionPreference = 'Stop'
$repo = 'alvarodgarcia/scanserver'
$remote = "https://github.com/$repo.git"
$description = 'LAN-only self-hosted document scanning web app with SANE/eSCL, ADF, OCR searchable PDFs, manual duplex and user folders.'
$topics = 'self-hosted,document-scanning,ocr,fastapi,homelab,lan'
$source = $PSScriptRoot
$temp = Join-Path $env:TEMP ('scanserver-publish-' + [guid]::NewGuid().ToString('N'))
$target = Join-Path $temp 'repository'

function Assert-Exit([string]$operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$operation ha fallado (cÃ³digo $LASTEXITCODE). No se realizarÃ¡ un push forzado."
    }
}

Write-Host "ScanServer v0.1.0 -> $remote" -ForegroundColor Cyan
foreach ($exe in @('git', 'gh')) {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
        throw "No encuentro '$exe'. Instala Git for Windows y GitHub CLI (gh) antes de ejecutar el publicador."
    }
}

foreach ($required in @('VERSION', 'web/app.py', 'web/static/app.js', 'web/static/index.html',
                      'scan_batch.sh', 'README.md', 'SECURITY.md', 'docs/screenshots/dashboard-demo.png')) {
    if (-not (Test-Path -LiteralPath (Join-Path $source $required))) {
        throw "Falta '$required'. Extrae el ZIP completo y ejecuta el .cmd desde esa carpeta."
    }
}

if ((Get-Content (Join-Path $source 'VERSION') -Raw).Trim() -ne '0.1.0') {
    throw 'El paquete no corresponde a la versiÃ³n v0.1.0.'
}

& gh auth status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Abriendo autenticaciÃ³n con GitHub...' -ForegroundColor Yellow
    & gh auth login --hostname github.com --web --git-protocol https
    Assert-Exit 'AutenticaciÃ³n'
}
& gh auth setup-git
Assert-Exit 'ConfiguraciÃ³n de GitHub CLI'
$login = (& gh api user --jq .login).Trim()
Assert-Exit 'Identificar usuario'
if ($login -ne 'alvarodgarcia') { throw "La cuenta conectada es '$login', no 'alvarodgarcia'." }
& gh repo view $repo --json name,visibility
Assert-Exit 'Comprobar repositorio'

New-Item -ItemType Directory -Path $temp -Force | Out-Null
try {
    # CLONAR evita rechazos por los commits que ya se han realizado desde ChatGPT.
    & git clone --branch main $remote $target
    Assert-Exit 'Clonar repositorio existente'

    # Copiar archivos individualmente con su ruta relativa.
    # Evita duplicados como docs/docs, tests/tests y .github/.github
    # cuando el repositorio ya contiene esas carpetas.
    Get-ChildItem -LiteralPath $source -File -Recurse -Force |
        Where-Object { $_.FullName -notmatch '[\\/]\.git([\\/]|$)' } |
        ForEach-Object {
            $relative = $_.FullName.Substring($source.Length).TrimStart([char[]]@('\', '/'))
            $destination = Join-Path $target $relative
            $parent = Split-Path -Parent $destination
            if (-not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Force
        }

    # Limpiar espacios invisibles y lineas extra al final de archivos
    # de la interfaz y del publicador, solo en el clon temporal.
    foreach ($relative in @('PUBLICAR_EN_GITHUB.ps1', 'web/static/app.js', 'web/static/index.html')) {
        $filePath = Join-Path $target $relative
        if (-not (Test-Path -LiteralPath $filePath)) { continue }
        $oldText = [System.IO.File]::ReadAllText($filePath)
        $newText = [regex]::Replace($oldText, '(?m)[ \t]+(?=\r?$)', '')
        $newText = [regex]::Replace($newText, '(?:\r?\n)+\z', "`n")
        if ($newText -ne $oldText) {
            [System.IO.File]::WriteAllText(
                $filePath, $newText, (New-Object System.Text.UTF8Encoding($false))
            )
        }
    }

    # Evita conversiones LF -> CRLF durante el git add en Windows.
    & git -C $target config core.autocrlf false
    Assert-Exit 'Configurar saltos de linea'

    $localName = (& git -C $target config user.name) -join ''
    if (-not $localName.Trim()) {
        & git -C $target config user.name $login
        Assert-Exit 'Configurar autor'
    }
    $localEmail = (& git -C $target config user.email) -join ''
    if (-not $localEmail.Trim()) {
        $githubId = (& gh api user --jq .id).Trim()
        Assert-Exit 'Identificar ID GitHub'
        & git -C $target config user.email "$githubId+$login@users.noreply.github.com"
        Assert-Exit 'Proteger correo del autor'
    }

    & git -C $target add --all
    Assert-Exit 'Preparar archivos'
    & git -C $target diff --cached --check
    Assert-Exit 'Revisar cambios'
    $stagedNames = @(& git -C $target diff --cached --name-only)
    if ($stagedNames.Count -gt 0) {
        Write-Host ('Archivos nuevos o modificados: ' + $stagedNames.Count) -ForegroundColor Cyan
        $stagedNames | ForEach-Object { Write-Host "  $_" }
        & git -C $target commit -m 'chore: import complete sanitized ScanServer v0.1.0 source'
        Assert-Exit 'Crear commit'
        & git -C $target push origin main
        Assert-Exit 'Publicar rama main'
    } else {
        Write-Host 'CÃ³digo y documentaciÃ³n ya publicados; no hay diferencias.'
    }

    # El tag solamente se publica despuÃ©s del push del contenido completo.
    & git -C $target fetch origin --tags
    Assert-Exit 'Consultar etiquetas'
    $tag = (@(& git -C $target tag --list 'v0.1.0') -join "").Trim()
    if (-not $tag) {
        & git -C $target tag -a v0.1.0 -m 'ScanServer v0.1.0 - Initial LAN-only source release'
        Assert-Exit 'Crear etiqueta'
        & git -C $target push origin v0.1.0
        Assert-Exit 'Publicar etiqueta'
    } else {
        Write-Host 'La etiqueta v0.1.0 ya existe; no se modificarÃ¡.' -ForegroundColor Yellow
    }

    # Esta operaciÃ³n requiere permiso de administraciÃ³n del repositorio.
    & gh repo edit $repo --description $description --add-topic $topics
    Assert-Exit 'Guardar descripciÃ³n y temas'

    & gh release view v0.1.0 --repo $repo --json tagName --jq .tagName 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & gh release create v0.1.0 --repo $repo --verify-tag `
            --title 'ScanServer v0.1.0 - Initial release' `
            --notes-file (Join-Path $target 'docs/RELEASE_NOTES_v0.1.0.md')
        Assert-Exit 'Crear entrega GitHub Release'
    }

    Write-Host ''
    Write-Host 'PUBLICACION COMPLETA' -ForegroundColor Green
    Write-Host "https://github.com/$repo"
    Write-Host "https://github.com/$repo/releases/tag/v0.1.0"
} finally {
    # Mantener la copia temporal si algo falla permite inspeccionar el problema.
    if (Test-Path $target) { Write-Host "Clon de trabajo: $target" }
}
