# Informe técnico detallado: escaneo por semanas en CVirtual

## 1) Resumen ejecutivo
El escaneo de semanas se implementa en `cogs/course_watcher.py` y tiene dos modos:
- **Automático** por horarios (`tasks.loop`) definidos en zona horaria de El Salvador.
- **Manual** con `/tareas nuevas [semana]`.

La lógica actual evita el problema de Moodle/tiles donde la URL base del curso puede mostrar actividades iniciales y no necesariamente la semana deseada. Para resolverlo, el bot:
1. Detecta semanas disponibles en el índice del curso.
2. Selecciona una semana objetivo.
3. Construye o usa la URL específica de sección (`course/view.php?id=...&section=N`).
4. Escanea esa sección para extraer foros y tareas.

---

## 2) Librerías utilizadas y su función

### `discord.py` (`discord`, `discord.ext.commands`, `discord.ext.tasks`, `discord.app_commands`)
- Define cogs, comandos slash y comandos de prefijo.
- Ejecuta tarea programada de escaneo (`@tasks.loop(minutes=1)`).
- Publica resultados en embeds en el canal de avisos.

### `aiohttp`
- Gestiona sesión HTTP asíncrona para login y consultas a Moodle.
- Reutiliza cookies de sesión para varias peticiones por curso.
- Permite timeout global (`ClientTimeout(total=30)`) para evitar bloqueos prolongados.

### `bs4` / `BeautifulSoup`
- Parsea HTML de Moodle.
- Extrae token de login (`input[name='logintoken']`).
- Localiza semanas, secciones y actividades mediante selectores CSS.

### `re` (expresiones regulares)
- `WEEK_REGEX` detecta textos tipo `Semana 8`.
- Extrae número de semana para selección y priorización.

### `urllib.parse.urljoin`
- Normaliza enlaces relativos/absolutos de actividades y secciones.

### `datetime` + `zoneinfo.ZoneInfo`
- Controla ejecución por franja horaria local (`America/El_Salvador`).
- Evita ejecución duplicada dentro del mismo minuto de slot.

### `hashlib`
- Genera hash SHA-256 de cada item detectado para deduplicar en DB.

### `os`
- Lee credenciales y configuración desde variables de entorno (`.env`).

---

## 3) Variables y constantes clave
- `COURSES`: mapa de cursos (nombre -> URL base).
- `MOODLE_LOGIN_URL`: endpoint de autenticación.
- `SCHEDULE_SLOTS`: horarios exactos de escaneo automático.
- `WEEK_REGEX`: patrón para identificar semana.
- `MIN_WEEK_TO_SCAN = 8`: umbral para priorizar semanas recientes.

---

## 4) Flujo completo del escaneo

## 4.1 Disparo del proceso
- **Automático**: `scan_courses_task` corre cada minuto y solo actúa si coincide con un slot configurado.
- **Manual**: `/tareas nuevas` permite forzar escaneo inmediato; parámetro `semana` opcional.

## 4.2 Autenticación Moodle
1. GET a login para obtener `logintoken`.
2. POST con `username`, `password`, token.
3. Si detecta retorno a login + `invalidlogin`, marca credenciales inválidas.

## 4.3 Resolución de semana objetivo
En `_resolve_target_week(soup, course_url, requested_week)`:
- Si el usuario indica `requested_week`, intenta usarla.
- Si no existe en índice, construye igualmente URL `&section=requested_week` (intento directo).
- Si no se indicó semana:
  - toma semanas detectadas,
  - filtra `>= 8`,
  - elige la mayor disponible,
  - si no hay >=8, toma la mayor global.

## 4.4 Extracción de semanas disponibles
En `_extract_available_weeks(...)`:
- Recorre anchors con `section=` y navegación de índice.
- Extrae `Semana N` desde texto visible.
- Fallback por IDs de sección (`section-8`, etc.) si faltan enlaces claros.

## 4.5 Carga de HTML de la semana
- Si hay semana objetivo, usa URL de sección para reducir ruido de semanas anteriores.
- Si falla carga de sección, conserva HTML base como fallback.

## 4.6 Extracción de actividades
En `_extract_activities(...)`:
- Localiza secciones con selectores flexibles para diferentes temas de Moodle.
- Busca actividades (`li.activity`, `div.activity`, enlaces `/mod/forum/` y `/mod/assign/`).
- `_detect_activity_type(...)` clasifica en FORO/TAREA.
- `_parse_activity_block(...)` extrae título, URL, curso, semana.
- Si la semana no se detecta por sección, usa inferencia de contexto con `_infer_week_from_context(...)`.

## 4.7 Deduplicación y persistencia
- `_hash_item(...)` genera hash con: curso + semana + tipo + título + URL.
- `add_course_watch_item(...)` en DB evita insertar duplicados.
- Solo items nuevos generan notificación.

## 4.8 Publicación
- Se resuelve canal destino con `_resolve_updates_channel(...)`.
- Cada item nuevo se publica con embed (`_build_activity_embed(...)`).

---

## 5) Por qué el enfoque por sección corrige el problema original
Problema detectado: varias semanas conviven en la misma URL base, pero el contenido visible/parseable puede sesgarse a primeros bloques.

Corrección aplicada:
- En vez de confiar solo en la vista base, se apunta a la semana objetivo con `section=N`.
- Esto aísla actividades de la semana requerida (ej. Semana 8) y evita omisiones de foros/tareas recientes.

---

## 6) Manejo de errores y resiliencia
- Timeouts de red por sesión HTTP.
- Fallbacks de parsing por múltiples selectores.
- Inferencia de semana por jerarquía DOM y siblings.
- Respuestas claras al usuario cuando no hay hallazgos.

---

## 7) Riesgos técnicos vigentes
1. **Cambios de HTML en Moodle**: selectores pueden requerir ajuste futuro.
2. **Credenciales/cookies caducadas**: bloquean o vacían resultados.
3. **Canal de avisos no encontrado**: no hay publicación aunque sí se detecten items.
4. **Semana inexistente solicitada manualmente**: se intenta URL directa, pero puede devolver vacío.

---

## 8) Recomendaciones de operación
- Mantener `CVIRTUAL_USER` y `CVIRTUAL_PASSWORD` vigentes.
- Probar semanalmente `/tareas nuevas semana:8` (o la actual) para validar parsing.
- Si hay cambios de tema Moodle, revisar primero `_extract_available_weeks` y `_extract_activities`.
- Usar `!sync` tras cambios de parámetros en comandos slash.

---

## 9) Checklist rápido de diagnóstico
1. Ejecutar `/tareas nuevas semana:N`.
2. Verificar que aparezcan links `mod/forum` o `mod/assign` en resultados.
3. Confirmar presencia de inserciones en tabla de `course_watch_items`.
4. Confirmar que el canal de avisos existe y es accesible por el bot.

Con esto, el escaneo por semana queda trazable, repetible y más robusto frente al formato de cursos en CVirtual.
