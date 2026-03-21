import pytest

from utils.date_ai import DueDateAI


@pytest.mark.parametrize(
    "raw_text,expected",
    [
        ("18/03/2026 23:59", "18/03/2026 23:59"),
        ("18-03-2026 23:59", "18/03/2026 23:59"),
        ("2026-03-18T23:59", "18/03/2026 23:59"),
        ("18 de marzo de 2026 11:59 pm", "18/03/2026 23:59"),
        ("march 18, 2026 11:59 pm", "18/03/2026 23:59"),
    ],
)
def test_normalize_valid_formats(raw_text, expected):
    parser = DueDateAI(default_hour=12, default_minute=0)
    assert parser.normalize(raw_text) == expected


def test_normalize_returns_none_for_no_date_tokens():
    parser = DueDateAI()
    assert parser.normalize("No asignada") is None
    assert parser.normalize("N/A") is None


def test_normalize_uses_default_time_if_missing():
    parser = DueDateAI(default_hour=12, default_minute=0)
    assert parser.normalize("18/03/2026") == "18/03/2026 12:00"


def test_normalize_invalid_date_returns_none():
    parser = DueDateAI()
    assert parser.normalize("31/02/2026 09:00") is None
