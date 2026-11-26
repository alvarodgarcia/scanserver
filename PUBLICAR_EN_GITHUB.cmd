@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PUBLICAR_EN_GITHUB.ps1"
echo.
if errorlevel 1 (
  echo No se ha completado la publicacion. Consulta el error mostrado arriba.
)
pause
