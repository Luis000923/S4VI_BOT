# main.py - Punto de entrada para el Bot de Discord
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from database.db_handler import DatabaseHandler
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

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

bot = S4VIBot()

# Comando administrativo para sincronización manual
@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("Sincronización completada.")

if __name__ == "__main__":
    if not TOKEN:
        print("FATA: DISCORD_TOKEN no definido en variables de entorno.")
        exit(1)
    
    try:
        # Iniciar servicio para mantener el bot activo
        print("Iniciando servidor web (keep_alive)...")
        keep_alive()
        print("Servidor web activo.")
        
        # Ejecución del bot
        print("Conectando a Discord...")
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("\nBot detenido por usuario.")
    except Exception as e:
        print(f"ERROR CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
