import datetime
import re
import unicodedata
from dataclasses import dataclass


@dataclass
class DateParseCandidate:
    dt: datetime.datetime
    confidence: float
    strategy: str


class DueDateAI:
    def __init__(self, default_hour: int = 12, default_minute: int = 0):
        self.default_hour = default_hour
        self.default_minute = default_minute

        self.no_date_tokens = {
            "no asignada",
            "sin fecha",
            "no disponible",
            "not available",
            "n/a",
            "ninguna",
            "pendiente",
        }

        self.month_map_es = {
            "enero": 1,
            "febrero": 2,
            "marzo": 3,
            "abril": 4,
            "mayo": 5,
            "junio": 6,
            "julio": 7,
            "agosto": 8,
            "septiembre": 9,
            "setiembre": 9,
            "octubre": 10,
            "noviembre": 11,
            "diciembre": 12,
        }

        self.month_map_en = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }

    def supported_formats(self):
        return [
            "DD/MM/AAAA HH:MM",
            "DD-MM-AAAA HH:MM",
            "AAAA-MM-DD HH:MM",
            "DD.MM.AAAA HH:MM",
            "DD/MM/AAAA (sin hora -> 12:00)",
            "DD-MM-AAAA (sin hora -> 12:00)",
            "AAAA-MM-DD (sin hora -> 12:00)",
            "miércoles, 18 de marzo de 2026, 23:59",
            "18 de marzo de 2026 11:59 pm",
            "march 18, 2026 11:59 pm",
            "18 march 2026 23:59",
            "2026-03-18T23:59",
        ]

    def normalize(self, raw_text: str):
        if not raw_text:
            return None

        text = self._clean_text(raw_text)
        if not text:
            return None

        if any(token in text for token in self.no_date_tokens):
            return None

        candidates = []
        candidates.extend(self._match_numeric(text))
        candidates.extend(self._match_spanish_textual(text))
        candidates.extend(self._match_english_textual(text))

        if not candidates:
            return None

        best = max(candidates, key=lambda c: c.confidence)
        return best.dt.strftime("%d/%m/%Y %H:%M")

    def _clean_text(self, raw_text: str):
        text = str(raw_text).strip().strip("\"'“”")
        text = re.sub(r"\s+", " ", text)
        text = text.replace("a. m.", "am").replace("p. m.", "pm")
        text = text.replace("a.m.", "am").replace("p.m.", "pm")
        text = text.replace("a m", "am").replace("p m", "pm")
        text = text.replace("h", ":") if re.fullmatch(r"\d{1,2}h\d{2}", text) else text
        return self._strip_accents(text.lower())

    def _strip_accents(self, text: str):
        return "".join(
            char for char in unicodedata.normalize("NFD", text) if unicodedata.category(char) != "Mn"
        )

    def _safe_dt(self, year: int, month: int, day: int, hour: int | None, minute: int | None):
        final_hour = self.default_hour if hour is None else hour
        final_minute = self.default_minute if minute is None else minute
        try:
            return datetime.datetime(year, month, day, final_hour, final_minute)
        except ValueError:
            return None

    def _ampm_to_24(self, hour: int | None, ampm: str | None):
        if hour is None:
            return None
        marker = (ampm or "").replace(".", "").replace(" ", "")
        if marker == "pm" and hour < 12:
            return hour + 12
        if marker == "am" and hour == 12:
            return 0
        return hour

    def _match_numeric(self, text: str):
        candidates = []

        numeric_patterns = [
            (r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\s+(\d{1,2}):(\d{2})\s*(am|pm)?\b", "dmy_time"),
            (r"\b(\d{4})-(\d{1,2})-(\d{1,2})[t\s](\d{1,2}):(\d{2})\s*(am|pm)?\b", "ymd_time"),
            (r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\s+(\d{1,2}):(\d{2})\s*(am|pm)?\b", "dmy_dot_time"),
            (r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", "dmy_date"),
            (r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", "ymd_date"),
        ]

        for pattern, strategy in numeric_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groups()

                if strategy == "dmy_time":
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                    hour, minute = int(groups[3]), int(groups[4])
                    ampm = groups[5]
                elif strategy == "ymd_time":
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    hour, minute = int(groups[3]), int(groups[4])
                    ampm = groups[5]
                elif strategy == "dmy_dot_time":
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                    hour, minute = int(groups[3]), int(groups[4])
                    ampm = groups[5]
                elif strategy == "dmy_date":
                    day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                    hour, minute, ampm = None, None, None
                else:
                    year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                    hour, minute, ampm = None, None, None

                if year < 100:
                    year = 2000 + year

                hour = self._ampm_to_24(hour, ampm)
                dt = self._safe_dt(year, month, day, hour, minute)
                if dt:
                    confidence = 0.97 if hour is not None else 0.90
                    candidates.append(DateParseCandidate(dt=dt, confidence=confidence, strategy=strategy))

        return candidates

    def _match_spanish_textual(self, text: str):
        candidates = []

        pattern = re.compile(
            r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo,?\s*)?"
            r"(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})"
            r"(?:,?\s*(\d{1,2}):(\d{2})\s*(am|pm)?)?",
            re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))
            hour = int(match.group(4)) if match.group(4) else None
            minute = int(match.group(5)) if match.group(5) else None
            ampm = match.group(6)

            month = self.month_map_es.get(month_name)
            if not month:
                continue

            hour = self._ampm_to_24(hour, ampm)
            dt = self._safe_dt(year, month, day, hour, minute)
            if dt:
                confidence = 0.96 if hour is not None else 0.88
                candidates.append(DateParseCandidate(dt=dt, confidence=confidence, strategy="es_textual"))

        return candidates

    def _match_english_textual(self, text: str):
        candidates = []

        month_first = re.compile(
            r"([a-z]+)\s+(\d{1,2}),?\s+(\d{4})(?:,?\s*(\d{1,2}):(\d{2})\s*(am|pm)?)?",
            re.IGNORECASE,
        )
        day_first = re.compile(
            r"(\d{1,2})\s+([a-z]+)\s+(\d{4})(?:,?\s*(\d{1,2}):(\d{2})\s*(am|pm)?)?",
            re.IGNORECASE,
        )

        for pattern, month_idx, day_idx, year_idx, hour_idx, minute_idx, ampm_idx in [
            (month_first, 1, 2, 3, 4, 5, 6),
            (day_first, 2, 1, 3, 4, 5, 6),
        ]:
            for match in pattern.finditer(text):
                month_name = match.group(month_idx).lower()
                day = int(match.group(day_idx))
                year = int(match.group(year_idx))
                hour = int(match.group(hour_idx)) if match.group(hour_idx) else None
                minute = int(match.group(minute_idx)) if match.group(minute_idx) else None
                ampm = match.group(ampm_idx)

                month = self.month_map_en.get(month_name)
                if not month:
                    continue

                hour = self._ampm_to_24(hour, ampm)
                dt = self._safe_dt(year, month, day, hour, minute)
                if dt:
                    confidence = 0.94 if hour is not None else 0.86
                    candidates.append(DateParseCandidate(dt=dt, confidence=confidence, strategy="en_textual"))

        return candidates