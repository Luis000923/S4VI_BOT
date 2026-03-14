# config.py - Constantes de configuración y funciones de utilidad
import unicodedata
import re
import discord

NON_ALNUM_REGEX = re.compile(r'[^a-z0-9]')

# Normaliza el texto para búsquedas consistentes de canales (elimina acentos y caracteres no alfanuméricos)
def normalize_text(text):
    if not text: return ""
    text = unicodedata.normalize('NFD', text)
    text = "".join(c for c in text if unicodedata.category(c) != 'Mn')
    return NON_ALNUM_REGEX.sub('', text.lower())

# Busca un canal basado en palabras clave o nombres normalizados
def find_channel(guild, name_query):
    if not name_query: return None
    
    # Verifica si la consulta se refiere a una materia para obtener el canal específico
    target_name = None
    if name_query in SUBJECTS:
        internal_name = SUBJECTS_MAP.get(name_query)
        target_name = SUBJECT_CHANNEL_MAP.get(internal_name)
    elif name_query in SUBJECTS_MAP.values():
        target_name = SUBJECT_CHANNEL_MAP.get(name_query)
    
    # Normaliza la entrada para la búsqueda
    query = normalize_text(target_name) if target_name else normalize_text(name_query)
    simple_query = normalize_text(name_query)
    channels_with_norm = [(channel, normalize_text(channel.name)) for channel in guild.text_channels]

    # 1. Coincidencia exacta normalizada
    for channel, chan_norm in channels_with_norm:
        if chan_norm == query or chan_norm == simple_query:
            return channel
            
    # 2. Coincidencia parcial usando el nombre mapeado
    for channel, chan_norm in channels_with_norm:
        if query and (query in chan_norm or chan_norm in query):
            return channel
            
    # 3. Búsqueda basada en palabras clave para materias específicas
    base_keywords = {
        "ciberseguridad": "seguridad",
        "infraestructuradered": "infraestructura",
        "programacion": "programacion",
        "matematica": "matematica",
        "etica": "etica"
    }
    
    search_key = base_keywords.get(simple_query, simple_query)
    for channel, chan_norm in channels_with_norm:
        if search_key in chan_norm:
            return channel
            
    return None

# Mapeo de materias y nombres para visualización
SUBJECTS_MAP = {
    "📐 MATEMÁTICA": "Matemática",
    "🔐 SEGURIDAD-DE-LA-INFORMACIÓN": "Ciberseguridad",
    "🌐 INFRAESTRUCTURA-DE-RED": "Infraestructura de Red",
    "💻 PROGRAMACIÓN": "Programación",
    "⚖️ ÉTICA": "Ética"
}

SUBJECTS = list(SUBJECTS_MAP.keys())

# Nombres de canales del sistema
CHANNELS = {
    "WELCOME": "general",
    "PENDING": "📄-tareas-pendientes",
    "DELIVERED": "📄-tareas-entregadas",
    "DATES": "fechas-de-entrega",
    "COURSE_UPDATES": "avisos-tareas-pendientes",
    "SUBJECT_PREFIX": "📄-tareas-" 
}

# Mapeo de canales específicos por materia
SUBJECT_CHANNEL_MAP = {
    "Matemática": "📏-tareas-matemática",
    "Ciberseguridad": "🔐-tareas-seguridad",
    "Infraestructura de Red": "🌐-tareas-infraestructura",
    "Programación": "💻-tareas-programación",
    "Ética": "⚖️-tareas-ética"
}

# Obtiene el nombre del canal específico para una materia dada
def get_subject_channel_name(display_name):
    internal_name = SUBJECTS_MAP.get(display_name, display_name)
    return SUBJECT_CHANNEL_MAP.get(internal_name, f"tareas-{internal_name.lower()}")

# Definición de roles y permisos
ROLES = {
    "ADMIN": "admin",
    "DELEGADO": "delegado",
    "ESTUDIANTRE": "estudiantes",
    "DELEGADOS_ESPECIALES": [
        "delegado-mate",
        "delegado-pro",
        "delegado-etica",
        "delegado-redes",
        "delegado-ciber"
    ]
}

# Constantes de colores para la interfaz
COLOR_PENDING = 0x3498db
COLOR_SUCCESS = 0x2ecc71
COLOR_REMINDER = 0xe67e22
COLOR_DANGER = 0xe74c3c
