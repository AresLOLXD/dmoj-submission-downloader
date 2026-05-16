# README Deployment Guide — Design Spec

**Date:** 2026-05-16  
**Status:** Approved  
**Scope:** Fix contradictions in the production deployment section of README.md, improve security of admin bootstrap, and add missing documentation. No architectural changes to the app itself.

---

## Problem Statement

The current README has five concrete issues:

1. **Ownership timing contradiction:** Step 1 gives `/opt/dmoj-downloader` to `your-user`, Steps 2–4 run as that user, then Step 5 creates `dmoj-dl` and transfers all ownership. This is backwards — the service user appears after the directory is already configured.
2. **No update procedure:** After `chown -R dmoj-dl` transfers ownership, your user can no longer `git pull` or edit files without `sudo`. The README never explains how to update the app.
3. **Password exposed in process list and shell history:** `create_admin.py admin mi_contraseña` is visible in `ps aux` and `~/.bash_history`.
4. **`HTTPS_ONLY` missing from `.env.example`:** Documented in README but not in the example file users copy.
5. **`uv sync --dev` vs `uv sync` inconsistency:** Dev section uses `--dev`, production doesn't — no explanation of the difference.

---

## Design

### 1. `create_admin.py` — Interactive Password

Modify the script to use `getpass.getpass()` instead of accepting the password as a positional argument.

**Before:**
```bash
uv run python3 create_admin.py admin mi_contraseña_fuerte_123
```

**After:**
```bash
uv run python3 create_admin.py admin
# Prompts: "Contraseña para el administrador: " (no echo)
```

The script still accepts the username as a positional argument. Only the password moves to an interactive prompt. This eliminates exposure in shell history and `ps aux`.

### 2. Permission Model

Use a minimal two-command permission setup after initial configuration. Your user owns all code and the venv. The service user (`dmoj-dl`) owns only the database file. No groups, no `chmod` values beyond one `600`.

```bash
chmod 600 .env                                   # secrets unreadable by other users
sudo chown dmoj-dl:dmoj-dl dmoj_downloader.db    # service writes only to its own DB
```

**Why this works:**
- `.venv/bin/uvicorn` has default `755` permissions — `dmoj-dl` can execute it as world-executable.
- `ProtectSystem=strict` + `ReadWritePaths=/opt/dmoj-downloader` in the service file already limits what `dmoj-dl` can touch at the kernel level.
- `systemd` reads `EnvironmentFile` as root before dropping to `dmoj-dl`, so `.env` never needs to be readable by `dmoj-dl`.
- SQLite WAL/SHM journal files created during runtime will be owned by `dmoj-dl` automatically.

**Update procedure (no permission changes needed):**
```bash
cd /opt/dmoj-downloader
git pull
uv sync
sudo systemctl restart dmoj-downloader
```

### 3. Corrected Step Order in Production Deployment

| # | Step | Who runs it |
|---|------|-------------|
| 1 | Prepare server (apt, Python, uv, Caddy) | your user with sudo |
| 2 | **Create `dmoj-dl` service user** | sudo |
| 3 | Create `/opt/dmoj-downloader` and clone repo | your user |
| 4 | Configure `.env` | your user |
| 5 | Install dependencies (`uv sync`) | your user |
| 6 | Create first admin (interactive, creates DB) | your user |
| 7 | **Apply permissions** (`chmod 600 .env` + `chown dmoj-dl` on DB) | your user + sudo |
| 8 | Install systemd service | sudo |
| 9 | Start and enable service | sudo |
| 10 | Configure Caddy | sudo |
| 11 | Verify deployment | your user |

Creating `dmoj-dl` at Step 2 (before any file setup) eliminates the contradiction where a user referenced in the service file is created after the service file is configured.

### 4. `.env.example` Fix

Add `HTTPS_ONLY` with a comment:

```
HTTPS_ONLY=true
```

With inline comment: `# false solo en desarrollo local sin HTTPS`.

### 5. New "Actualizar la aplicación" Section

Add a dedicated section after "Monitoreo en producción" with three commands:

```bash
cd /opt/dmoj-downloader
git pull
uv sync
sudo systemctl restart dmoj-downloader
```

### 6. `uv sync --dev` Clarification

In the development section, change `uv sync --dev` to `uv sync` and add a note:

> Si vas a ejecutar las pruebas, usa `uv sync --dev` para incluir las dependencias de desarrollo.

This avoids confusing non-technical users while keeping the information available.

---

## Files Changed

| File | Change |
|------|--------|
| `create_admin.py` | Use `getpass.getpass()` for password input |
| `README.md` | Reorder production steps, add permissions step, add update section, clarify `uv sync --dev` |
| `.env.example` | Add `HTTPS_ONLY=true` |

---

## Subagents

| Task | Subagent | Parallel? |
|------|----------|-----------|
| Modify `create_admin.py` to use `getpass` | `voltagent-lang:python-pro` | ✓ with docs |
| Rewrite production deployment section of README | `voltagent-dev-exp:documentation-engineer` | ✓ with code |
| Update `.env.example` | `voltagent-dev-exp:documentation-engineer` | ✓ (same agent) |
| Add "Actualizar la aplicación" section | `voltagent-dev-exp:documentation-engineer` | ✓ (same agent) |
| Security review of permission model | `voltagent-qa-sec:security-auditor` | ✗ (after above) |

---

## Testing

- Run `uv run python3 create_admin.py testuser` locally and verify the interactive prompt works and the user is created in the DB.
- Manually follow the corrected deployment steps on a fresh machine (or VM) to verify no steps break.
- Verify `sudo systemctl status dmoj-downloader` shows the service running after the permission changes.

---

## Out of Scope

- Changes to the app's authentication or session logic.
- Adding a web-based admin bootstrap flow.
- Automated deployment scripts or Ansible playbooks.
