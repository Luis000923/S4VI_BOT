# Comando: /eliminar-tarea

## Ubicación
- Cog: `cogs/tasks.py`
- Función del comando: `tarea_eliminar(self, interaction, materia, tarea)`

## Objetivo
Eliminar una tarea de forma permanente junto con sus mensajes asociados.

## Parámetros
- `materia`: usado para filtrar opciones en autocompletado.
- `tarea`: ID de tarea (o formato con prefijo de ID).

## Flujo interno
1. Verifica permisos (`check_permissions`).
2. Extrae ID numérico desde `tarea`.
3. Comprueba que la tarea exista.
4. Difiriere respuesta efímera.
5. Obtiene lista de mensajes asociados (`get_task_messages`).
6. Intenta borrar mensajes en cada canal guardado.
7. Elimina tarea en DB (`delete_task`).
8. Responde con embed de éxito.

## Funciones relacionadas
- `materia_del_autocomplete(...)`
- `task_delete_autocomplete(...)`

## Errores comunes
- Mensajes ya eliminados manualmente (se ignora y continúa).
- ID inválido o inexistente.

## Resultado esperado
Tarea y rastros de mensajes eliminados del sistema.
