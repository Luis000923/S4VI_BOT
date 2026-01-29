import discord
from discord import app_commands
from discord.ext import commands
from utils.config import ROLES, CHANNELS
from utils.embeds import create_success_embed

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ayuda", description="Muestra la lista de comandos disponibles y cómo usarlos")
    async def ayuda(self, interaction: discord.Interaction):
        user_roles = [role.name.lower() for role in interaction.user.roles]
        is_staff = ROLES["ADMIN"].lower() in user_roles or ROLES["DELEGADO"].lower() in user_roles

        embed = discord.Embed(
            title="📚 Guía de Comandos - S4VI_BOT",
            description="Bienvenido al sistema de gestión académica. Aquí tienes los comandos disponibles:",
            color=0x3498db
        )

        # Comandos para Estudiantes
        student_cmds = (
            "**/mis-tareas**\nVer tus tareas próximas que aún no has entregado.\n\n"
            "**/inscribirme** `[materias]`\nSelecciona las materias de las que quieres recibir recordatorios.\n*Ejemplo: /inscribirme materias: Matemática, Programación*\n\n"
            "**/completar-tarea** `[materia]` `[tarea]`\nMarca una tarea como entregada para dejar de recibir alertas.\n*Uso: Solo en #📄-tareas-entregadas*"
        )
        embed.add_field(name="🎓 Para Estudiantes", value=student_cmds, inline=False)

        # Comandos para Staff
        if is_staff:
            staff_cmds = (
                "**/crear-tarea** `[materia]` `[titulo]` `[fecha]`\nCrea una nueva tarea para todos.\n*Uso: Solo en #📄-tareas-pendientes*\n\n"
                "**!sync**\n(Opcional) Fuerza la sincronización de comandos si no aparecen."
            )
            embed.add_field(name="🛡️ Para Admin/Delegados", value=staff_cmds, inline=False)

        embed.set_footer(text="S4VI_BOT - Gestión Académica Eficiente")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Mensaje de bienvenida en el canal general
        channel = discord.utils.get(member.guild.channels, name=CHANNELS["WELCOME"])
        if channel:
            embed = discord.Embed(
                title=f"¡Bienvenido/a {member.display_name}! 👋",
                description=(
                    f"Hola {member.mention}, bienvenido al servidor académico del **Ciclo 1**.\n\n"
                    "Para empezar, usa el comando `/ayuda` para ver lo que puedo hacer por ti.\n"
                    "No olvides inscribirte a tus materias con `/inscribir` para recibir recordatorios personalizados."
                ),
                color=0x2ecc71
            )
            await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
