# deliveries.py - Gestión de entregas de tareas
import discord
from discord import app_commands
from discord.ext import commands
from utils.config import SUBJECTS, CHANNELS
from utils.embeds import create_success_embed, create_error_embed
import datetime

class Deliveries(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Registrar la entrega de una tarea por parte de un usuario
    @app_commands.command(name="completar-tarea", description="Marcar una tarea como completada")
    @app_commands.describe(
        materia="Materia de la tarea",
        tarea="ID o nombre de la tarea específica"
    )
    async def tarea_entregada(self, interaction: discord.Interaction, materia: str, tarea: str):
        # Validar restricción de canal
        channel_name = interaction.channel.name
        expected = CHANNELS["DELIVERED"]
        
        if channel_name != expected and channel_name.replace(" ", "-") != expected.replace(" ", "-"):
            target = discord.utils.get(interaction.guild.channels, name=expected)
            await interaction.response.send_message(
                f"Use este comando en <#{target.id if target else 'entregadas'}>", 
                ephemeral=True
            )
            return

        from utils.config import SUBJECTS_MAP
        internal_subject = SUBJECTS_MAP.get(materia, materia)
        tasks = self.bot.db.get_tasks(interaction.guild.id)
        target_task = None

        # Extraer el ID de la tarea del input
        if tarea.isdigit():
            tid = int(tarea)
            target_task = next((t for t in tasks if t[0] == tid), None)
        
        if not target_task:
            await interaction.response.send_message(create_error_embed("Tarea no encontrada."), ephemeral=True)
            return

        # Registrar entrega en la base de datos
        self.bot.db.mark_as_delivered(target_task[0], interaction.user.id, interaction.guild.id)

        # Confirmar éxito
        embed = create_success_embed(f"Tarea **{target_task[2]}** marcada como entregada.")
        embed.set_footer(text=f"Usuario: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    # Autocompletado para materias
    @tarea_entregada.autocomplete('materia')
    async def materia_autocomplete(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=s, value=s) for s in SUBJECTS if current.lower() in s.lower()][:25]

    # Autocompletado para tareas basado en la materia seleccionada
    @tarea_entregada.autocomplete('tarea')
    async def tarea_autocomplete(self, interaction: discord.Interaction, current: str):
        materia_sel = interaction.namespace.materia
        from utils.config import SUBJECTS_MAP
        internal_subject = SUBJECTS_MAP.get(materia_sel, "")
        
        tasks = self.bot.db.get_tasks(interaction.guild.id)
        choices = []
        for t in tasks:
            if internal_subject and t[1] != internal_subject:
                continue
            
            label = f"#{t[0]} - {t[2]}"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=str(t[0])))
        return choices[:25]

async def setup(bot):
    await bot.add_cog(Deliveries(bot))
