from types import SimpleNamespace

from utils.config import find_channel, normalize_text


def _guild_with_channels(*names):
    return SimpleNamespace(text_channels=[SimpleNamespace(name=name) for name in names])


def test_normalize_text_removes_accents_and_symbols():
    assert normalize_text("⚖️ ÉTICA") == "etica"
    assert normalize_text("🔐-SEGURIDAD-DE-LA-INFORMACIÓN") == "seguridaddelainformacion"


def test_find_channel_by_subject_mapping():
    guild = _guild_with_channels(
        "📄-tareas-pendientes",
        "📏-tareas-matemática",
        "⚖️-tareas-ética",
    )
    channel = find_channel(guild, "📐 MATEMÁTICA")
    assert channel is not None
    assert channel.name == "📏-tareas-matemática"


def test_find_channel_partial_and_normalized_match():
    guild = _guild_with_channels("avisos-tareas-pendientes", "fechas-de-entrega")
    channel = find_channel(guild, "Avisos Tareas")
    assert channel is not None
    assert channel.name == "avisos-tareas-pendientes"


def test_find_channel_returns_none_when_missing():
    guild = _guild_with_channels("general")
    assert find_channel(guild, "materia-inexistente") is None
