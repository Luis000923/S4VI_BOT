# Comando: !sync

## Ubicación
- Archivo: `main.py`
- Función del comando: `sync(ctx)`
- Tipo: comando por prefijo (`!`), no slash.

## Objetivo
Sincronizar manualmente el árbol de slash commands del bot.

## Parámetros
Este comando no recibe parámetros.

## Flujo interno
1. Requiere permisos de administrador (`@commands.has_permissions(administrator=True)`).
2. Ejecuta `await bot.tree.sync()`.
3. Envía confirmación en el canal: `Sincronización completada.`

## Uso recomendado
Usar después de agregar/renombrar comandos slash o tras cambios de cogs.

## Errores comunes
- Usuario sin permisos administrativos.
- Falta de permisos del bot en el servidor.

## Resultado esperado
Comandos slash actualizados en Discord según estado actual del código.
