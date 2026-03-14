# Documentación de comandos - S4VI_BOT

Esta carpeta contiene un archivo por comando del bot, explicando:
- propósito del comando,
- parámetros,
- validaciones,
- flujo interno,
- funciones involucradas,
- errores comunes.

## Índice (1 archivo por comando)
- `comando-ayuda.md` → `/ayuda`
- `comando-inscribirme.md` → `/inscribirme`
- `comando-completar-tarea.md` → `/completar-tarea`
- `comando-crear-tarea.md` → `/crear-tarea`
- `comando-mis-tareas.md` → `/mis-tareas`
- `comando-editar-tarea.md` → `/editar-tarea`
- `comando-eliminar-tarea.md` → `/eliminar-tarea`
- `comando-tareas-nuevas.md` → `/tareas nuevas`
- `comando-sync.md` → `!sync`

## Informe técnico adicional
- `informe-escaneo-semanas.md` → análisis detallado del escaneo por semanas, librerías y flujo técnico del monitor de CVirtual.

## Notas recientes
- `/crear-tarea` y `/editar-tarea` aceptan títulos largos; el recorte se aplica solo en visualización cuando es necesario.
- `/tareas nuevas` puede auto-programar tareas detectadas por CVirtual con fecha de entrega/cierre y link fuente.
- `/tareas nuevas` actualiza tareas existentes cuando CVirtual cambia la información.
- El control de duplicados de tareas detectadas prioriza coincidencia por `source_url`.
- `keep_alive.py` ahora reporta `cpu`, `ram` y `almacenamiento` con detalle (`usado/total/libre/porcentaje`) y elimina GPU.
- Se añadió mantenimiento seguro para limpieza de `__pycache__` y archivos compilados temporales de Python.
