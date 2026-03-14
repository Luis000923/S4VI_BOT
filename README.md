El bot corre en render y se mantiene activo gracias a una petición al sitio web
https://s4vi-bot.onrender.com que le llega cada 5 minutos con por parte de uptime robot
tiene que crear un .env con el token del bot.

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
- Extrae curso, semana, tipo, título y enlace.
- Guarda un hash en SQLite para no repetir notificaciones.
- Publica novedades en el canal de avisos de tareas.
- Horarios automáticos (`America/El_Salvador`):
  - Lunes 06:00
  - Miércoles 18:00
  - Viernes 23:00
- Comando manual: `/tareas nuevas`
