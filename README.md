El bot corre en render y se mantiene activo gracias a una petición al sitio web
https://s4vi-bot.onrender.com que le llega cada 5 minutos con por parte de uptime robot
tiene que crear un .env con el token del bot.

EJEMPLO DE .env
#api del bot del discord
DISCORD_TOKEN=TOKEN_DEL_BOT
#id del grupo
GUILD_ID=ID_DEL_SERVIDOR

### CAMBIAR LA MENCION DE LOS DEL GRUPO CON everyone

## ESTRUCTURA DEL PROYECTO
- **cogs/**: Comandos y eventos del bot.
  - `deliveries.py`
  - `enrollment.py`
  - `help.py`
  - `reminders.py`
  - `tasks.py`
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
