# Comando: /inscribirme

## Ubicación
- Cog: `cogs/enrollment.py`
- Función del comando: `inscribirme(self, interaction, materias)`

## Objetivo
Guardar en base de datos las materias del usuario para filtrar recordatorios y vistas de tareas.

## Parámetros
- `materias` (opcional, texto):
  - Lista separada por comas de materias (ejemplo: `Matemática, Ética`).
  - Opción especial: `Todas las materias`.

## Flujo interno
1. Si `materias` viene vacío o como `Todas las materias`, toma todas las materias de `SUBJECTS_MAP`.
2. Si viene texto, separa por coma y valida cada materia:
   - acepta etiqueta pública (`SUBJECTS`),
   - o nombre interno equivalente (`SUBJECTS_MAP`).
3. Si no hay materias válidas, responde con embed de error.
4. Guarda la inscripción con `self.bot.db.set_enrollments(...)`.
5. Responde con embed de éxito y lista de materias inválidas (si hubo).

## Funciones relacionadas
- `materias_autocomplete(...)`: autocompletado para el campo `materias`.
- `create_success_embed(...)`, `create_error_embed(...)`.

## Errores comunes
- Nombres escritos distinto a `SUBJECTS`/`SUBJECTS_MAP`.
- Ejecutar comando en DM sin `guild` (depende de `interaction.guild.id`).

## Resultado esperado
Preferencias de inscripción actualizadas para el usuario en su servidor.
