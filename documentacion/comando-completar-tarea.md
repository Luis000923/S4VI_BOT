# Comando: /completar-tarea

## Ubicación
- Cog: `cogs/deliveries.py`
- Función del comando: `tarea_entregada(self, interaction, materia, tarea)`

## Objetivo
Marcar una tarea como entregada por un usuario.

## Parámetros
- `materia` (texto): materia de referencia.
- `tarea` (texto): actualmente se espera ID numérico para resolución segura.

## Flujo interno
1. Valida que el comando se ejecute en el canal configurado de entregas (`CHANNELS["DELIVERED"]`).
2. Convierte materia pública a nombre interno con `SUBJECTS_MAP`.
3. Obtiene tareas del servidor (`self.bot.db.get_tasks(...)`).
4. Si `tarea` es numérico, busca coincidencia por ID.
5. Si no encuentra tarea, responde con error.
6. Marca entrega con `self.bot.db.mark_as_delivered(...)`.
7. Responde con embed de éxito.

## Funciones relacionadas
- `materia_autocomplete(...)`
- `tarea_autocomplete(...)` (filtra por materia)

## Errores comunes
- Ejecutar fuera del canal de entregas.
- Enviar texto no numérico en `tarea`.

## Resultado esperado
La relación tarea-usuario queda registrada como entregada en base de datos.
