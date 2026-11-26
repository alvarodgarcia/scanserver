# Security policy — ScanServer

## Intended deployment

ScanServer is a **LAN-only** self-hosted scanning service. Publishing the source repository on GitHub does **not** imply that the web UI, scanner, or SMB services should be exposed to the public Internet.

- Restrict web port 8080 and SMB ports to trusted local networks or a private VPN.
- Do not configure port forwarding, public reverse proxies or anonymous remote access.
- Segment untrusted IoT networks; allow only the specific scanner protocols required.
- Always configure a unique, random `SCANSERVER_SECRET` (32+ characters) outside the repository.
- Do not publish `.env`, `/opt/scanserver/data`, scanned files, usernames, Samba credentials, session files or real screenshots.
- HTTP on LAN is not encrypted. Use an internal TLS endpoint if the LAN includes untrusted clients or Wi-Fi.
- Run services with the minimum permissions compatible with SANE, document storage and the SMB helper.

## v0.1.1 development hardening

The unmerged v0.1.1 branch adds same-origin protection for browser API writes, per-process login throttling, session revocation on password or enabled-state change, stricter new-user folder permissions, and atomic scan/duplex transitions. **It is a candidate, not an audited production release.**

- Browser API POST requests require a same-origin `Origin` header (or valid same-origin `Referer`). If integrating external clients, configure the correct local origin deliberately.
- The login limiter is **in memory and per process**; it must be replaced with shared persistent storage for multiple Uvicorn workers.
- The database migration adds `session_version` to `users` without deleting data. All existing sessions must sign in again.
- Avoid restarting the LXC during an active scanning session; job state is still memory-only.
- The real Samba helper, deployment configuration and end-to-end scanner behavior are not included in this audit.

## Known initial-release limitations

- The legacy `web/security.py` reverse-proxy middleware was unused in the supplied runtime and is not included in this source distribution. Authentication throttling is **not** enabled by the FastAPI app in v0.1.0 (addressed in v0.1.1 candidate).
- No additional CSRF token mechanism has been verified beyond `SameSite=Strict` cookies; origin validation should be added and tested.
- Password changes may not revoke already-issued signed sessions.
- Dedicated integration tests for user isolation, symlink behavior and Samba helper permissions are pending.
- In-memory scan sessions do not survive service restarts.
- An authenticated user may see a list of up to 100 documents; server-side pagination is pending.

## Reporting a vulnerability

Use GitHub private vulnerability reporting / security advisories where available. Avoid including credentials, private documents or network details in public issues.

Full audit notes: [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md).
