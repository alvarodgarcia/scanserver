# Installation and migration (LAN only)

**Status:** documented source snapshot, not an automated installer. The current installation also depends on existing operating-system users, Samba configuration, a privileged Samba helper and a systemd unit that were **not included in the supplied source archive**.

## 1. Host packages

Example for Debian-based systems (confirm package names for your distribution):

```sh
sudo apt update
sudo apt install sane-utils sane-airscan curl img2pdf ocrmypdf tesseract-ocr tesseract-ocr-spa python3-venv samba
scanimage -L
```

Confirm the scanner is reachable from the service environment before proceeding.

## 2. Python environment

```sh
sudo mkdir -p /opt/scanserver
# Copy the repository's Python and shell source under /opt/scanserver
python3 -m venv /opt/scanserver/venv
/opt/scanserver/venv/bin/pip install -r /opt/scanserver/requirements.txt
```

The OCR plugin is invoked by `/usr/bin/ocrmypdf`, which uses the system Python environment. Keep the OCR system dependencies separate from the web venv.

## 3. Environment

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Create a private environment file (for example `/etc/default/scanserver`) owned by root, mode `0600`; set the scanner values obtained from your installation, **not** example values:

```sh
SCANSERVER_SECRET=<random-generated-secret>
SCANSERVER_HTTPS=0
SCANSERVER_SANE_DEVICE=<exact-scanimage-L-device>
SCANSERVER_SCANNER_STATUS_URL=https://<scanner-address>/eSCL/ScannerStatus
SCANSERVER_OCR_LANG=spa
```

For systemd, use `EnvironmentFile=/etc/default/scanserver` in a unit adapted to your deployment. Never put real credentials in the repository. Keep Uvicorn bound only to an appropriate private interface, and restrict access to port 8080 at the firewall.

## 4. Required storage and Samba prerequisites

- `/opt/scanserver/data/scanserver.db` stores account metadata and Argon2 hashes. Do not publish or overwrite it.
- `/srv/scans/usuarios` contains private user PDF folders.
- `/srv/scans/sessions` contains temporary jobs and manual duplex markers.
- `/usr/local/sbin/scanserver-smb-user` is an **external deployment-specific helper**. Its create/password/enable/disable contract is expected by `web/app.py`, but its implementation was not supplied. Provision and audit it separately. Do not grant unrestricted root execution to the FastAPI process.
- Check ownership, ACLs, Samba `[homes]` mapping, and SMB account lifecycle on your host.

## 5. First run (only after prerequisites)

```sh
cd /opt/scanserver
set -a
. /etc/default/scanserver
set +a
/opt/scanserver/venv/bin/uvicorn web.app:app --host 127.0.0.1 --port 8080
```

Use a trusted LAN bind and firewall rule for remote local clients. Do not port-forward 8080 or SMB.

## Safe upgrade of an existing installation

1. **Complete and finalize all running scans first.** Scan session state is in memory and restarts can strand unfinished jobs.
2. Back up `/opt/scanserver` excluding secrets from any public destination, SQLite database, and `/srv/scans` separately.
3. Compare existing `web/app.py`, scripts and environment variables with this release; the public snapshot is not a drop-in migration script.
4. Verify a local admin login, a standard-user login, document isolation, ADF scanning, OCR, duplex assembly and SMB accounts.
5. Roll back by restoring the backup if necessary.

## Verification

```sh
python3 -m compileall -q web/app.py ocr_progress.py
bash -n scan.sh scan_batch.sh finalize.sh
node --check web/static/app.js  # if Node is available
python3 -m unittest discover -s tests -v
```
