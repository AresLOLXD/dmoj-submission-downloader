# DMOJ Submission Downloader

Una aplicación web FastAPI que permite a delegados autenticados descargar todos los envíos de un concurso DMOJ auto-hospedado como un archivo ZIP en streaming. Los administradores gestionan cuentas de usuario a través de un panel web.

## Requisitos

- Python 3.11 o superior
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (gestor de paquetes y entornos virtuales)
- SQLite 3 (incluido en Python)
- Un reverse proxy para producción (se recomienda [Caddy](https://caddyserver.com/) por su configuración simple y TLS automático, pero cualquier otro como nginx o Traefik funciona)
- Acceso a una instancia DMOJ auto-hospedada con token API válido

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/AresLOLXD/dmoj-submission-downloader.git
cd dmoj-downloader
```

### 2. Instalar dependencias

Requiere [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync --dev
```

> `--dev` incluye las dependencias de prueba. En producción usa `uv sync` sin esa bandera.

## Configuración

### Variables de entorno

Copia el archivo `.env.example` a `.env` y completa los valores:

```bash
cp .env.example .env
```

Edita `.env` con tus valores:

```
DMOJ_BASE_URL=https://tu-instancia-dmoj.com
DMOJ_API_TOKEN=tu_token_aqui
SECRET_KEY=una_cadena_larga_aleatoria_muy_segura
LOG_LEVEL=INFO
```

**Descripción de variables:**

- `DMOJ_BASE_URL`: URL completa de tu instancia DMOJ (sin barra final). Ejemplo: `https://dmoj.example.com`
- `DMOJ_API_TOKEN`: Token de API válido de DMOJ con permisos para acceder a participantes y envíos de concursos
- `SECRET_KEY`: Cadena aleatoria larga para firmar sesiones. Genérala con:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- `LOG_LEVEL`: Nivel de registro (por defecto `INFO`). Opciones: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- `HTTPS_ONLY`: (opcional) Si es `true` (por defecto), las cookies de sesión requieren HTTPS. Usa `false` solo en desarrollo local

## Bootstrap: Crear primer administrador

Después de configurar las variables de entorno, crea la base de datos y el usuario administrador inicial:

```bash
uv run python3 create_admin.py nombre_usuario
```

Ejemplo:

```bash
uv run python3 create_admin.py admin
```

El script te pedirá la contraseña sin mostrarla en pantalla. Este comando:

1. Inicializa la base de datos SQLite (`dmoj_downloader.db`)
2. Crea un usuario administrador con las credenciales proporcionadas
3. Imprime un mensaje de confirmación

**Nota:** Solo puedes crear un administrador inicial con este script. Para agregar más usuarios, usa el panel de administración web después de iniciar sesión.

## Desarrollo local

### Ejecutar el servidor

```bash
uv run uvicorn app.main:app --reload
```

El servidor estará disponible en `http://localhost:8000`.

### Acceder a la aplicación

1. Abre tu navegador en `http://localhost:8000`
2. Se redirige automáticamente a `/login`
3. Inicia sesión con el usuario administrador que creaste
4. Verás el panel de control con la opción de descargar concursos

### Rutas principales

**Autenticación:**

- `GET /login` - Página de inicio de sesión
- `POST /login` - Procesa el formulario de inicio de sesión
- `POST /logout` - Cierra la sesión
- `GET /health` - Estado de salud del servidor (no requiere autenticación)

**Usuarios (delegados y administradores):**

- `GET /` - Redirige a `/dashboard`
- `GET /dashboard` - Panel de control (requiere autenticación)
- `GET /download?slug=nombre-concurso` - Descarga ZIP del concurso en streaming (requiere autenticación)

**Administración (solo administradores):**

- `GET /admin` - Panel de administración
- `POST /admin/users` - Crear nuevo usuario (delegado o administrador)
- `POST /admin/users/{user_id}/toggle` - Activar/desactivar una cuenta
- `POST /admin/users/{user_id}/reset-password` - Cambiar contraseña de un usuario

## Despliegue en producción

### Estructura del despliegue

El despliegue en producción utiliza:

- **Uvicorn** como servidor ASGI (escuchando en `127.0.0.1:8000`)
- **systemd** como gestor de servicios (reinicio automático en fallos)
- **Un reverse proxy** para exponer la aplicación al exterior y terminar TLS. Las instrucciones usan Caddy por su simplicidad, pero puedes usar nginx, Traefik o cualquier otro

### Paso 1: Preparar el servidor

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python 3.11 si no lo tiene
sudo apt install -y python3.11 python3.11-dev
python3.11 --version

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

Verifica que la base de datos fue creada correctamente:

```bash
ls /opt/dmoj-downloader/dmoj_downloader.db
```

Si el archivo existe, continúa:

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

## Uso

### Descargar concursos (usuarios delegados)

1. Inicia sesión con una cuenta de delegado
2. En el panel de control, ingresa el slug del concurso (ejemplo: `icpc2024`)
3. Haz clic en "Descargar"
4. Se genera un archivo ZIP con todos los envíos en streaming
5. El ZIP incluye envíos organizados por usuario y problema, con marcas de tiempo

Estructura del ZIP descargado:

```
nombre-concurso.zip
├── usuario1/
│   ├── problema_a/
│   │   ├── 1_usuario1_2024-01-15_14-30-45_AC.py
│   │   └── 2_usuario1_2024-01-15_14-35-20_WA.py
│   └── problema_b/
│       └── 1_usuario1_2024-01-15_15-10-00_AC.cpp
└── usuario2/
    └── problema_a/
        └── 1_usuario2_2024-01-15_13-45-30_AC.java
```

### Panel de administración

1. Inicia sesión como administrador
2. Accede a `/admin` (enlace visible en la barra de navegación)
3. Gestiona usuarios:
   - Ver lista completa de usuarios
   - Crear nuevos usuarios (delegados o administradores)
   - Cambiar contraseñas
   - Activar/desactivar cuentas

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

## Monitoreo en producción

### Verificar estado del servicio

```bash
sudo systemctl status dmoj-downloader
```

### Ver logs en tiempo real

```bash
sudo journalctl -u dmoj-downloader -f
```

### Ver logs de un período específico

```bash
sudo journalctl -u dmoj-downloader --since "2 hours ago"
```

### Verifica la conectividad con DMOJ

```bash
curl https://tu-instancia-dmoj.com/api/
```

### Verifica que el endpoint de salud responda

```bash
curl https://tu-dominio.com/health
```

## Solución de problemas

### El servicio no inicia

```bash
sudo journalctl -u dmoj-downloader -n 50
```

Causas comunes:

- **Variables de entorno no definidas:** Verifica que `/opt/dmoj-downloader/.env` exista con todos los valores requeridos
- **Permisos incorrectos:** Asegúrate de que el usuario `dmoj-dl` tiene permisos de lectura/escritura en `/opt/dmoj-downloader`
- **Puerto 8000 en uso:** Cambia el puerto en `/etc/systemd/system/dmoj-downloader.service` y recarga con `sudo systemctl daemon-reload`

### No puedo conectarme a DMOJ

- Verifica `DMOJ_BASE_URL` en `.env` (sin barra final)
- Verifica que `DMOJ_API_TOKEN` sea válido
- Comprueba la conectividad con: `curl https://tu-instancia-dmoj.com/api/`
- Verifica que la instancia DMOJ esté en línea y accesible desde el servidor

### Caddy no obtiene certificado TLS

```bash
sudo systemctl restart caddy
sudo journalctl -u caddy -n 50
```

Asegúrate de que:

- El dominio apunta correctamente a la dirección IP del servidor (verifica con `nslookup tu-dominio.com`)
- El puerto 443 está abierto y accesible desde internet
- El puerto 80 está abierto para validación ACME
- El servidor no tiene un cortafuegos bloqueando estos puertos

### Descarga de concurso no comienza

1. Verifica que el slug sea válido (solo alfanuméricos, guiones y guiones bajos)
2. Asegúrate de que el concurso existe en DMOJ
3. Verifica logs: `sudo journalctl -u dmoj-downloader -f`
4. Comprueba permisos del token API de DMOJ

### Problemas de rendimiento en descargas grandes

- La descarga es en streaming, por lo que no debería consumir memoria significativa
- Si la descarga es muy lenta, verifica la conectividad entre el servidor y DMOJ
- Consulta los logs para errores de conexión a la API

## Licencia

Ver LICENSE para detalles.
