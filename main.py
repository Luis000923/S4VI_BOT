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
                await self.load_extension(f"cogs.{filename[:-3]}")
        
        # Sincronización de comandos de barra (slash commands) con el servidor especificado
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            try:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"Comandos sincronizados para el servidor: {guild_id}")
            except Exception as e:
                print(f"Error de sincronización: {e}")
        else:
            print("No se especificó GUILD_ID. Los comandos podrían tardar en propagarse.")

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
        print("Falta DISCORD_TOKEN en las variables de entorno.")
    else:
        # Iniciar servicio para mantener el bot activo
        keep_alive()
        # Ejecución del bot
        bot.run(TOKEN)
