# Comando: /crear-tarea

## Ubicación
- Cog: `cogs/tasks.py`
- Función del comando: `tarea_crear(self, interaction, materia, titulo, fecha_entrega, recordatorios=True)`

## Objetivo
Crear una tarea nueva, publicarla y persistirla en base de datos con sus mensajes asociados.

## Parámetros
- `materia`: una materia válida de `SUBJECTS`.
- `titulo`: texto de la tarea (sin límite funcional en la lógica del comando; se aplica recorte visual cuando es necesario para mostrarlo en embeds/listados).
- `fecha_entrega`: `DD/MM/AAAA HH:MM` o equivalente a sin fecha (`ninguna`, `sin fecha`, etc.).
- `recordatorios`: booleano para activar recordatorios automáticos.

## Flujo interno
1. Valida canal, permisos y materia.
2. Restringe ejecución al canal de tareas pendientes.
3. Verifica permisos con `check_permissions(...)`.
4. Valida materia.
5. Normaliza y valida fecha.
6. Difiriere respuesta para operaciones largas.
7. Crea embed (`create_task_embed`) y envía mensaje inicial.
8. Guarda tarea con `self.bot.db.add_task(...)`.
9. Registra mensaje con `self.bot.db.add_task_message(...)`.
10. Edita embed para añadir `ID` de tarea.
11. Replica notificación a canal de materia y canal de fechas.

## Funciones relacionadas
- `check_permissions(...)`
- `materia_autocomplete(...)`

## Errores comunes
- Permisos insuficientes.
- Fecha en formato inválido o pasada.
- Falta de permisos del bot para enviar/editar mensajes.

## Resultado esperado
Tarea creada con ID, visible en canales clave y persistida en SQLite.
