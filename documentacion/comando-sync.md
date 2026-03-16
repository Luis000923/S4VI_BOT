# Comando: !sync

## Ubicación
- Archivo: `main.py`
- Función del comando: `sync(ctx)`
- Tipo: comando por prefijo (`!`), no slash.

## Objetivo
Sincronizar manualmente el árbol de slash commands del bot.

## Nota técnica
- **NO se ejecuta sincronización automática al iniciar** para evitar rate limits de Discord (Error 1015).
- La sincronización debe hacerse manualmente usando `!sync` cuando cambies slash commands.
- Esta es una medida de seguridad especialmente importante en entornos con reinicio frecuente (como Render).

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
