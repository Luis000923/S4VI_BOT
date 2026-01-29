import discord
from discord import app_commands
from discord.ext import commands
from utils.config import SUBJECTS, CHANNELS, ROLES, find_channel
from utils.embeds import create_task_embed, create_success_embed, create_error_embed
import datetime

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Mira si el usuario tiene permiso (Dueño, Admin o Delegado)
    async def check_permissions(self, interaction: discord.Interaction):
        if interaction.user == interaction.guild.owner:
            return True
        if interaction.user.guild_permissions.administrator:
            return True

        user_roles = [role.name.lower() for role in interaction.user.roles]
        if ROLES["ADMIN"].lower() in user_roles or ROLES["DELEGADO"].lower() in user_roles:
            return True
            
        for specialty in ROLES["DELEGADOS_ESPECIALES"]:
            if specialty.lower() in user_roles:
                return True
                
        if any(role_name.startswith("delegado-") for role_name in user_roles):
            return True
        return False

    # Comando para crear una tarea nueva
    @app_commands.command(name="crear-tarea", description="Crea una nueva tarea")
    @app_commands.describe(
        materia="Selecciona la materia",
        titulo="Que hay que hacer?",
        fecha_entrega="Formato: DD/MM/AAAA HH:MM"
    )
    async def tarea_crear(self, interaction: discord.Interaction, materia: str, titulo: str, fecha_entrega: str):
        # Solo deja usarlo en el canal de tareas pendientes
        channel_name = interaction.channel.name.lower()
        if "tareas-pendientes" not in channel_name.replace(" ", "-"):
            target_channel = find_channel(interaction.guild, "tareas-pendientes")
            await interaction.response.send_message(
                f"Usa este comando en <#{target_channel.id if target_channel else 'pendientes'}>", 
                ephemeral=True
            )
            return

        if not await self.check_permissions(interaction):
            await interaction.response.send_message("No tienes permiso.", ephemeral=True)
            return

        if materia not in SUBJECTS:
            await interaction.response.send_message("Materia no valida.", ephemeral=True)
            return

        # Revisa que la fecha este bien escrita
        try:
            formatted_date = datetime.datetime.strptime(fecha_entrega, "%d/%m/%Y %H:%M")
            if formatted_date < datetime.datetime.now():
                await interaction.response.send_message("Esa fecha ya paso.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("Usa el formato: DD/MM/AAAA HH:MM", ephemeral=True)
            return

        from utils.config import SUBJECTS_MAP
        internal_subject = SUBJECTS_MAP.get(materia, materia)
        embed = create_task_embed(titulo, internal_subject, fecha_entrega)
        embed.set_author(name=f"Por {interaction.user.display_name}")
        
        try:
            await interaction.response.send_message(embed=embed)
            original_msg = await interaction.original_response()
            
            # Guarda todo en la base de datos
            task_id = self.bot.db.add_task(internal_subject, titulo, fecha_entrega, interaction.user.id, 
                                          interaction.guild.id, original_msg.id, interaction.channel.id)
        except discord.errors.Forbidden:
            await interaction.response.send_message("No tengo permisos para enviar mensajes aqui.", ephemeral=True)
            return

        # Manda el aviso al canal de la materia
        subject_channel = find_channel(interaction.guild, internal_subject)
        if subject_channel:
            try:
                await subject_channel.send(content=f"🔔 **NUEVA TAREA** de **{materia}**!", embed=embed)
            except discord.errors.Forbidden:
                await interaction.followup.send(f"No pude avisar en {subject_channel.mention} por permisos.", ephemeral=True)
        
        # Manda el aviso a fechas de entrega
        dates_channel = find_channel(interaction.guild, "fechas-de-entrega")
        if dates_channel:
            try:
                await dates_channel.send(embed=embed)
            except:
                pass

    @tarea_crear.autocomplete('materia')
    async def materia_autocomplete(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=subj, value=subj) for subj in SUBJECTS if current.lower() in subj.lower()][:25]

    # Lista las tareas que el usuario aun no entrega
    @app_commands.command(name="mis-tareas", description="Mira que tienes pendiente")
    async def tareas_pendientes(self, interaction: discord.Interaction):
        tasks = self.bot.db.get_tasks(interaction.guild.id)
        if not tasks:
            await interaction.response.send_message("No hay nada anotado todavia.", ephemeral=True)
            return

        user_enrollments = self.bot.db.get_user_enrollments(interaction.user.id, interaction.guild.id)
        embed = discord.Embed(title="📋 Tus Tareas Pendientes", color=0x3498db)
        found = False

        for task in tasks:
            # Los indices cambian segun las columnas de la tabla
            tid, subject, title, due_date = task[0], task[1], task[2], task[3]
            
            if self.bot.db.is_delivered(tid, interaction.user.id):
                continue
            if user_enrollments and subject not in user_enrollments:
                continue

            embed.add_field(
                name=f"#{tid} - {title}",
                value=f"**Materia:** {subject}\n**Entrega:** {due_date}",
                inline=False
            )
            found = True

        if not found:
            await interaction.response.send_message("No tienes nada pendiente por ahora.", ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed)

    # Borra una tarea del sistema y su mensaje
    @app_commands.command(name="eliminar-tarea", description="Borra una tarea definitivamente")
    @app_commands.describe(tarea="Cual quieres borrar?")
    async def tarea_eliminar(self, interaction: discord.Interaction, tarea: str):
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("No tienes permiso.", ephemeral=True)
            return

        try:
            task_id = int(tarea.split(":")[0])
        except:
            await interaction.response.send_message("ID no valido.", ephemeral=True)
            return

        task_data = self.bot.db.get_task_by_id(task_id)
        if not task_data:
            await interaction.response.send_message("Esa tarea ya no existe.", ephemeral=True)
            return

        # Defer por si tarda borrando el mensaje
        await interaction.response.defer(ephemeral=True)

        # Borra el mensaje original si se puede
        msg_id, chan_id = task_data[6], task_data[7]
        if msg_id and chan_id:
            try:
                channel = self.bot.get_channel(chan_id)
                if channel:
                    msg = await channel.fetch_message(msg_id)
                    await msg.delete()
            except:
                pass

        self.bot.db.delete_task(task_id)
        await interaction.followup.send(embed=create_success_embed(f"Tarea #{task_id} borrada y mensaje eliminado."), ephemeral=True)

    @tarea_eliminar.autocomplete('tarea')
    async def task_delete_autocomplete(self, interaction: discord.Interaction, current: str):
        tasks = self.bot.db.get_tasks(interaction.guild.id)
        choices = []
        for t in tasks:
            label = f"{t[0]}: {t[2]} ({t[1]})"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=str(t[0])))
        return choices[:25]

async def setup(bot):
    await bot.add_cog(Tasks(bot))
