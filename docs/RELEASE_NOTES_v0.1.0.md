# ScanServer v0.1.0 — Initial public source release

This first version documents the existing LAN-only scanning application as an initial source snapshot.

## Included

- Web UI for desktop and mobile; Argon2-based user login and separate user document folders.
- SANE/eSCL ADF workflows, multiple scan batches, PDF creation and optional OCR.
- Manual two-pass duplex assembly, compact history UI and 10/25/50/100 row selection.
- README, version history, setup instructions, security policy, roadmap and anonymized demo screenshots.
- Static syntax and source-safety checks in GitHub Actions.

## Important limitations

- **LAN only:** do not port-forward the API or SMB service to the Internet.
- This is a **source snapshot**, not an independently tested, turnkey installer. The external Samba helper and deployment-specific systemd configuration are not bundled.
- Current frontend history pagination only covers the backend's returned records; real backend pagination is planned.
- Current sessions are in-memory and do not survive service restarts.
- Additional tests and hardening for CSRF, authentication throttling, session revocation and user path isolation are planned.

See [SECURITY.md](../SECURITY.md) and [security audit](SECURITY_AUDIT.md) before deployment.
