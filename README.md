El bot corre en render y se mantiene activo gracias a una petición al sitio web
https://s4vi-bot.onrender.com que le llega cada 5 minutos con por parte de uptime robot
tiene que crear un .env con el token del bot.

La ruta principal `/` del `keep_alive.py` ahora devuelve un estado minimalista en JSON:
- `status`: confirma que el bot está en línea.
- `metrics.ram`: uso de RAM.
- `metrics.gpu`: uso de GPU (si no está disponible en el host, responde `N/D`).
- `metrics.storage`: uso de almacenamiento del disco.

EJEMPLO DE .env
#api del bot del discord
DISCORD_TOKEN=TOKEN_DEL_BOT
#id del grupo
GUILD_ID=ID_DEL_SERVIDOR
#usuario y contraseña para acceder a CVIRTUAL
CVIRTUAL_USER=USUARIO_CVIRTUAL
CVIRTUAL_PASSWORD=CLAVE_CVIRTUAL
#cookie opcional para cursos privados (Moodle)
#CVIRTUAL_COOKIE=MoodleSession=...; other_cookie=...

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
- Si detecta una **TAREA** nueva, la programa automáticamente en el canal de materia correspondiente.
- Si la tarea ya existe, no la duplica y solo la reporta al usuario que ejecutó el comando.
- Si la información cambia en CVIRTUAL (fecha, título o materia), actualiza la tarea existente y sus mensajes en Discord.
- La no-duplicación se refuerza con `source_url` de la tarea, además de validación por materia+título.
- Los títulos largos de tareas se aceptan; el sistema recorta solo para visualización cuando aplica.
- Las tareas auto-programadas incluyen el link de origen de CVIRTUAL en el embed.
- Las tareas auto-programadas incluyen también las indicaciones extraídas desde la página de la tarea.
- Horarios automáticos (`America/El_Salvador`):
  - Lunes 06:00
  - Miércoles 18:00
  - Viernes 23:00
- Comando manual: `/tareas nuevas [semana]`
  - Cooldown: 1 uso cada 30 minutos por servidor.
  - Si se especifica `semana`, escanea esa semana exacta (ej. 8).
  - Si no se especifica, escanea la semana más reciente disponible del curso.
  - Prioriza semanas desde la 8 en adelante cuando existen.
