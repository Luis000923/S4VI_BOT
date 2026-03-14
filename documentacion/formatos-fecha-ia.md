# Formatos de fecha soportados (mini IA)

El bot convierte automáticamente fechas al formato interno de recordatorios:

**`DD/MM/AAAA HH:MM`**

Si una fecha viene **sin hora**, se asigna por defecto **12:00** (mediodía).

## Formas aceptadas

- `18/03/2026 23:59`
- `18-03-2026 23:59`
- `2026-03-18 23:59`
- `2026-03-18T23:59`
- `18.03.2026 23:59`
- `18/03/2026`
- `18-03-2026`
- `2026-03-18`
- `miércoles, 18 de marzo de 2026, 23:59`
- `18 de marzo de 2026 23:59`
- `18 de marzo de 2026 11:59 pm`
- `march 18, 2026 11:59 pm`
- `18 march 2026 23:59`

## Variaciones que también reconoce

- `a. m.`, `p. m.`, `a.m.`, `p.m.`
- con comas o sin comas
- con espacios extra

## Palabras que se interpretan como “sin fecha”

- `no asignada`
- `sin fecha`
- `no disponible`
- `not available`
- `n/a`
- `ninguna`
- `pendiente`

## Resultado final para recordatorios

Siempre que pueda interpretar la fecha, el bot guarda el valor en `DD/MM/AAAA HH:MM`, que es el formato usado por el sistema de recordatorios.