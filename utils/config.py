import unicodedata
import re
import discord

# Limpia el texto para que el bot encuentre canales facil (sin tildes ni emojis)
def normalize_text(text):
    if not text: return ""
    text = unicodedata.normalize('NFD', text)
    text = "".join([c for c in text if unicodedata.category(c) != 'Mn'])
    return re.sub(r'[^a-z0-9]', '', text.lower())

# Busca un canal aunque tenga emojis o espacios raros
def find_channel(guild, name_query):
    query = normalize_text(name_query)
    # Primero busca que sean iguales
    for channel in guild.text_channels:
        if normalize_text(channel.name) == query:
            return channel
    # Luego busca que el nombre contenga la palabra (ej: "mate" en "tareas-mate")
    for channel in guild.text_channels:
        if query in normalize_text(channel.name):
            return channel
    return None

# Nombres de materias y sus etiquetas en Discord
SUBJECTS_MAP = {
    "📐 MATEMÁTICA": "Matemática",
    "🔐 SEGURIDAD-DE-LA-INFORMACIÓN": "Ciberseguridad",
    "🌐 INFRAESTRUCTURA-DE-RED": "Infraestructura de Red",
    "💻 PROGRAMACIÓN": "Programación",
    "⚖️ ÉTICA": "Ética"
}

SUBJECTS = list(SUBJECTS_MAP.keys())

# Canales del sistema
CHANNELS = {
    "WELCOME": "general",
    "PENDING": "📄-tareas-pendientes",
    "DELIVERED": "📄-tareas-entregadas",
    "DATES": "fechas-de-entrega",
    "SUBJECT_PREFIX": "📄-tareas-" 
}

# Canales especificos por materia
SUBJECT_CHANNEL_MAP = {
    "Matemática": "📏-tareas-matemática",
    "Ciberseguridad": "🔐-tareas-seguridad",
    "Infraestructura de Red": "🌐-tareas-infraestructura",
    "Programación": "💻-tareas-programación",
    "Ética": "⚖️-tareas-ética"
}

# Saca el nombre del canal de una materia
def get_subject_channel_name(display_name):
    internal_name = SUBJECTS_MAP.get(display_name, display_name)
    return SUBJECT_CHANNEL_MAP.get(internal_name, f"tareas-{internal_name.lower()}")

# Roles que pueden usar el bot
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

# Colores para los mensajes
COLOR_PENDING = 0x3498db
COLOR_SUCCESS = 0x2ecc71
COLOR_REMINDER = 0xe67e22
COLOR_DANGER = 0xe74c3c
