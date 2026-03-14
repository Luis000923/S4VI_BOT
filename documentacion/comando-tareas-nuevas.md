# Comando: /tareas nuevas

## Ubicación
- Cog: `cogs/course_watcher.py` (GroupCog `tareas`)
- Función del comando: `tareas_nuevas(self, interaction, semana=None)`

## Objetivo
Forzar escaneo de CVirtual para detectar actividades nuevas de tipo foro y tarea.

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
   - deduplica por hash en DB,
   - publica embebidos en canal de avisos.
5. Responde con total de nuevas actividades detectadas.

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
Publicación de nuevas actividades, sin duplicados, en el canal de avisos de tareas.
