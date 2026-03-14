# Comando: /editar-tarea

## Ubicación
- Cog: `cogs/tasks.py`
- Función del comando: `tarea_editar(self, interaction, tarea, titulo=None, fecha_entrega=None)`

## Objetivo
Actualizar título y/o fecha de una tarea existente y reflejar el cambio en el mensaje principal.

## Parámetros
- `tarea`: ID de tarea (acepta formato `123` o `123: ...`).
- `titulo` (opcional): nuevo título.
- `fecha_entrega` (opcional): nueva fecha en `DD/MM/AAAA HH:MM` o valor de sin fecha.

## Flujo interno
1. Verifica permisos administrativos/delegado.
2. Valida longitud de título (si viene).
3. Extrae ID numérico desde `tarea`.
4. Verifica existencia de la tarea.
5. Exige al menos un cambio (`titulo` o `fecha_entrega`).
6. Valida y normaliza fecha si fue enviada.
7. Difiriere respuesta efímera.
8. Actualiza DB con `update_task(...)`.
9. Recupera tarea actualizada y edita el mensaje original en Discord, si existe.
10. Responde con embed de éxito.

## Funciones relacionadas
- `check_permissions(...)`
- `task_edit_autocomplete(...)`

## Errores comunes
- ID mal formateado.
- Falta de permisos para editar mensajes antiguos.

## Resultado esperado
Datos de tarea actualizados en DB y en publicación principal.
