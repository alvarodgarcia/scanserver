# Initial security review — 2026-11-26

**Scope:** eight source files from the supplied LXC archive. **Not reviewed:** live environment settings, Samba privileged helper, systemd service, firewall, actual SQLite file, network ACLs, credentials or runtime logs. This is a code review, **not a penetration test or security certification**.

| Severity | Finding | Evidence | State in public snapshot |
|---|---|---|---|
| High | The session signing key defaulted to a predictable static literal. Forged cookies could become possible if the service used this fallback. | `web/app.py`, original lines 68–71 | **Fixed in source**: requires a 32+ character environment secret; production environment not independently verified |
| Medium | `web/security.py` existed but the FastAPI app did not import or register its middleware; its advertised login throttling / CSRF and host checks were not active. | Original `web/security.py`; no import/add_middleware in original `web/app.py` | **Documented**: unused legacy proxy module intentionally omitted. LAN-specific hardening pending |
| Medium | A real internal scanner IP and unique SANE device identifier were hard-coded. | Original `scan_batch.sh`/`scan.sh` | **Fixed in source**: environment variables required |
| Medium | A personal domain appeared in the unused proxy security module. | Original `web/security.py` | **Removed with unused module** |
| Medium | Plain HTTP is used on LAN by default; signed cookies are not encrypted in transit. | `web/app.py`, `SCANSERVER_HTTPS` and SessionMiddleware | **Documented**: LAN-only; optional HTTPS now controls Secure cookie flag |
| Medium | No verified IP/account login rate limiting in the effective application. | `web/app.py` login flow | Open, planned for v0.1.1 |
| Medium | No verified CSRF token or active origin middleware. | All POST routes, same-site cookie setting | Open, planned for v0.1.1 |
| Medium | User-provided folders and PDF symlink edge cases require isolation tests, especially under SMB. | `safe_user_path`, `/api/documents`, `/documents` | Open; basic path `resolve()` restrictions exist |
| Low | The history API returns at most 100 files; frontend paging is visual only. | `/api/documents` | Open, v0.2.0 |
| Operational | In-memory `current_session` does not persist through restarts. | `web/app.py` | Open, v0.2.0 |
| Operational | Error text from Samba helper may be returned to API callers (administrators). | `smb_account` | Review helper and sanitize failure messages |

## Secret scan results

- No real plaintext application user password, real token value, credential database or PDF was present among the eight supplied text source files.
- Configuration identifiers and a personal example were found. These were parameterized or replaced for the public package.
- **Unknown:** actual secret injected by systemd and the external Samba helper, because neither was supplied.

## Before publishing

- Verify generated files with a secret scanner such as Gitleaks; inspect all commit history before marking a repo public.
- Use fictional sample accounts and documents in screenshots.
- Do not include `security.py` from the original backup, `.env`, databases, scanner IPs, backups or logs.
- Restrict ports 8080 and 445 to trusted networks, not WAN.
- Choose a license before publishing if the project is to be open source.


## v0.1.1 development candidate update

These changes are **on a development branch**, not the released v0.1.0 baseline:

- [Implemented in source] Request origin verification for every mutating API endpoint.
- [Implemented in source] IP-based login throttling; in-memory only.
- [Implemented in source] Session-version migration and revocation on password/status change.
- [Implemented in source] Atomic scanner start, odd/even transition and cancellation.
- [Implemented in source] Restricted new account directories and redacted SMB helper errors.
- [Added] Isolated tests that do not connect to real scanners or user records.

**Still outstanding:** rate limiting across multiple workers, runtime-origin compatibility checks for supported browsers, end-to-end scanner/Samba authorization tests, symlink race defense, and live deployment audit. No security certification is claimed.
