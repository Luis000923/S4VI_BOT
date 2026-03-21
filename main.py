# main.py - Punto de entrada para el Bot de Discord
import discord
from discord.ext import commands
import os
import random
import time
import logging
import sys
import asyncio
from dotenv import load_dotenv
from database.db_handler import DatabaseHandler
from keep_alive import keep_alive

load_dotenv()
TOKEN = (os.getenv("DISCORD_TOKEN") or "").strip()

logger = logging.getLogger("s4vi")


def _configure_logging():
    level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _configure_global_exception_hooks():
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Excepción no controlada en proceso principal", exc_info=(exc_type, exc_value, exc_traceback))

    def handle_async_exception(loop, context):
        message = context.get("message", "Excepción no controlada en loop asyncio")
        exception = context.get("exception")
        if exception is not None:
            logger.error(message, exc_info=exception)
        else:
            logger.error("%s | contexto=%s", message, context)

    sys.excepthook = handle_exception
    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_async_exception)
    except Exception:
        logger.exception("No se pudo configurar el handler global de asyncio")

# Clase de configuración del bot
class S4VIBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = DatabaseHandler()

    async def setup_hook(self):
        # Carga de extensiones (cogs) desde el directorio correspondiente
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    logger.info("Cog cargado: %s", filename)
                except Exception as e:
                    logger.exception("Error cargando cog %s: %s", filename, e)
                    # No tumbar el bot, solo registrar el error
        
        logger.info("Setup completado. Sincronización de startup desactivada por defecto.")
        logger.info("Usa el comando !sync solo cuando necesites actualizar slash commands.")

    async def on_ready(self):
        logger.info("Sesión iniciada como: %s", self.user)

    async def on_disconnect(self):
        logger.warning("Discord gateway desconectado")

    async def on_resumed(self):
        logger.info("Discord gateway reanudado")

    async def on_error(self, event_method, *args, **kwargs):
        logger.exception("Error global en evento Discord: %s", event_method)


def build_bot() -> S4VIBot:
    bot = S4VIBot()

    # Comando administrativo para sincronización manual
    @bot.command()
    @commands.has_permissions(administrator=True)
    async def sync(ctx):
        await bot.tree.sync()
        await ctx.send("Sincronización completada.")

    return bot

if __name__ == "__main__":
    _configure_logging()
    _configure_global_exception_hooks()
    # Iniciar servicio web siempre, aunque Discord falle, para evitar 502/restarts.
    logger.info("Iniciando servidor web (keep_alive)...")
    try:
        keep_alive()
        logger.info("Servidor web activo")
    except Exception as e:
        logger.exception("ADVERTENCIA: keep_alive falló: %s", e)

    if not TOKEN:
        logger.critical("FATAL: DISCORD_TOKEN no definido en variables de entorno")
        logger.critical("Manteniendo el proceso vivo para evitar reinicios; configura la variable y redeploy")
        while True:
            time.sleep(3600)

    attempt = 0
    while True:
        try:
            attempt += 1
            if attempt == 1:
                logger.info("Conectando a Discord...")
            else:
                logger.warning("Reintentando conexión a Discord (intento %s)...", attempt)

            bot = build_bot()

            # Bloqueante; si sale por error, lo capturamos y reintentamos con backoff.
            bot.run(TOKEN, reconnect=True, log_handler=None)
            logger.warning("Discord bot finalizó (bot.run retornó). Reintentando en 15s...")
            time.sleep(15)
            continue
        except KeyboardInterrupt:
            logger.info("Bot detenido por usuario")
            break
        except discord.LoginFailure as e:
            logger.critical("FATAL: LoginFailure (token inválido o revocado): %s", e)
            logger.critical("No se reintentará automáticamente. Manteniendo el proceso vivo")
            while True:
                time.sleep(3600)
        except Exception as e:
            # Backoff exponencial con jitter para no agravar rate limits (p. ej. Cloudflare 1015).
            backoff_base = min(300, 2 ** min(attempt, 8))
            jitter = random.uniform(0, backoff_base * 0.25)
            sleep_s = backoff_base + jitter

            logger.exception("ERROR ejecutando/conectando el bot: %s", e)
            logger.warning("Esperando %.1fs antes de reintentar...", sleep_s)
            time.sleep(sleep_s)
