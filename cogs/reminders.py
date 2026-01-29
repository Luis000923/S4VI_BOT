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

    # Tarea que corre cada minuto buscando tareas por vencer
    @tasks.loop(minutes=1)
    async def check_reminders(self):
        for guild in self.bot.guilds:
            tasks_list = self.bot.db.get_tasks(guild.id)
            now = datetime.datetime.now()

            for task in tasks_list:
                tid = task[0]
                subject = task[1]
                title = task[2]
                due_date_str = task[3]
                
                try:
                    due_date = datetime.datetime.strptime(due_date_str, "%d/%m/%Y %H:%M")
                except ValueError:
                    continue

                diff = due_date - now
                hours_left = diff.total_seconds() / 3600

                #Ignora tareas muy viejas
                if hours_left < -0.5:
                    continue

                # Tiempos de recordatorio
                reminder_checks = [
                    (24, "24h"),
                    (6, "6h"),
                    (1, "1h"),
                    (0, "final")
                ]

                for trigger_hours, r_type in reminder_checks:
                    # Si toca mandar recordatorio y no se ha enviado ese tipo antes
                    if 0 <= hours_left <= trigger_hours and not self.bot.db.is_reminder_sent(tid, r_type):
                        await self.send_reminder(guild, task, r_type, hours_left)
                        self.bot.db.mark_reminder_sent(tid, r_type)
                        break 

    # Envia el recordatorio al canal de la materia
    async def send_reminder(self, guild, task, r_type, hours_left):
        tid, subject, title, due_date_str = task[0], task[1], task[2], task[3]
        
        # Busca el canal de la materia (sin importar emojis)
        channel = find_channel(guild, subject)
        
        if not channel:
            print(f"⚠️ No encontre canal para el recordatorio de {subject}")
            return

        time_text = {
            "24h": "24 horas",
            "6h": "6 horas",
            "1h": "1 hora",
            "final": "el día de hoy"
        }.get(r_type, f"{int(hours_left)} horas")

        embed = create_reminder_embed(title, subject, time_text)
        
        # Busca quienes no han entregado aun
        enrolled_users = []
        for member in guild.members:
            if member.bot: continue
            
            is_enrolled = self.bot.db.is_user_enrolled_in_subject(member.id, subject, guild.id)
            has_delivered = self.bot.db.is_delivered(tid, member.id)
            
            if is_enrolled and not has_delivered:
                enrolled_users.append(member.mention)

        # Manda el ping a los que faltan
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
