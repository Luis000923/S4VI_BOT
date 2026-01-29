# embeds.py - Embeds de gestión de tareas
import discord
from .config import *

# Crear un embed estandarizado para el anuncio de tareas
def create_task_embed(title, subject, due_date, status="Pendiente"):
    # Alternativa a "No asignada" si no se proporciona fecha de entrega
    display_date = "No asignada"
    if due_date and str(due_date).lower() not in ["null", "none", "", "no asignada"]:
        display_date = due_date
    
    embed = discord.Embed(
        title=f"📝 {title}",
        description=f"**Materia:** {subject}\n**Entrega:** {display_date}",
        color=COLOR_PENDING if status == "Pendiente" else COLOR_SUCCESS
    )
    embed.set_footer(text=f"Estado: {status}")
    return embed

# Alerta de recordatorio para plazos próximos
def create_reminder_embed(title, subject, tiempo_restante):
    embed = discord.Embed(
        title=f"⏰ Recordatorio: {title}",
        description=f"La tarea de **{subject}** vence en **{tiempo_restante}**.",
        color=COLOR_REMINDER
    )
    return embed

# Notificación de éxito (Verde)
def create_success_embed(message):
    return discord.Embed(description=f"✅ {message}", color=COLOR_SUCCESS)

# Notificación de error (Rojo)
def create_error_embed(message):
    return discord.Embed(description=f"❌ {message}", color=COLOR_DANGER)
