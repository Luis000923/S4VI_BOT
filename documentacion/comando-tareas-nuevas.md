# Comando: /tareas nuevas

## Ubicación
- Cog: `cogs/course_watcher.py` (GroupCog `tareas`)
- Función del comando: `tareas_nuevas(self, interaction, semana=None, contrasena=None)`

## Objetivo
Forzar escaneo de CVirtual para detectar actividades nuevas de tipo foro y tarea.
Además, tanto foros como tareas se registran como tareas internas del bot para seguimiento en Discord.

## Parámetros
- `semana` (opcional, entero 1..60):
  - Si se define, el escaneo se concentra en esa semana.
  - Si no se define, usa la semana más reciente disponible (priorizando semana >= 8).
- `contrasena` (opcional, texto):
  - Si envías `00923`, se omite el límite global diario para esa ejecución.
  - Si no se envía o es incorrecta, aplica el límite diario global.

## Límite de uso
- El comando tiene límite global de **2 usos por día** para todos los usuarios.
- Excepción: si `contrasena=00923`, el comando se ejecuta sin consumir ni bloquear por ese límite.

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
6. Registra FOROS y TAREAS como tareas en Discord (el foro se guarda con prefijo `FORO:`).
7. Incluye el link de origen de CVirtual en el embed de la tarea programada.
8. Extrae también las indicaciones desde la vista de la tarea (bloque de introducción/descripcion) y las incluye en el embed.
9. Si la tarea ya estaba asignada, no la duplica y solo la reporta al usuario que ejecutó el comando.
10. Si CVIRTUAL actualiza datos de una tarea existente (fecha/título/materia), el bot actualiza esa tarea y edita sus mensajes publicados.
11. Para evitar duplicados usa materia+título normalizado.
12. Las publicaciones automáticas incluyen mención `@everyone`.
13. En base de datos de tareas se guarda información mínima de tarea/materia/fecha de entrega.
14. Responde con resumen de actividades nuevas, tareas programadas, tareas actualizadas y tareas ya asignadas.

## ¿Cómo obtiene las tareas de la semana?
Este es el flujo específico para “traer tareas de una semana”:

1. **Lee el parámetro `semana`** del comando `/tareas nuevas`.
  - Si envías `/tareas nuevas semana:10`, intenta escanear la **Semana 10**.
  - Si no envías semana, el bot elige automáticamente la más reciente disponible (prioriza semanas `>= 8`).

2. **Carga la página del curso** en CVirtual y detecta semanas disponibles con `_extract_available_weeks(...)`.

3. **Resuelve la semana objetivo** con `_resolve_target_week(...)`:
  - Si la semana pedida existe en el índice del curso, usa su URL real.
  - Si no aparece en el índice, intenta URL directa con `?section=N`.
  - Si no pediste semana, toma la semana más reciente según la regla anterior.

4. **Escanea solo la sección objetivo** (`...course/view.php?id=...&section=N`) para reducir ruido de otras semanas.

5. **Extrae actividades** de esa sección y filtra los tipos relevantes:
  - `FORO`
  - `TAREA`

6. Para cada `TAREA`, **abre el detalle de la actividad** y busca:
  - `Fecha de entrega` / `Fecha de cierre` (normalizada por IA de fechas).
  - Indicaciones o descripción de la tarea.

7. **Deduplica y guarda**:
  - No duplica actividades ya registradas (hash en DB).
  - Si la tarea ya existe pero cambió en CVirtual (título/fecha/materia/enlace), la actualiza.

8. **Publica y programa**:
  - Publica actividad nueva en canal de avisos.
  - Para tareas, crea o actualiza mensajes en el canal de materia y en `fechas-de-entrega`.

En resumen: el bot no “adivina” la semana por la portada del curso; primero resuelve la semana objetivo y luego escanea su sección específica para obtener tareas con mayor precisión.

## Funciones relacionadas
- `_resolve_target_week(...)`
- `_extract_available_weeks(...)`
- `_extract_activities(...)`
- `_build_activity_embed(...)`

## Errores comunes
- Credenciales inválidas en `.env` (`CVIRTUAL_USER`, `CVIRTUAL_PASSWORD`).
- No encontrar canal de avisos configurado.
- Estructura HTML variable de Moodle (mitigada con selectores de fallback).
- Si falla autenticación en CVirtual, el comando responde explícitamente con aviso de credenciales en lugar de mostrar "sin actividades".

## Resultado esperado
Publicación de nuevas actividades, programación automática de tareas por materia, actualización de tareas existentes y control de duplicados.

## Informe técnico (resumen para ingeniería)

### 1) Propósito del proceso
El comando `/tareas nuevas` implementa un pipeline de ingesta desde CVirtual (Moodle) para detectar actividades académicas de tipo foro/tarea, con foco en tareas para su programación automática en Discord.

### 2) Arquitectura funcional
- **Capa de disparo**: comando manual con parámetro de semana opcional.
- **Capa de adquisición**: autenticación HTTP (`aiohttp`) + descarga de HTML de curso y sección.
- **Capa de parsing**: extracción robusta por selectores + regex (`WEEK_REGEX`) para identificar semana y actividades.
- **Capa de enriquecimiento**: consulta de detalle de tarea para extraer fecha (`Fecha de entrega/cierre`) e indicaciones.
- **Capa de persistencia**: deduplicación por hash e inserción/actualización en DB.
- **Capa de publicación**: notificación en canal de avisos y sincronización de mensajes en canales de materia.

### 3) Algoritmo de obtención por semana
1. Resolver `requested_week`:
  - Si existe en índice de curso, usar URL detectada.
  - Si no existe, intentar `course_url?section=N`.
  - Si no hay `requested_week`, seleccionar la mayor semana disponible, priorizando `N >= 8`.
2. Cargar HTML de la sección objetivo para minimizar ruido de semanas no relevantes.
3. Extraer nodos de actividad y clasificar (`FORO` / `TAREA`).
4. Para cada `TAREA`, abrir detalle y normalizar fecha vía `DueDateAI`.
5. Persistir resultados con control de idempotencia.

### 4) Consistencia e idempotencia
- **No duplicación de actividades**: hash determinístico por curso + semana + tipo + título + URL.
- **No duplicación de tareas**: matching principal por `source_url`; fallback por `materia+título normalizado`.
- **Convergencia de estado**: si CVirtual cambia fecha/título/materia, se actualiza DB y se editan mensajes ya publicados.

### 5) Comportamiento ante fallos
- Si falla autenticación o una carga HTML, el curso afectado se omite sin tumbar todo el proceso.
- Si no existe canal de materia, aplica fallback al canal pendiente (si está configurado).
- Si no se detectan novedades, retorna respuesta explícita sin efectos secundarios.

### 6) Riesgos técnicos y mitigación
- **Variación de HTML Moodle**: mitigado con selectores de fallback, pero requiere mantenimiento evolutivo.
- **Dependencia de credenciales/cookies**: validar `.env` y expiración de sesión.
- **Semana solicitada inexistente**: se intenta por URL directa; puede resultar en escaneo vacío.

### 7) Checklist de validación para ingeniería
1. Ejecutar `/tareas nuevas semana:N` y confirmar resolución de sección `section=N`.
2. Verificar detección de `FORO/TAREA` y extracción de fechas en tareas.
3. Confirmar inserción única en DB y ausencia de duplicados tras reejecución.
4. Simular cambio en CVirtual (fecha/título) y validar actualización de mensajes existentes.
