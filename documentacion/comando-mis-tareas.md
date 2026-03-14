# Comando: /mis-tareas

## Ubicación
- Cog: `cogs/tasks.py`
- Función del comando: `tareas_pendientes(self, interaction)`

## Objetivo
Listar tareas pendientes del usuario en el servidor actual.

## Parámetros
Este comando no recibe parámetros.

## Flujo interno
1. Carga todas las tareas del servidor con `self.bot.db.get_tasks(guild_id)`.
2. Obtiene inscripciones del usuario (`get_user_enrollments`).
3. Recorre tareas y descarta:
   - tareas ya entregadas por el usuario (`is_delivered`),
   - tareas de materias en las que no está inscrito (si tiene filtro de inscripciones).
4. Construye embed con tareas filtradas.
5. Si no hay resultados, responde en efímero; si hay, envía embed normal.

## Funciones relacionadas
- Métodos DB: `get_tasks`, `get_user_enrollments`, `is_delivered`.

## Errores comunes
- No aparecen tareas cuando el usuario está inscrito solo en materias distintas.

## Resultado esperado
Vista personalizada de pendientes por usuario.
