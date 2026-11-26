# ScanServer v0.1.1 — parche controlado para el LXC

**Estado:** candidato de pruebas; no instalado ni validado todavía en tu escáner real.

Este paquete aplica únicamente tres archivos (`web/app.py`, `web/static/app.js`, `web/static/index.html`) desde el commit INMUTABLE `1f8f44ec756e1aae0ec428649bebbdbe98c283c9` de `alvarodgarcia/scanserver`.

La versión v0.1.0 estable de GitHub permanece intacta. No modifica los scripts SANE, el helper SMB, Samba, los archivos escaneados, ni los usuarios o sus contraseñas.

## Qué incluye

- `scripts/apply_v0.1.1.sh`: preflight, descarga y verificación de Git blobs, respaldo de código y SQLite, parada controlada, despliegue y prueba de salud; rollback del código si falla.
- `scripts/rollback_v0.1.1.sh`: restaura los tres archivos del respaldo sin reemplazar bases de datos en uso.

## Antes de instalar

1. **Finaliza o cancela cada sesión en la interfaz** (también cualquier escaneo dúplex) y bloquea nuevos escaneos durante la ventana de mantenimiento.
2. Haz una instantánea/backup de Proxmox del LXC cuando esté en reposo. El script guarda una copia de la base de datos y del código, pero no de todos los PDF bajo `/srv/scans`.
3. Identifica el servicio: `systemctl list-unit-files | grep -i scanserver`. Si hay más de uno, usa `--service nombre.service`.
4. La nueva versión necesita que el servicio ya tenga `SCANSERVER_SECRET` aleatorio de al menos 32 caracteres. El preflight solo comprueba su longitud **sin mostrar el valor**. Si falta, no se instalará nada: se debe preparar un `EnvironmentFile` o drop-in systemd específico del servicio, en un paso separado.
5. Esta versión obliga a todos los usuarios a iniciar sesión otra vez. Conserva las cuentas y hashes Argon2.

## Transferir desde PowerShell de Windows

Con este archivo descomprimido o con su `.tar.gz`:

```powershell
scp "$env:USERPROFILE\Downloads\ScanServer_v0.1.1_ServerPatch.tar.gz" root@192.168.1.16:/root/
ssh root@192.168.1.16
```

Dentro del LXC:

```bash
cd /root
tar -xzf ScanServer_v0.1.1_ServerPatch.tar.gz
cd ScanServer_v0.1.1_ServerPatch
bash scripts/apply_v0.1.1.sh --check-only
```

Si el preflight está bien y no hay nadie escaneando:

```bash
bash scripts/apply_v0.1.1.sh --health-url http://127.0.0.1:8080/api/me
```

Si la interfaz **no** escucha en localhost, sustituye la URL por `http://192.168.1.16:8080/api/me` (o el destino LAN real). Si no detecta exactamente un servicio `scanserver*.service`, añade `--service nombre.service`.

**Verificación esperada:** respuesta HTTP 401 sin autenticar de `/api/me`, `systemctl is-active`, y después login + prueba PDF de prueba con usuario normal. No hagas pruebas destructivas con documentos personales.

### Si el LXC no tiene salida a GitHub

Descarga desde Windows el ZIP del commit exacto:

`https://github.com/alvarodgarcia/scanserver/archive/1f8f44ec756e1aae0ec428649bebbdbe98c283c9.tar.gz`

Cópialo a `/root/scanserver-source-v011.tar.gz` mediante SCP, y utiliza:

```bash
bash scripts/apply_v0.1.1.sh --archive /root/scanserver-source-v011.tar.gz --health-url http://127.0.0.1:8080/api/me
```

El script sigue validando que los tres archivos del archive coinciden exactamente con los Git blobs del commit auditado.

## Volver atrás

La instalación muestra la ruta de backup, por ejemplo:

`/var/backups/scanserver-v0.1.1-AAAAmmddTHHMMSSZ-PID`

Con el escáner sin sesiones pendientes:

```bash
bash scripts/rollback_v0.1.1.sh --backup /var/backups/scanserver-v0.1.1-... --health-url http://127.0.0.1:8080/api/me
```

El rollback **no elimina ni restaura automáticamente SQLite**, para no perder usuarios o cambios posteriores al despliegue; la columna añadida `session_version` es inocua para la versión anterior. El backup de SQLite queda conservado bajo permisos root `0700` por si se necesita una recuperación manual.

## Límites conocidos

- El preflight bloquea cualquier directorio de sesión pendiente, incluso residuos de trabajos antiguos. No borres estos archivos sin inspeccionarlos.
- Las comprobaciones automatizadas de CI han pasado, pero no equivalen a un test real ADF/OCR/Samba.
- El rate-limit de login es por proceso y no funciona como límite compartido si hubiera varios workers.
- Los clientes HTTP externos que escriban directamente en `/api/` sin cabecera `Origin` o `Referer` compatible recibirán HTTP 403. La interfaz normal del navegador envía el `Origin` correspondiente.
- Este parche no modifica reglas de red, cortafuegos ni abre acceso desde Internet. **Solo LAN.**

> Los scripts del parche se distribuyen como paquete descargable en la conversación de revisión; no se ha desplegado aún en ningún servidor.
