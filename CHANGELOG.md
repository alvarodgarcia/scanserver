# Changelog

All notable changes to ScanServer are documented here. Versioning follows SemVer.

## [Unreleased]

### Planned
- Server-side document pagination and filters.
- Persistent scan sessions across service restarts.
- Security middleware for local authentication throttling and origin checks.
- Standalone installation automation, including the Samba user helper.
- Automated scanner-free integration tests.

## [0.1.0] - 2026-11-26

### Initial baseline
- Web interface with authenticated per-user document storage.
- HP/eSCL ADF scanning via SANE/airscan, multi-batch jobs, PDF generation and optional OCR.
- Manual duplex workflow, user folders and Samba user management integration.
- Compact history browser with client-side 10/25/50/100-row pagination.
- LAN-only deployment instructions and sanitized UI demo screenshots.

### Security / portability
- Removed unsafe hard-coded fallback for the signed-session key; environment secret is now mandatory.
- Made scanner SANE identifier and eSCL status endpoint configurable.
- Removed unused legacy reverse-proxy security module from the public snapshot.
- Generalized private/person-specific example values in the interface.

**Important:** This first source release is a reviewed code snapshot, not a one-command standalone installer. Required local provisioning is detailed in docs/INSTALLATION.md.
