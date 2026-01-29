# reminders.py - Recordatorios automáticos de tareas
import discord
from discord.ext import tasks, commands
from utils.config import CHANNELS, SUBJECTS, find_channel
from utils.embeds import create_reminder_embed
import datetime

class Reminders(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_reminders.start()

    def cog_unload(self):
        self.check_reminders.cancel()

    # Tarea periódica para identificar tareas próximas a vencer
    @tasks.loop(minutes=1)
    async def check_reminders(self):
        for guild in self.bot.guilds:
            tasks_list = self.bot.db.get_tasks(guild.id)
            now = datetime.datetime.now()

            for task in tasks_list:
                tid, subject, title, due_date_str = task[0], task[1], task[2], task[3]
                reminders_active = task[8] if len(task) > 8 else 1
                
                if not reminders_active:
                    continue
                    
                try:
                    due_date = datetime.datetime.strptime(due_date_str, "%d/%m/%Y %H:%M")
                except ValueError:
                    # Omitir tareas sin fecha asignada o formatos inválidos
                    continue

                diff = due_date - now
                hours_left = diff.total_seconds() / 3600

                # Ignorar tareas vencidas
                if hours_left < -0.5:
                    continue

                # Umbrales de recordatorio (horas restantes antes del vencimiento)
                reminder_checks = [
                    (24, "24h"),
                    (6, "6h"),
                    (1, "1h"),
                    (0, "final")
                ]

                for trigger_hours, r_type in reminder_checks:
                    # Enviar recordatorio si está dentro del umbral y no se ha enviado previamente
                    if 0 <= hours_left <= trigger_hours and not self.bot.db.is_reminder_sent(tid, r_type):
                        await self.send_reminder(guild, task, r_type, hours_left)
                        self.bot.db.mark_reminder_sent(tid, r_type)
                        break 

    # Enviar notificación de recordatorio al canal de la materia
    async def send_reminder(self, guild, task, r_type, hours_left):
        tid, subject, title, due_date_str = task[0], task[1], task[2], task[3]
        
        # Localizar el canal designado para la materia
        channel = find_channel(guild, subject)
        
        if not channel:
            print(f"Advertencia: No se encontró el canal para el recordatorio de: {subject}")
            return

        # Formatear el tiempo restante preciso
        now = datetime.datetime.now()
        try:
            due_date = datetime.datetime.strptime(due_date_str, "%d/%m/%Y %H:%M")
            diff = due_date - now
            
            days = diff.days
            hours, remainder = divmod(diff.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            time_parts = []
            if days > 0: time_parts.append(f"{days}d")
            if hours > 0: time_parts.append(f"{hours}h")
            if minutes > 0: time_parts.append(f"{minutes}m")
            
            time_text = " ".join(time_parts) if time_parts else "menos de 1 minuto"
        except:
            time_text = f"{int(hours_left)} horas"

        embed = create_reminder_embed(title, subject, time_text)
        
        # Filtrar usuarios inscritos en la materia que aún no han entregado
        enrolled_users = []
        for member in guild.members:
            if member.bot: continue
            
            is_enrolled = self.bot.db.is_user_enrolled_in_subject(member.id, subject, guild.id)
            has_delivered = self.bot.db.is_delivered(tid, member.id)
            
            if is_enrolled and not has_delivered:
                enrolled_users.append(member.mention)

        # Enviar pings en bloques para evitar límites de mensajes
        if enrolled_users:
            for i in range(0, len(enrolled_users), 20):
                chunk = enrolled_users[i:i+20]
                mentions = " ".join(chunk)
                try:
                    await channel.send(content=f"🔔 **Recordatorio** para: {mentions}", embed=embed)
                except:
                    pass

async def setup(bot):
    await bot.add_cog(Reminders(bot))
