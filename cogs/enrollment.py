# enrollment.py - Gestión de inscripciones a materias
import discord
from discord import app_commands
from discord.ext import commands
from utils.config import SUBJECTS
from utils.embeds import create_success_embed, create_error_embed

class Enrollment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Permitir a los usuarios seleccionar materias para recibir notificaciones
    @app_commands.command(name="inscribirme", description="Seleccionar materias para recibir notificaciones")
    @app_commands.describe(materias="Materias que cursa (use 'Todas' para todas)")
    async def inscribirme(self, interaction: discord.Interaction, materias: str = None):
        from utils.config import SUBJECTS_MAP
        
        # Manejar entrada vacía o selección masiva
        if materias is None or materias == "Todas las materias":
            valid_subjects = [SUBJECTS_MAP[s] for s in SUBJECTS]
            invalid_subjects = []
            msg_header = "Te has inscrito en **TODAS** las materias."
        else:
            # Procesar entrada separada por comas
            input_subjects = [s.strip() for s in materias.split(",")]
            valid_subjects = []
            invalid_subjects = []

            for s in input_subjects:
                if s in SUBJECTS:
                    valid_subjects.append(SUBJECTS_MAP[s])
                else:
                    # Alternativa: coincidencia por nombre interno
                    match = next((subj for label, subj in SUBJECTS_MAP.items() if subj.lower() == s.lower()), None)
                    if match:
                        valid_subjects.append(match)
                    else:
                        invalid_subjects.append(s)
            
            msg_header = f"Inscrito en: **{', '.join(valid_subjects)}**."

        if not valid_subjects:
            await interaction.response.send_message(create_error_embed("No se reconocieron las materias proporcionadas."), ephemeral=True)
            return

        # Actualizar registros de inscripción en la base de datos
        self.bot.db.set_enrollments(interaction.user.id, valid_subjects, interaction.guild.id)

        msg = msg_header
        if invalid_subjects:
            msg += f"\n*(Materias no definidas: {', '.join(invalid_subjects)})*"
        
        msg += "\n\nPreferencias de notificación actualizadas correctamente."
        await interaction.response.send_message(embed=create_success_embed(msg), ephemeral=True)

    # Autocompletado para materias incluyendo opción masiva
    @inscribirme.autocomplete('materias')
    async def materias_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = ["Todas las materias"] + SUBJECTS
        return [app_commands.Choice(name=c, value=c) for c in choices if current.lower() in c.lower()][:25]

async def setup(bot):
    await bot.add_cog(Enrollment(bot))
