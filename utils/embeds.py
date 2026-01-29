import discord
from .config import *

# Crea el cuadrito para una tarea nueva
def create_task_embed(title, subject, due_date, status="Pendiente"):
    embed = discord.Embed(
        title=f"📝 {title}",
        description=f"**Materia:** {subject}\n**Entrega:** {due_date}",
        color=COLOR_PENDING if status == "Pendiente" else COLOR_SUCCESS
    )
    embed.set_footer(text=f"Estado: {status}")
    return embed

# Alerta de que falta poco para entregar
def create_reminder_embed(title, subject, time_left):
    embed = discord.Embed(
        title=f"⏰ Recordatorio: {title}",
        description=f"La tarea de **{subject}** vence en **{time_left}**.",
        color=COLOR_REMINDER
    )
    return embed

# Mensaje de exito (verde)
def create_success_embed(message):
    return discord.Embed(description=f"✅ {message}", color=COLOR_SUCCESS)

# Mensaje de error (rojo)
def create_error_embed(message):
    return discord.Embed(description=f"❌ {message}", color=COLOR_DANGER)
