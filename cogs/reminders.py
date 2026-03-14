# reminders.py - Recordatorios automáticos de tareas
import discord
from discord.ext import tasks, commands
from utils.config import find_channel
from utils.embeds import create_reminder_embed
import datetime


REMINDER_CHECKS = (
    (24, "24h"),
    (6, "6h"),
    (1, "1h"),
    (0, "final"),
)

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
            if not tasks_list:
                continue

            now = datetime.datetime.now()
            task_ids = [task[0] for task in tasks_list]
            sent_reminders = self.bot.db.get_sent_reminders_for_tasks(task_ids)
            enrollment_snapshot = self.bot.db.get_enrollment_snapshot(guild.id)
            delivered_pairs = self.bot.db.get_delivered_pairs_for_tasks(guild.id, task_ids)
            channel_cache = {}

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

                for trigger_hours, r_type in REMINDER_CHECKS:
                    # Enviar recordatorio si está dentro del umbral y no se ha enviado previamente
                    if 0 <= hours_left <= trigger_hours and (tid, r_type) not in sent_reminders:
                        await self.send_reminder(
                            guild,
                            task,
                            r_type,
                            hours_left,
                            enrollment_snapshot=enrollment_snapshot,
                            delivered_pairs=delivered_pairs,
                            channel_cache=channel_cache,
                        )
                        self.bot.db.mark_reminder_sent(tid, r_type)
                        sent_reminders.add((tid, r_type))
                        break 

    # Enviar notificación de recordatorio al canal de la materia
    async def send_reminder(self, guild, task, r_type, hours_left, enrollment_snapshot=None, delivered_pairs=None, channel_cache=None):
        tid, subject, title, due_date_str = task[0], task[1], task[2], task[3]
        
        # Localizar el canal designado para la materia
        if channel_cache is None:
            channel = find_channel(guild, subject)
        else:
            channel = channel_cache.get(subject)
            if subject not in channel_cache:
                channel = find_channel(guild, subject)
                channel_cache[subject] = channel
        
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

        users_with_enrollments = set()
        subjects_by_user = {}
        if enrollment_snapshot:
            users_with_enrollments = enrollment_snapshot.get("users_with_enrollments", set())
            subjects_by_user = enrollment_snapshot.get("subjects_by_user", {})
        delivered_lookup = delivered_pairs if delivered_pairs is not None else set()
        
        # Filtrar usuarios inscritos en la materia que aún no han entregado
        enrolled_users = []
        for member in guild.members:
            if member.bot:
                continue

            if enrollment_snapshot is None:
                is_enrolled = self.bot.db.is_user_enrolled_in_subject(member.id, subject, guild.id)
            else:
                if member.id in users_with_enrollments:
                    is_enrolled = subject in subjects_by_user.get(member.id, set())
                else:
                    is_enrolled = True

            if delivered_pairs is None:
                has_delivered = self.bot.db.is_delivered(tid, member.id)
            else:
                has_delivered = (tid, member.id) in delivered_lookup
            
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
