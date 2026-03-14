# Comando: /tareas nuevas

## Ubicación
- Cog: `cogs/course_watcher.py` (GroupCog `tareas`)
- Función del comando: `tareas_nuevas(self, interaction, semana=None)`

## Objetivo
Forzar escaneo de CVirtual para detectar actividades nuevas de tipo foro y tarea.
Además, para actividades de tipo tarea, intenta leer fecha de entrega/cierre y programarlas automáticamente en el canal de la materia.

## Parámetros
- `semana` (opcional, entero 1..60):
  - Si se define, el escaneo se concentra en esa semana.
  - Si no se define, usa la semana más reciente disponible (priorizando semana >= 8).

## Flujo interno
1. Difiriere respuesta efímera.
2. Recorre los servidores del bot (o solo el servidor de la interacción).
3. Llama `_scan_and_notify(guild, requested_week=semana)`.
4. El scanner:
   - autentica en Moodle,
   - obtiene HTML de cada curso,
   - resuelve semana objetivo,
   - consulta URL por sección (`...&section=N`),
  - extrae actividades foro/tarea,
  - para tareas, consulta su detalle y extrae `Fecha de entrega` o `Fecha de cierre`,
   - deduplica por hash en DB,
   - publica embebidos en canal de avisos.
5. Programa tareas detectadas en el canal correspondiente de materia si no existen aún.
6. Incluye el link de origen de CVirtual en el embed de la tarea programada.
7. Si la tarea ya estaba asignada, no la duplica y solo la reporta al usuario que ejecutó el comando.
8. Si el título es muy largo, lo recorta solo para visualización y conserva el original en DB.
9. Responde con resumen de actividades nuevas, tareas programadas y tareas ya asignadas.

## Funciones relacionadas
- `_resolve_target_week(...)`
- `_extract_available_weeks(...)`
- `_extract_activities(...)`
- `_build_activity_embed(...)`

## Errores comunes
- Credenciales inválidas en `.env` (`CVIRTUAL_USER`, `CVIRTUAL_PASSWORD`).
- No encontrar canal de avisos configurado.
- Estructura HTML variable de Moodle (mitigada con selectores de fallback).

## Resultado esperado
Publicación de nuevas actividades, programación automática de tareas por materia y control de duplicados.
