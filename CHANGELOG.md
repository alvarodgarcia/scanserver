# Changelog

All notable changes to ScanServer are documented here. Versioning follows SemVer.

## [Unreleased]

### Planned
- Real backend pagination and persistent scan sessions (v0.2.0).
- Reproducible LXC installer with audited Samba helper.
- Hardware/Samba integration tests.

## [0.1.1] - Unreleased (candidate)

### Security
- Require same-origin Origin/Referer on all API writes; reject cross-site fetch metadata.
- Limit failed logins per IP (8 within 5 minutes, 5-minute lockout; per-process).
- Add session_version migration; password changes and account state changes revoke prior sessions.
- Limit new user directory permissions to owner/group; stop returning privileged SMB helper error text.

### Stability
- Reserve the physical scanner and session status together under one lock.
- Make duplex odd-to-even transition and cancel operations atomic.
- Send duplex mode in the initial scan request instead of intercepting global window.fetch.
- Make automatic backside reversal explicit and disable the ineffective reverse checkbox.

### Tests
- Add isolated checks for origin validation, login throttle, DB migration and atomic scan start.

### Deployment notes
- Existing users must sign in again when upgrading to this version.
- No changes applied to the active LXC; validate first in a test environment.
- Release remains a draft candidate until real ADF, OCR, duplex and Samba smoke tests are complete.

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
