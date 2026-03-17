El bot corre en render y se mantiene activo gracias a una petición al sitio web
https://s4vi-bot-8h1b.onrender.com (pueden revisar estadisticas de consumo de recursos) que le llega cada 5 minutos con por parte de uptime robot
tiene que crear un .env con el token del bot.

Nota (Render/Discord): si ocurre un bloqueo temporal o error transitorio al conectar (por ejemplo, Cloudflare 1015), el proceso no termina; mantiene el endpoint web activo y reintenta la conexión a Discord con backoff.

La ruta principal `/` del `keep_alive.py` devuelve estado y métricas reales en JSON:
- `estado`: confirma que el bot está en línea.
- `actualizado_en`: timestamp UTC del muestreo.
- `actualizado_en_12h`: hora local legible en formato 12h con AM/PM.
- `metricas.cpu`:
  - `uso`: porcentaje de CPU.
  - `carga`: promedio de carga (1m/5m/15m) cuando el host lo soporta.
- `metricas.ram`:
  - `usada`, `total`, `libre`, `porcentaje_usado`.
- `metricas.almacenamiento`:
  - `usado`, `total`, `libre`, `porcentaje_usado`.

Notas de optimización del endpoint:
- Se removió por completo la métrica de GPU.
- Se usa caché corta de métricas para reducir lecturas frecuentes de sistema.
- Se ejecuta limpieza segura periódica de artefactos temporales de Python (`__pycache__`, `*.pyc`, `*.pyo`) fuera de `.venv` y `.git`.

EJEMPLO DE .env
#api del bot del discord
DISCORD_TOKEN=TOKEN_DEL_BOT
#id del grupo
GUILD_ID=ID_DEL_SERVIDOR
#nivel de logs (opcional): DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
#contraseña de bypass para /tareas nuevas (opcional)
TAREAS_NUEVAS_BYPASS_PASSWORD=00923
#usuario y contraseña para acceder a CVIRTUAL
CVIRTUAL_USER=USUARIO_CVIRTUAL
CVIRTUAL_PASSWORD=CLAVE_CVIRTUAL
#cookie opcional para cursos privados (Moodle)
#CVIRTUAL_COOKIE=MoodleSession=...; other_cookie=...
#también acepta solo el valor de sesión, ej: CVIRTUAL_COOKIE=abc123...

### CAMBIAR LA MENCION DE LOS DEL GRUPO CON everyone

## ESTRUCTURA DEL PROYECTO
- **cogs/**: Comandos y eventos del bot.
  - `deliveries.py`
  - `enrollment.py`
  - `help.py`
  - `reminders.py`
  - `tasks.py`
  - `course_watcher.py`
- **database/**: Gestión de datos.
  - `db_handler.py`
  - `bot.db`
- **utils/**: Configuraciones y embeds.
  - `config.py`
  - `embeds.py`
- `main.py`: Punto de entrada del bot.
- `keep_alive.py`: Servidor web para uptime.
- `.env`: Variables de entorno.
- `requirements.txt`: Dependencias del proyecto.
- `estructura-discord.md`: Guía de la estructura del servidor.

## MONITOREO DE CURSOS (NUEVO)
- El cog `course_watcher.py` revisa cursos de CVIRTUAL y detecta actividades de tipo **Foro** y **Tarea**.
- Extrae curso, semana, tipo, título, enlace y fecha de entrega/cierre (cuando Moodle la muestra).
- Guarda un hash en SQLite para no repetir notificaciones.
- Publica novedades en el canal de avisos de tareas.
- Si detecta una **TAREA** o **FORO** nuevo, lo registra automáticamente como tarea en el canal de materia correspondiente.
- Si la tarea ya existe, no la duplica y solo la reporta al usuario que ejecutó el comando.
- Si la información cambia en CVIRTUAL (fecha, título o materia), actualiza la tarea existente y sus mensajes en Discord.
- La no-duplicación se realiza por materia+título normalizado.
- Los títulos largos de tareas se aceptan; el sistema recorta solo para visualización cuando aplica.
- Las tareas auto-programadas incluyen el link de origen de CVIRTUAL en el embed.
- Las tareas auto-programadas incluyen también las indicaciones extraídas desde la página de la tarea.
- Los avisos de actividad y las tareas usan formato detallado consistente (Título, Materia, Entrega, Fuente, Indicaciones cuando existan).
- Cada publicación automática por canal se envía con intervalo de 30 segundos para evitar ráfagas.
- Horarios automáticos (`America/El_Salvador`):
  - Lunes 06:00
  - Jueves 18:00
  - Sábado 21:00
- Comando manual: `/tareas nuevas [semana]`
  - Límite global: 2 usos por día (todos los usuarios).
  - Bypass del límite: `contrasena=00923`.
  - Si se especifica `semana`, escanea esa semana exacta (ej. 8).
  - Si no se especifica, escanea la semana más reciente disponible del curso.
  - Prioriza semanas desde la 8 en adelante cuando existen.
  - Los avisos automáticos usan mención `@everyone`.
