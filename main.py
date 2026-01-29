import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from database.db_handler import DatabaseHandler
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Configuracion base del bot
class S4VIBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = DatabaseHandler()

    async def setup_hook(self):
        # Carga los archivos de la carpeta /cogs
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
        
        # Sincroniza los comandos slash con el servidor
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            try:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"🚀 Comandos sincronizados para el server {guild_id}")
            except Exception as e:
                print(f"⚠️ Error al sincronizar: {e}")
        else:
            print("ℹ️ No hay GUILD_ID. Los comandos tardaran en aparecer.")

    async def on_ready(self):
        print(f"✅ Bot listo: {self.user}")
        print("------")

bot = S4VIBot()

# Comando manual por si no salen los slash commands
@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("Sincronizado.")

if __name__ == "__main__":
    if not TOKEN:
        print("Falta el TOKEN en el .env")
    else:
        # Arrancamos el servidor web para que no se apague
        keep_alive()
        # Arranca el bot
        bot.run(TOKEN)
