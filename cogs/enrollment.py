import discord
from discord import app_commands
from discord.ext import commands
from utils.config import SUBJECTS
from utils.embeds import create_success_embed, create_error_embed

class Enrollment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Para que el usuario elija sus materias
    @app_commands.command(name="inscribirme", description="Elige tus materias para recibir avisos")
    @app_commands.describe(materias="Cuales materias llevas? (Puedes elegir 'Todas')")
    async def inscribirme(self, interaction: discord.Interaction, materias: str = None):
        from utils.config import SUBJECTS_MAP
        
        # Si no pone nada o pone "Todas", se le inscriben todas
        if materias is None or materias == "Todas las materias":
            valid_subjects = [SUBJECTS_MAP[s] for s in SUBJECTS]
            invalid_subjects = []
            msg_header = "Te inscribiste en **TODAS** las materias."
        else:
            # Separa por comas si el usuario escribio varias
            input_subjects = [s.strip() for s in materias.split(",")]
            valid_subjects = []
            invalid_subjects = []

            for s in input_subjects:
                if s in SUBJECTS:
                    valid_subjects.append(SUBJECTS_MAP[s])
                else:
                    # Busca por nombre interno si no esta el emoji
                    match = next((subj for label, subj in SUBJECTS_MAP.items() if subj.lower() == s.lower()), None)
                    if match:
                        valid_subjects.append(match)
                    else:
                        invalid_subjects.append(s)
            
            msg_header = f"Te inscribiste en: **{', '.join(valid_subjects)}**."

        if not valid_subjects:
            await interaction.response.send_message(create_error_embed("No reconoci esas materias."), ephemeral=True)
            return

        # Guarda la lista en la DB
        self.bot.db.set_enrollments(interaction.user.id, valid_subjects, interaction.guild.id)

        msg = msg_header
        if invalid_subjects:
            msg += f"\n*(No entendi estas: {', '.join(invalid_subjects)})*"
        
        msg += "\n\nSolo te avisare de estas materias ahora."
        await interaction.response.send_message(embed=create_success_embed(msg), ephemeral=True)

    # Autorelleno para las materias
    @inscribirme.autocomplete('materias')
    async def materias_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = ["Todas las materias"] + SUBJECTS
        return [app_commands.Choice(name=c, value=c) for c in choices if current.lower() in c.lower()][:25]

async def setup(bot):
    await bot.add_cog(Enrollment(bot))
