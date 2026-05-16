# README Deployment Guide Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five concrete contradictions in the README deployment guide, make `create_admin.py` prompt for passwords interactively, and add a missing update procedure.

**Architecture:** Three independent file changes — `create_admin.py` (code), `README.md` (documentation), `.env.example` (configuration). Tasks 1 and 2+3 can run in parallel. Task 4 (security review) runs after all others complete.

**Tech Stack:** Python `getpass` stdlib, Markdown, systemd, uv

**Subagents:**
| Task | Subagent | Parallel with |
|------|----------|---------------|
| Task 1 — `create_admin.py` | `voltagent-lang:python-pro` | Task 2 + 3 |
| Task 2 — README rewrite | `voltagent-dev-exp:documentation-engineer` | Task 1 |
| Task 3 — `.env.example` | `voltagent-dev-exp:documentation-engineer` | Task 1 (sequential after Task 2) |
| Task 4 — Security review | `voltagent-qa-sec:security-auditor` | None (runs last) |

---

### Task 1: Update `create_admin.py` to prompt for password interactively

**Files:**
- Modify: `create_admin.py`
- Create: `tests/test_create_admin.py`

**Context:** `create_admin.py` currently accepts the password as `sys.argv[2]`, exposing it in shell history and `ps aux`. Change it to use `getpass.getpass()` and accept only the username as a positional argument.

- [ ] **Step 1: Write the failing test**

Create `tests/test_create_admin.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
import sys

TEST_DB = "test_create_admin.db"


@pytest.fixture(autouse=True)
async def setup_db(monkeypatch):
    monkeypatch.setattr("app.database.DB_PATH", TEST_DB)
    import app.database
    await app.database.init_db()
    yield
    import os
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.mark.asyncio
async def test_create_admin_creates_user(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "adminuser"])
    with patch("getpass.getpass", return_value="securepass123"):
        import create_admin
        await create_admin.main()

    import aiosqlite
    from app.database import get_user_by_username
    async with aiosqlite.connect(TEST_DB) as db:
        db.row_factory = aiosqlite.Row
        user = await get_user_by_username(db, "adminuser")
    assert user is not None
    assert user.is_admin is True


@pytest.mark.asyncio
async def test_create_admin_fails_if_user_exists(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py", "adminuser"])
    with patch("getpass.getpass", return_value="securepass123"):
        import create_admin
        await create_admin.main()

    with pytest.raises(SystemExit) as exc_info:
        monkeypatch.setattr(sys, "argv", ["create_admin.py", "adminuser"])
        with patch("getpass.getpass", return_value="otherpass"):
            await create_admin.main()
    assert exc_info.value.code == 1


@pytest.mark.asyncio
async def test_create_admin_exits_with_wrong_arg_count(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["create_admin.py"])
    with pytest.raises(SystemExit) as exc_info:
        import create_admin
        await create_admin.main()
    assert exc_info.value.code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_create_admin.py -v
```

Expected: 3 failures — `getpass` is not imported in `create_admin.py` yet and `sys.argv` still expects 3 args.

- [ ] **Step 3: Implement the change in `create_admin.py`**

Replace the entire file with:

```python
#!/usr/bin/env python3
"""Bootstrap the first admin user. Run once after initial deployment."""
import asyncio
import getpass
import bcrypt
import aiosqlite
import sys
from app.database import DB_PATH, init_db, create_user, get_user_by_username


async def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python create_admin.py <username>")
        sys.exit(1)

    username = sys.argv[1]
    password = getpass.getpass("Contraseña para el administrador: ")
    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        existing = await get_user_by_username(db, username)
        if existing:
            print(f"Error: user '{username}' already exists.")
            sys.exit(1)
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = await create_user(db, username, hashed, is_admin=True)

    print(f"Admin '{user.username}' created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_create_admin.py -v
```

Expected: 3 PASSED.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add create_admin.py tests/test_create_admin.py
git commit -m "feat: prompt for admin password interactively to avoid shell history exposure"
```

---

### Task 2: Rewrite README production deployment section

**Files:**
- Modify: `README.md`

**Context:** The current deployment section has five issues described in the spec. This task rewrites the section in place with the corrected step order, the new permission model, the updated `create_admin.py` usage, a clarification on `uv sync --dev`, and a new "Actualizar la aplicación" section.

- [ ] **Step 1: Clarify `uv sync --dev` in the installation section**

Find this block in `README.md` (under `### 2. Instalar dependencias`):

```markdown
```bash
uv sync --dev
```
```

Replace it with:

```markdown
```bash
uv sync --dev
```

> `--dev` incluye las dependencias de prueba. En producción usa `uv sync` sin esa bandera.
```

- [ ] **Step 2: Rewrite `### Paso 1: Preparar el servidor`**

Find and replace the entire Paso 1 block. Current text starts with `### Paso 1: Preparar el servidor` and ends before `### Paso 2`. Replace it with:

```markdown
### Paso 1: Preparar el servidor

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python 3.11 si no lo tiene
sudo apt install -y python3.11 python3.11-dev

# Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Instalar Caddy
sudo apt install -y caddy

# Crear directorio de la aplicación
sudo mkdir -p /opt/dmoj-downloader
sudo chown $USER:$USER /opt/dmoj-downloader
```

### Paso 2: Crear usuario de servicio

Crea el usuario del sistema que ejecutará la aplicación. Este usuario no tiene contraseña ni acceso interactivo.

```bash
sudo useradd -r -s /bin/false dmoj-dl
```

### Paso 3: Clonar y configurar

```bash
cd /opt/dmoj-downloader
git clone https://github.com/AresLOLXD/dmoj-submission-downloader.git .

# Instalar dependencias (sin --dev en producción)
uv sync
```

### Paso 4: Configurar variables de entorno

```bash
cp .env.example .env
nano .env
```

Asegúrate de completar todos los valores, especialmente:

- `DMOJ_BASE_URL`
- `DMOJ_API_TOKEN`
- `SECRET_KEY` (generado con `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`)

Protege el archivo de secretos para que solo tu usuario pueda leerlo:

```bash
chmod 600 .env
```

### Paso 5: Crear primer administrador

```bash
cd /opt/dmoj-downloader
uv run python3 create_admin.py tu_usuario_admin
```

El script te pedirá la contraseña sin mostrarla en pantalla. Este comando:

1. Inicializa la base de datos SQLite (`dmoj_downloader.db`)
2. Crea un usuario administrador con las credenciales proporcionadas
3. Imprime un mensaje de confirmación

**Nota:** Solo puedes crear un administrador inicial con este script. Para agregar más usuarios, usa el panel de administración web después de iniciar sesión.

### Paso 6: Aplicar permisos al usuario de servicio

Transfiere la propiedad de la base de datos al usuario de servicio. El resto del código sigue siendo tuyo, lo que te permite actualizarlo sin necesitar permisos adicionales.

```bash
sudo chown dmoj-dl:dmoj-dl /opt/dmoj-downloader/dmoj_downloader.db
```

### Paso 7: Instalar servicio systemd

Copia el archivo de servicio a systemd:

```bash
sudo cp /opt/dmoj-downloader/dmoj-downloader.service /etc/systemd/system/
sudo systemctl daemon-reload
```

Inicia el servicio:

```bash
sudo systemctl start dmoj-downloader
sudo systemctl enable dmoj-downloader
```

Verifica el estado:

```bash
sudo systemctl status dmoj-downloader
```

Ver logs:

```bash
sudo journalctl -u dmoj-downloader -f
```

### Paso 8: Configurar Caddy

Edita el Caddyfile:

```bash
sudo nano /etc/caddy/Caddyfile
```

Reemplaza el contenido con:

```
tu-dominio.com {
    reverse_proxy localhost:8000
}
```

Reemplaza `tu-dominio.com` con tu dominio real.

Recarga la configuración de Caddy:

```bash
sudo systemctl reload caddy
```

Verifica que Caddy esté corriendo:

```bash
sudo systemctl status caddy
```

### Paso 9: Verificar despliegue

1. Accede a `https://tu-dominio.com` en tu navegador
2. Serás redirigido a `/login` automáticamente
3. Inicia sesión con las credenciales del administrador creado
4. Verifica que el panel de control funcione
```

- [ ] **Step 3: Add "Actualizar la aplicación" section**

Find the line `## Monitoreo en producción` and insert the following block **before** it:

```markdown
## Actualizar la aplicación

Cuando haya una nueva versión disponible:

```bash
cd /opt/dmoj-downloader
git pull
uv sync
sudo systemctl restart dmoj-downloader
```

Verifica que el servicio siga corriendo después de la actualización:

```bash
sudo systemctl status dmoj-downloader
```

```

- [ ] **Step 4: Review the full production section reads correctly**

Read the section from `## Despliegue en producción` to `## Uso` and verify:
- Steps are numbered Paso 1 through Paso 9 with no gaps.
- `useradd` appears only in Paso 2.
- `chown` for `dmoj-dl` appears only in Paso 6.
- `create_admin.py` invocation has only one argument (username).
- No old Paso 5 content (the one with `useradd` and `chown -R`) remains.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: fix deployment step order, add permissions model and update procedure"
```

---

### Task 3: Update `.env.example`

**Files:**
- Modify: `.env.example`

**Context:** `HTTPS_ONLY` is documented in the README but missing from the example file users copy. Add it with a comment.

- [ ] **Step 1: Add `HTTPS_ONLY` to `.env.example`**

Current content of `.env.example`:

```
DMOJ_BASE_URL=https://your-dmoj-instance.com
DMOJ_API_TOKEN=your_token_here
SECRET_KEY=change_this_to_a_long_random_string
LOG_LEVEL=INFO
```

Replace it with:

```
DMOJ_BASE_URL=https://your-dmoj-instance.com
DMOJ_API_TOKEN=your_token_here
SECRET_KEY=change_this_to_a_long_random_string
LOG_LEVEL=INFO
HTTPS_ONLY=true
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: add HTTPS_ONLY to .env.example"
```

---

### Task 4: Security review of permission model

**Subagent:** `voltagent-qa-sec:security-auditor`  
**Runs after:** Tasks 1, 2, and 3 are all committed.

**Context for the reviewer:** This app runs as a systemd service under the `dmoj-dl` system user (no shell, no login). The permission model after deployment is:

- `/opt/dmoj-downloader/` — owned by the deploy user, world-readable (default 755/644)
- `/opt/dmoj-downloader/.env` — owned by deploy user, mode 600 (secrets)
- `/opt/dmoj-downloader/dmoj_downloader.db` — owned by `dmoj-dl`, default mode (644 initially, but chowned)
- `.venv/bin/uvicorn` — world-executable (755), owned by deploy user
- systemd `EnvironmentFile` reads `.env` as root before dropping privileges to `dmoj-dl`
- systemd hardening: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome`, `ReadWritePaths=/opt/dmoj-downloader`, `CapabilityBoundingSet=`

**Review questions to address:**
1. Can `dmoj-dl` read `.env` directly (e.g., via `/proc/self/environ` or file access)? Is that a concern?
2. Is world-readable code in `/opt/dmoj-downloader` a risk on a single-purpose VPS?
3. Does `chmod 600 .env` adequately protect the secrets given that systemd reads it as root?
4. Is the `dmoj_downloader.db` permission model (owned by `dmoj-dl`, default mode) correct? Should it be `600` instead of `644`?
5. Any other risks in the deployment model described in `README.md` and `dmoj-downloader.service`?

- [ ] **Step 1: Run security review**

Dispatch `voltagent-qa-sec:security-auditor` with the context above plus the content of `dmoj-downloader.service` and the updated `README.md` production section.

- [ ] **Step 2: Apply any findings**

If the reviewer flags issues (e.g., DB should be `chmod 600`, or `.env` needs a different approach), update `README.md` accordingly and commit.

```bash
git add README.md
git commit -m "docs: apply security review findings to deployment guide"
```
