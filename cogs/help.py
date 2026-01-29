# help.py - Comando de ayuda y eventos de unión de miembros
import discord
from discord import app_commands
from discord.ext import commands
from utils.config import ROLES, CHANNELS
from utils.embeds import create_success_embed

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Muestra los comandos disponibles basados en los permisos del usuario
    @app_commands.command(name="ayuda", description="Muestra los comandos disponibles y la guía de uso")
    async def ayuda(self, interaction: discord.Interaction):
        user_roles = [role.name.lower() for role in interaction.user.roles]
        is_staff = ROLES["ADMIN"].lower() in user_roles or ROLES["DELEGADO"].lower() in user_roles

        embed = discord.Embed(
            title="📚 Guía de Comandos - S4VI_BOT",
            description="Sistema de gestión académica. Comandos disponibles:",
            color=0x3498db
        )

        # Comandos para Estudiantes
        student_cmds = (
            "**/mis-tareas**\nLista de tareas próximas no entregadas.\n\n"
            "**/inscribirme** `[materias]`\nSuscripción a materias para recibir recordatorios.\n*Uso: /inscribirme materias: Matemática, Programación*\n\n"
            "**/completar-tarea** `[materia]` `[tarea]`\nRegistrar entrega de tarea.\n*Uso: Se debe ejecutar en el canal de entregas*"
        )
        embed.add_field(name="🎓 Estudiantes", value=student_cmds, inline=False)

        # Comandos para Personal Administrativo
        if is_staff:
            staff_cmds = (
                "**/crear-tarea** `[materia]` `[titulo]` `[fecha]`\nCreación de nuevas tareas.\n\n"
                "**/editar-tarea** `[id]` `[titulo]` `[fecha]`\nModificación de tareas existentes.\n\n"
                "**/eliminar-tarea** `[id]`\nEliminación permanente de registros.\n\n"
                "**!sync**\nSincronización manual de la interfaz de comandos."
            )
            embed.add_field(name="🛡️ Administración / Delegados", value=staff_cmds, inline=False)

        embed.set_footer(text="S4VI_BOT - Gestión Académica")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Escuchador de eventos para nuevas llegadas de miembros
    @commands.Cog.listener()
    async def on_member_join(self, member):
        # Enviar mensaje de bienvenida al canal designado
        channel = discord.utils.get(member.guild.channels, name=CHANNELS["WELCOME"])
        if channel:
            embed = discord.Embed(
                title=f"Bienvenido/a {member.display_name} 👋",
                description=(
                    f"Hola {member.mention}, se ha unido al servidor académico.\n\n"
                    "Utilice el comando `/ayuda` para conocer las funciones disponibles.\n"
                    "Configure sus materias con `/inscribirme` para recibir notificaciones."
                ),
                color=0x2ecc71
            )
            await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
