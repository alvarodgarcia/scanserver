# Roadmap

## v0.1.0 — initial baseline
- Current ADF scanning, multi-page sessions, PDF generation and OCR.
- Manual duplex and compact paged history (frontend only).
- Source sanitization, documentation, fictional-data previews, static CI tests.

## v0.1.1 — stability and LAN security
- Effective authentication throttling for the LAN app (not the unused proxy module).
- Origin/CSRF protections and robust session revocation.
- Multi-user isolation, symlink and file ownership tests.
- Safer Samba helper error handling.

## v0.2.0 — history and state
- Backend pagination of all PDF documents, sorting, searching and page-size selection.
- Persistent sessions, recovery after restart and detailed scan-job state.
- Cleaner JS modules; remove legacy fetch interception from duplex UI.

## v0.3.0 — scanner UX and deployability
- Scanner autodiscovery and settings without hard-coded host addresses.
- Reliable ADF status, resume-after-jam and duplex edge cases.
- Reproducible installer, privileged helper and systemd examples with tests.
- Accessibility and translations.
