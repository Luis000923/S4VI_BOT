# main.py - Punto de entrada para el Bot de Discord
import discord
from discord.ext import commands
import os
import random
import time
import logging
from dotenv import load_dotenv
from database.db_handler import DatabaseHandler
from keep_alive import keep_alive

load_dotenv()
TOKEN = (os.getenv("DISCORD_TOKEN") or "").strip()


def _configure_logging():
    level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

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
                    print(f"✓ Cog cargado: {filename}")
                except Exception as e:
                    print(f"✗ Error cargando cog {filename}: {e}")
                    # No tumbar el bot, solo registrar el error
        
        print("✓ Setup completado. Sincronización de startup desactivada por defecto.")
        print("  Usa el comando !sync solo cuando necesites actualizar slash commands.")

    async def on_ready(self):
        print(f"Sesión iniciada como: {self.user}")
        print("------")


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
    # Iniciar servicio web siempre, aunque Discord falle, para evitar 502/restarts.
    print("Iniciando servidor web (keep_alive)...")
    try:
        keep_alive()
        print("Servidor web activo.")
    except Exception as e:
        print(f"ADVERTENCIA: keep_alive falló: {e}")
        import traceback

        traceback.print_exc()

    if not TOKEN:
        print("FATAL: DISCORD_TOKEN no definido en variables de entorno.")
        print("Manteniendo el proceso vivo para evitar reinicios; configura la variable y redeploy.")
        while True:
            time.sleep(3600)

    attempt = 0
    while True:
        try:
            attempt += 1
            if attempt == 1:
                print("Conectando a Discord...")
            else:
                print(f"Reintentando conexión a Discord (intento {attempt})...")

            bot = build_bot()

            # Bloqueante; si sale por error, lo capturamos y reintentamos con backoff.
            bot.run(TOKEN, reconnect=True, log_handler=None)
            print("Discord bot finalizó (bot.run retornó). Reintentando en 15s...")
            time.sleep(15)
            continue
        except KeyboardInterrupt:
            print("\nBot detenido por usuario.")
            break
        except discord.LoginFailure as e:
            print(f"FATAL: LoginFailure (token inválido o revocado): {e}")
            print("No se reintentará automáticamente. Manteniendo el proceso vivo.")
            while True:
                time.sleep(3600)
        except Exception as e:
            # Backoff exponencial con jitter para no agravar rate limits (p. ej. Cloudflare 1015).
            backoff_base = min(300, 2 ** min(attempt, 8))
            jitter = random.uniform(0, backoff_base * 0.25)
            sleep_s = backoff_base + jitter

            print(f"ERROR ejecutando/conectando el bot: {e}")
            import traceback

            traceback.print_exc()
            print(f"Esperando {sleep_s:.1f}s antes de reintentar...")
            time.sleep(sleep_s)
