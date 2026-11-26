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

## Known initial-release limitations

- The legacy `web/security.py` reverse-proxy middleware was unused in the supplied runtime and is not included in this source distribution. Authentication throttling is **not** enabled by the FastAPI app in v0.1.0.
- No additional CSRF token mechanism has been verified beyond `SameSite=Strict` cookies; origin validation should be added and tested.
- Password changes may not revoke already-issued signed sessions.
- Dedicated integration tests for user isolation, symlink behavior and Samba helper permissions are pending.
- In-memory scan sessions do not survive service restarts.
- An authenticated user may see a list of up to 100 documents; server-side pagination is pending.

## Reporting a vulnerability

Use GitHub private vulnerability reporting / security advisories where available. Avoid including credentials, private documents or network details in public issues.

Full audit notes: [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md).