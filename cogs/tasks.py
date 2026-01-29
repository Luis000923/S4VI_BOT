# tasks.py - Cog de gestión de tareas
import discord
from discord import app_commands
from discord.ext import commands
from utils.config import SUBJECTS, CHANNELS, ROLES, find_channel, SUBJECTS_MAP
from utils.embeds import create_task_embed, create_success_embed, create_error_embed
import datetime

class Tasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Verificar permisos de usuario (Propietario, Administrador o roles específicos)
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

    # Comando para crear una nueva tarea
    @app_commands.command(name="crear-tarea", description="Crear una nueva tarea")
    @app_commands.describe(
        materia="Seleccionar la materia",
        titulo="Descripción de la tarea",
        fecha_entrega="Formato: DD/MM/AAAA HH:MM o 'ninguna'",
        recordatorios="¿Activar recordatorios automáticos? (Sí por defecto)"
    )
    async def tarea_crear(self, interaction: discord.Interaction, materia: str, titulo: str, fecha_entrega: str, recordatorios: bool = True):
        # 1. Validaciones rápidas (Respuestas efímeras)
        channel_name = interaction.channel.name.lower()
        if "tareas-pendientes" not in channel_name.replace(" ", "-"):
            target_channel = find_channel(interaction.guild, "tareas-pendientes")
            await interaction.response.send_message(
                f"Use este comando en <#{target_channel.id if target_channel else 'pendientes'}>",
                ephemeral=True
            )
            return

        if not await self.check_permissions(interaction):
            await interaction.response.send_message("Permisos insuficientes.", ephemeral=True)
            return

        if materia not in SUBJECTS:
            await interaction.response.send_message("Selección de materia inválida.", ephemeral=True)
            return

        # Procesamiento de fecha
        clean_date = fecha_entrega.lower().strip()
        if clean_date in ["no", "no asignada", "n/a", "sin fecha", "vacío", "vacio", "ninguna", "pendiente"]:
            formatted_date_str = "No asignada"
        else:
            try:
                formatted_date = datetime.datetime.strptime(fecha_entrega, "%d/%m/%Y %H:%M")
                if formatted_date < datetime.datetime.now():
                    await interaction.response.send_message("La fecha especificada ya ha pasado.", ephemeral=True)
                    return
                formatted_date_str = fecha_entrega
            except ValueError:
                await interaction.response.send_message("Use el formato: DD/MM/AAAA HH:MM o 'ninguna' para sin fecha.", ephemeral=True)
                return

        # 2. Diferir respuesta para el trabajo pesado
        try:
            await interaction.response.defer(ephemeral=False)
        except discord.errors.InteractionResponded:
            pass # Ya fue respondida por otra instancia o proceso
        except discord.errors.NotFound:
            print("Error: La interacción expiró antes de poder diferir.")
            return

        internal_subject = SUBJECTS_MAP.get(materia, materia)
        embed = create_task_embed(titulo, internal_subject, formatted_date_str)
        embed.set_author(name=f"Añadido por {interaction.user.display_name}")
        
        try:
            # Enviar el mensaje y obtener la referencia al mismo
            original_msg = await interaction.followup.send(embed=embed)
            
            # Persistir los datos de la tarea en la base de datos
            task_id = self.bot.db.add_task(internal_subject, titulo, formatted_date_str, interaction.user.id, 
                                          interaction.guild.id, original_msg.id, interaction.channel.id, int(recordatorios))
            
            # Guardar el mensaje original en la tabla de rastreo
            self.bot.db.add_task_message(task_id, interaction.channel.id, original_msg.id)
            
            # Actualizar el pie de página con el identificador único de la tarea
            embed.set_footer(text=f"ID: {task_id} | Estado: Pendiente")
            await original_msg.edit(embed=embed)
        except discord.errors.Forbidden:
            await interaction.followup.send("No tengo permisos para enviar mensajes aquí.")
            return

        # Notificar al canal específico de la materia
        subject_channel = find_channel(interaction.guild, internal_subject)
        if subject_channel:
            try:
                sub_msg = await subject_channel.send(content=f"🔔 **NUEVA TAREA** para **{materia}**!", embed=embed)
                self.bot.db.add_task_message(task_id, subject_channel.id, sub_msg.id)
            except discord.errors.Forbidden:
                await interaction.followup.send(f"No se pudo notificar en {subject_channel.mention} por falta de permisos.")
        
        # Notificar al canal centralizado de fechas de entrega
        dates_channel = find_channel(interaction.guild, "fechas-de-entrega")
        if dates_channel:
            try:
                date_msg = await dates_channel.send(embed=embed)
                self.bot.db.add_task_message(task_id, dates_channel.id, date_msg.id)
            except:
                pass

    @tarea_crear.autocomplete('materia')
    async def materia_autocomplete(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=subj, value=subj) for subj in SUBJECTS if current.lower() in subj.lower()][:25]

    # Comando para listar tareas pendientes del usuario local
    @app_commands.command(name="mis-tareas", description="Ver tus tareas pendientes")
    async def tareas_pendientes(self, interaction: discord.Interaction):
        tasks = self.bot.db.get_tasks(interaction.guild.id)
        if not tasks:
            await interaction.response.send_message("No hay tareas registradas actualmente.", ephemeral=True)
            return

        user_enrollments = self.bot.db.get_user_enrollments(interaction.user.id, interaction.guild.id)
        embed = discord.Embed(title="📋 Tareas Pendientes", color=0x3498db)
        found = False

        for task in tasks:
            tid, subject, title, due_date = task[0], task[1], task[2], task[3]
            
            # Saltar si ya fue entregada o no está inscrito en la materia
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
            await interaction.response.send_message("No tienes tareas pendientes.", ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed)

    # Comando para editar una tarea existente
    @app_commands.command(name="editar-tarea", description="Editar una tarea existente")
    @app_commands.describe(
        tarea="ID de la tarea a modificar",
        titulo="Nuevo título (opcional)",
        fecha_entrega="Nueva fecha DD/MM/AAAA HH:MM (opcional)"
    )
    async def tarea_editar(self, interaction: discord.Interaction, tarea: str, titulo: str = None, fecha_entrega: str = None):
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("Permisos insuficientes.", ephemeral=True)
            return

        try:
            task_id = int(tarea.split(":")[0])
        except:
            await interaction.response.send_message("Formato de ID inválido.", ephemeral=True)
            return

        task_data = self.bot.db.get_task_by_id(task_id)
        if not task_data:
            await interaction.response.send_message("Tarea no encontrada.", ephemeral=True)
            return

        if not titulo and not fecha_entrega:
            await interaction.response.send_message("Especifique el título o la fecha para actualizar.", ephemeral=True)
            return

        new_date = None
        if fecha_entrega:
            clean_date = fecha_entrega.lower().strip()
            if clean_date in ["no", "no asignada", "n/a", "sin fecha", "vacío", "vacio", "ninguna", "pendiente"]:
                new_date = "No asignada"
            else:
                try:
                    datetime.datetime.strptime(fecha_entrega, "%d/%m/%Y %H:%M")
                    new_date = fecha_entrega
                except ValueError:
                    await interaction.response.send_message("Formato de fecha inválido. use DD/MM/AAAA HH:MM o 'ninguna'.", ephemeral=True)
                    return

        # Diferir después de validaciones
        try:
            await interaction.response.defer(ephemeral=True)
        except:
            return

        # Actualizar registros en la base de datos
        self.bot.db.update_task(task_id, title=titulo, due_date=new_date)
        
        # Recuperar el conjunto de datos actualizado
        updated_task = self.bot.db.get_task_by_id(task_id)
        sub, tit, due, msg_id, chan_id = updated_task[1], updated_task[2], updated_task[3], updated_task[6], updated_task[7]

        # Actualizar el mensaje de anuncio original si es accesible
        if msg_id and chan_id:
            try:
                channel = self.bot.get_channel(chan_id)
                if channel:
                    msg = await channel.fetch_message(msg_id)
                    new_embed = create_task_embed(tit, sub, due)
                    new_embed.set_author(name=msg.embeds[0].author.name if msg.embeds else "S4VI Bot")
                    new_embed.set_footer(text=f"ID: {task_id} | Estado: Pendiente")
                    await msg.edit(embed=new_embed)
            except:
                pass

        await interaction.followup.send(embed=create_success_embed(f"Tarea #{task_id} actualizada correctamente."), ephemeral=True)

    @tarea_editar.autocomplete('tarea')
    async def task_edit_autocomplete(self, interaction: discord.Interaction, current: str):
        tasks = self.bot.db.get_tasks(interaction.guild.id)
        choices = []
        for t in tasks:
            label = f"{t[0]}: {t[2]} ({t[1]})"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=str(t[0])))
        return choices[:25]

    # Comando para eliminar una tarea y sus mensajes asociados
    @app_commands.command(name="eliminar-tarea", description="Eliminar una tarea de forma permanente")
    @app_commands.describe(
        materia="Filtrar por materia",
        tarea="Seleccionar la tarea específica"
    )
    async def tarea_eliminar(self, interaction: discord.Interaction, materia: str, tarea: str):
        if not await self.check_permissions(interaction):
            await interaction.response.send_message("Permisos insuficientes.", ephemeral=True)
            return

        try:
            task_id = int(tarea.split(":")[0])
        except:
            await interaction.response.send_message("Formato de ID inválido.", ephemeral=True)
            return

        task_data = self.bot.db.get_task_by_id(task_id)
        if not task_data:
            await interaction.response.send_message("Tarea no encontrada.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Intentar eliminar todos los mensajes asociados a la tarea en los diferentes canales
        cached_messages = self.bot.db.get_task_messages(task_id)
        for chan_id, msg_id in cached_messages:
            try:
                channel = self.bot.get_channel(chan_id)
                if channel:
                    msg = await channel.fetch_message(msg_id)
                    await msg.delete()
            except Exception as e:
                print(f"Error al eliminar mensaje {msg_id} en canal {chan_id}: {e}")

        self.bot.db.delete_task(task_id)
        await interaction.followup.send(embed=create_success_embed(f"Tarea #{task_id} y su mensaje asociado han sido eliminados."), ephemeral=True)

    @tarea_eliminar.autocomplete('materia')
    async def materia_del_autocomplete(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=subj, value=subj) for subj in SUBJECTS if current.lower() in subj.lower()][:25]

    @tarea_eliminar.autocomplete('tarea')
    async def task_delete_autocomplete(self, interaction: discord.Interaction, current: str):
        materia_sel = interaction.namespace.materia
        internal_subject = SUBJECTS_MAP.get(materia_sel, "")
        
        tasks = self.bot.db.get_tasks(interaction.guild.id)
        choices = []
        for t in tasks:
            # Filtrar por materia si se ha seleccionado una
            if internal_subject and t[1] != internal_subject:
                continue
                
            label = f"{t[0]}: {t[2]} ({t[1]})"
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label, value=str(t[0])))
        return choices[:25]

async def setup(bot):
    await bot.add_cog(Tasks(bot))
