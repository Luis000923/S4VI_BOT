# embeds.py - Embeds de gestión de tareas
import discord
from .config import COLOR_DANGER, COLOR_PENDING, COLOR_REMINDER, COLOR_SUCCESS


def _clip(text, limit):
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."

# Crear un embed estandarizado para el anuncio de tareas
def create_task_embed(title, subject, due_date, status="Pendiente", source_url=None, instructions=None):
    # Alternativa a "No asignada" si no se proporciona fecha de entrega
    display_date = "No asignada"
    if due_date and str(due_date).lower() not in ["null", "none", "", "no asignada"]:
        display_date = due_date

    clean_title = str(title or "").strip() or "Tarea sin título"
    clean_subject = str(subject or "").strip() or "Sin materia"
    safe_title = _clip(clean_title, 3500)

    description_lines = [
        f"**Título:** {safe_title}",
        f"**Materia:** {clean_subject}",
        f"**Entrega:** {display_date}",
    ]

    if source_url:
        description_lines.append(f"**Fuente:** {source_url}")
    
    embed = discord.Embed(
        title="📝 Tarea",
        description="\n".join(description_lines),
        color=COLOR_PENDING if status == "Pendiente" else COLOR_SUCCESS
    )

    if instructions:
        embed.add_field(name="Indicaciones", value=_clip(instructions, 1000), inline=False)

    embed.set_footer(text=f"Estado: {status}")
    return embed

# Alerta de recordatorio para plazos próximos
def create_reminder_embed(title, subject, tiempo_restante):
    safe_title = _clip(title, 180)
    embed = discord.Embed(
        title=f"⏰ Recordatorio: {safe_title}",
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
