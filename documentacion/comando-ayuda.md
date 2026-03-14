# Comando: /ayuda

## Ubicación
- Cog: `cogs/help.py`
- Función del comando: `ayuda(self, interaction)`

## Objetivo
Mostrar una guía de comandos disponible para el usuario que ejecuta el comando.

## Parámetros
Este comando no recibe parámetros.

## Flujo interno
1. Obtiene los roles del usuario (`interaction.user.roles`).
2. Determina si es staff (`ADMIN` o `DELEGADO`) usando `ROLES`.
3. Construye un embed base con comandos de estudiante.
4. Si el usuario es staff, añade sección de comandos administrativos.
5. Responde de forma efímera (`ephemeral=True`).

## Funciones y utilidades relacionadas
- `discord.Embed(...)`: construcción del mensaje enriquecido.
- Variables de configuración: `ROLES` (desde `utils.config`).

## Errores comunes
- Si faltan roles configurados en `ROLES`, la detección de staff puede no reflejar permisos reales.

## Resultado esperado
El usuario recibe una guía contextual de comandos, sin generar mensajes públicos en el canal.
