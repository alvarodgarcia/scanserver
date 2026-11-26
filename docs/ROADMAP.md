# Roadmap

## v0.1.0 — initial baseline
- Current ADF scanning, multi-page sessions, PDF generation and OCR.
- Manual duplex and compact paged history (frontend only).
- Source sanitization, documentation, fictional-data previews, static CI tests.

## v0.1.1 — stability and LAN security (development candidate)
- [x] In-process login throttle and same-origin API mutation checks.
- [x] Session revocation after credential/status changes; non-destructive SQLite migration.
- [x] Atomic start/duplex/cancel transitions and fixed duplex selection.
- [x] Private new-user folder permissions; generic privileged-helper errors.
- [x] Isolated origin/login/concurrency regressions.
- [ ] Live scanner ADF, OCR, duplex, login and Samba tests before release.
- [ ] Stronger multi-user isolation and symlink tests using a non-privileged runtime.

## v0.2.0 — history and state
- Backend pagination of all PDF documents, sorting, searching and page-size selection.
- Persistent sessions, recovery after restart and detailed scan-job state.
- Further JS modularization (global fetch interception removed in v0.1.1).

## v0.3.0 — scanner UX and deployability
- Scanner autodiscovery and settings without hard-coded host addresses.
- Reliable ADF status, resume-after-jam and duplex edge cases.
- Reproducible installer, privileged helper and systemd examples with tests.
- Accessibility and translations.
