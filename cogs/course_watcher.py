import datetime
import hashlib
import os
import re
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import aiohttp
import discord
from bs4 import BeautifulSoup
from discord import app_commands
from discord.ext import commands, tasks

from utils.config import CHANNELS, find_channel
from utils.embeds import create_task_embed

COURSES = {
    "INFRAESTRUCTURA DE RED": "https://www.cvirtualuees.edu.sv/course/view.php?id=23879",
    "ETICA": "https://www.cvirtualuees.edu.sv/course/view.php?id=23881",
    "FUNDAMENTOS DE PROGRAMACION": "https://www.cvirtualuees.edu.sv/course/view.php?id=23880",
    "MATEMATICA": "https://www.cvirtualuees.edu.sv/course/view.php?id=23878",
    "SEGURIDAD DE LA INFORMACION": "https://www.cvirtualuees.edu.sv/course/view.php?id=23877",
}

MOODLE_BASE_URL = "https://www.cvirtualuees.edu.sv"
MOODLE_LOGIN_URL = f"{MOODLE_BASE_URL}/login/index.php"

SCHEDULE_SLOTS = {
    (0, 6, 0),   # Lunes 06:00
    (2, 18, 0),  # Miércoles 18:00
    (4, 23, 0),  # Viernes 23:00
}

TIMEZONE_NAME = "America/El_Salvador"
WEEK_REGEX = re.compile(r"semana\s*\d+", re.IGNORECASE)
MIN_WEEK_TO_SCAN = 8

COURSE_SUBJECT_MAP = {
    "INFRAESTRUCTURA DE RED": "Infraestructura de Red",
    "ETICA": "Ética",
    "FUNDAMENTOS DE PROGRAMACION": "Programación",
    "MATEMATICA": "Matemática",
    "SEGURIDAD DE LA INFORMACION": "Ciberseguridad",
}


class CourseWatcher(commands.GroupCog, group_name="tareas", group_description="Escaneo de cursos virtuales"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.timezone = ZoneInfo(TIMEZONE_NAME)
        self.last_slot_processed = None
        self.scan_courses_task.start()

    def cog_unload(self):
        self.scan_courses_task.cancel()

    @tasks.loop(minutes=1)
    async def scan_courses_task(self):
        now = datetime.datetime.now(self.timezone).replace(second=0, microsecond=0)
        slot = (now.weekday(), now.hour, now.minute)

        if slot not in SCHEDULE_SLOTS:
            return

        slot_key = now.strftime("%Y-%m-%d %H:%M")
        if slot_key == self.last_slot_processed:
            return

        self.last_slot_processed = slot_key

        for guild in self.bot.guilds:
            await self._scan_and_notify(guild)

    @scan_courses_task.before_loop
    async def before_scan_courses_task(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="nuevas", description="Forzar escaneo de cursos y detectar nuevos foros/tareas")
    @app_commands.describe(semana="Número de semana a escanear (opcional)")
    async def tareas_nuevas(
        self,
        interaction: discord.Interaction,
        semana: app_commands.Range[int, 1, 60] | None = None,
    ):
        await interaction.response.defer(ephemeral=True)

        new_items_total = 0
        created_tasks_total = 0
        already_assigned_items = []
        for guild in self.bot.guilds:
            if interaction.guild and guild.id != interaction.guild.id:
                continue

            report = await self._scan_and_notify(
                guild,
                requested_week=semana,
                command_user_id=interaction.user.id,
            )
            new_items_total += report["new_activities"]
            created_tasks_total += report["created_tasks"]
            already_assigned_items.extend(report["already_assigned"])

        if new_items_total == 0 and created_tasks_total == 0 and not already_assigned_items:
            week_text = f" en Semana {semana}" if semana is not None else ""
            await interaction.followup.send(
                f"No se detectaron actividades nuevas (Foro/Tarea){week_text}.",
                ephemeral=True,
            )
            return

        summary_lines = [
            f"Escaneo completado: {new_items_total} actividades nuevas detectadas.",
            f"Tareas programadas en canales de materia: {created_tasks_total}.",
        ]

        if already_assigned_items:
            summary_lines.append("\nTareas ya asignadas (mostradas solo para ti):")
            for item in already_assigned_items[:12]:
                summary_lines.append(f"- {item['subject']}: {item['title']}")
            if len(already_assigned_items) > 12:
                summary_lines.append(f"- ... y {len(already_assigned_items) - 12} más")

        await interaction.followup.send("\n".join(summary_lines), ephemeral=True)

    async def _scan_and_notify(
        self,
        guild: discord.Guild,
        requested_week: int | None = None,
        command_user_id: int | None = None,
    ) -> dict:
        channel = self._resolve_updates_channel(guild)
        new_items = await self._scan_courses_for_guild(guild.id, requested_week=requested_week)

        if channel:
            for item in new_items:
                embed = self._build_activity_embed(item)
                await channel.send(embed=embed)

        task_report = await self._schedule_detected_tasks(
            guild,
            new_items,
            command_user_id=command_user_id,
        )

        return {
            "new_activities": len(new_items),
            "created_tasks": task_report["created_tasks"],
            "already_assigned": task_report["already_assigned"],
        }

    async def _scan_courses_for_guild(self, guild_id: int, requested_week: int | None = None):
        new_items = []

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            await self._authenticate_session(session)

            for course_name, course_url in COURSES.items():
                html = await self._fetch_course_html(session, course_url)
                if not html:
                    continue

                soup = BeautifulSoup(html, "html.parser")
                target_week = self._resolve_target_week(soup, course_url, requested_week=requested_week)

                target_url = course_url
                target_week_name = None
                target_html = html

                if target_week:
                    target_url = target_week["week_url"]
                    target_week_name = target_week["week_name"]
                    if target_url != course_url:
                        section_html = await self._fetch_course_html(session, target_url)
                        if section_html:
                            target_html = section_html

                items = self._extract_activities(
                    course_name,
                    target_url,
                    target_html,
                    forced_week_name=target_week_name,
                )

                for item in items:
                    if item["activity_type"] == "TAREA":
                        item["due_date"] = await self._extract_due_date_from_assignment(session, item["url"])

                for item in items:
                    item_hash = self._hash_item(item)
                    created = self.bot.db.add_course_watch_item(
                        item_hash=item_hash,
                        course_name=item["course_name"],
                        week_name=item["week_name"],
                        activity_type=item["activity_type"],
                        title=item["title"],
                        url=item["url"],
                        guild_id=guild_id,
                    )
                    if created:
                        new_items.append(item)

        return new_items

    async def _schedule_detected_tasks(self, guild: discord.Guild, items: list[dict], command_user_id: int | None = None):
        created_tasks = 0
        already_assigned = []

        if not items:
            return {"created_tasks": 0, "already_assigned": []}

        existing_keys = set()
        for task in self.bot.db.get_tasks(guild.id):
            subject = (task[1] or "").strip().lower()
            title = self._normalize_task_title(task[2] or "")
            existing_keys.add((subject, title))

        actor_id = command_user_id or getattr(self.bot.user, "id", 0) or 0

        for item in items:
            if item.get("activity_type") != "TAREA":
                continue

            subject = COURSE_SUBJECT_MAP.get(item.get("course_name", ""), item.get("course_name", "").title())
            title = (item.get("title") or "").strip()
            if not title:
                continue

            task_key = (subject.strip().lower(), self._normalize_task_title(title))
            if task_key in existing_keys:
                if command_user_id:
                    already_assigned.append({"subject": subject, "title": title})
                continue

            due_date = item.get("due_date") or "No asignada"
            target_channel = find_channel(guild, subject)
            if not target_channel:
                target_channel = find_channel(guild, CHANNELS.get("PENDING", ""))
            if not target_channel:
                continue

            embed = create_task_embed(title, subject, due_date, source_url=item.get("url"))
            embed.set_author(name="Detectado automáticamente desde CVirtual")

            try:
                msg = await target_channel.send(content="📥 **Nueva tarea detectada automáticamente**", embed=embed)
            except Exception:
                continue

            task_id = self.bot.db.add_task(
                subject,
                title,
                due_date,
                actor_id,
                guild.id,
                msg.id,
                target_channel.id,
                1,
            )
            self.bot.db.add_task_message(task_id, target_channel.id, msg.id)

            embed.set_footer(text=f"ID: {task_id} | Estado: Pendiente")
            try:
                await msg.edit(embed=embed)
            except Exception:
                pass

            dates_channel = find_channel(guild, "fechas-de-entrega")
            if dates_channel:
                try:
                    date_msg = await dates_channel.send(embed=embed)
                    self.bot.db.add_task_message(task_id, dates_channel.id, date_msg.id)
                except Exception:
                    pass

            created_tasks += 1
            existing_keys.add(task_key)

        return {"created_tasks": created_tasks, "already_assigned": already_assigned}

    async def _extract_due_date_from_assignment(self, session: aiohttp.ClientSession, assignment_url: str):
        html = await self._fetch_course_html(session, assignment_url)
        if not html:
            return "No asignada"

        detected = self._extract_due_date_from_html(html)
        return detected or "No asignada"

    def _extract_due_date_from_html(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        date_candidates = []

        for row in soup.select("tr"):
            header = row.select_one("th")
            value_cell = row.select_one("td")
            if not header or not value_cell:
                continue

            header_text = header.get_text(" ", strip=True).lower()
            if any(
                key in header_text
                for key in [
                    "fecha de entrega",
                    "fecha de cierre",
                    "fecha límite",
                    "fecha limite",
                    "due date",
                    "cut-off date",
                    "closing date",
                ]
            ):
                date_candidates.append(value_cell.get_text(" ", strip=True))

        for candidate in date_candidates:
            parsed = self._parse_due_date_text(candidate)
            if parsed:
                return parsed

        return None

    def _parse_due_date_text(self, raw_text: str):
        if not raw_text:
            return None

        text = re.sub(r"\s+", " ", raw_text).strip()
        lowered = text.lower()
        if any(token in lowered for token in ["no disponible", "not available", "sin fecha"]):
            return None

        for date_format in [
            "%d/%m/%Y %H:%M",
            "%d-%m-%Y %H:%M",
            "%Y-%m-%d %H:%M",
            "%d/%m/%Y %I:%M %p",
            "%d-%m-%Y %I:%M %p",
        ]:
            try:
                parsed = datetime.datetime.strptime(text, date_format)
                return parsed.strftime("%d/%m/%Y %H:%M")
            except ValueError:
                pass

        month_map_es = {
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

        month_map_en = {
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

        es_match = re.search(
            r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4}).*?(\d{1,2}):(\d{2})(?:\s*([ap]\.?(?:\s*)m\.?)?)?",
            lowered,
            re.IGNORECASE,
        )
        if es_match:
            day = int(es_match.group(1))
            month_name = es_match.group(2).lower()
            year = int(es_match.group(3))
            hour = int(es_match.group(4))
            minute = int(es_match.group(5))
            ampm = (es_match.group(6) or "").replace(".", "").replace(" ", "")

            month = month_map_es.get(month_name)
            if month:
                if ampm == "pm" and hour < 12:
                    hour += 12
                if ampm == "am" and hour == 12:
                    hour = 0
                try:
                    parsed = datetime.datetime(year, month, day, hour, minute)
                    return parsed.strftime("%d/%m/%Y %H:%M")
                except ValueError:
                    pass

        en_match = re.search(
            r"(\d{1,2})\s+([a-z]+)\s+(\d{4}).*?(\d{1,2}):(\d{2})(?:\s*([ap]m))?",
            lowered,
            re.IGNORECASE,
        )
        if en_match:
            day = int(en_match.group(1))
            month_name = en_match.group(2).lower()
            year = int(en_match.group(3))
            hour = int(en_match.group(4))
            minute = int(en_match.group(5))
            ampm = (en_match.group(6) or "").lower()

            month = month_map_en.get(month_name)
            if month:
                if ampm == "pm" and hour < 12:
                    hour += 12
                if ampm == "am" and hour == 12:
                    hour = 0
                try:
                    parsed = datetime.datetime(year, month, day, hour, minute)
                    return parsed.strftime("%d/%m/%Y %H:%M")
                except ValueError:
                    pass

        generic_match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4}).*?(\d{1,2}):(\d{2})", lowered)
        if generic_match:
            day = int(generic_match.group(1))
            month = int(generic_match.group(2))
            year = int(generic_match.group(3))
            hour = int(generic_match.group(4))
            minute = int(generic_match.group(5))
            try:
                parsed = datetime.datetime(year, month, day, hour, minute)
                return parsed.strftime("%d/%m/%Y %H:%M")
            except ValueError:
                pass

        return None

    def _normalize_task_title(self, title: str):
        return " ".join((title or "").strip().lower().split())

    async def _authenticate_session(self, session: aiohttp.ClientSession):
        username = os.getenv("CVIRTUAL_USER", "").strip()
        password = os.getenv("CVIRTUAL_PASSWORD", "").strip()

        if not username or not password:
            return False

        try:
            request_kwargs = self._cookie_request_kwargs()
            async with session.get(MOODLE_LOGIN_URL, **request_kwargs) as response:
                if response.status != 200:
                    return False
                login_html = await response.text()

            token = self._extract_login_token(login_html)
            payload = {
                "username": username,
                "password": password,
            }
            if token:
                payload["logintoken"] = token

            post_kwargs = self._cookie_request_kwargs()
            post_kwargs["data"] = payload

            async with session.post(MOODLE_LOGIN_URL, **post_kwargs) as response:
                final_url = str(response.url)
                html = await response.text()

            if "login/index.php" in final_url and "invalidlogin" in html.lower():
                print("CourseWatcher: credenciales Moodle inválidas.")
                return False

            return True
        except Exception as error:
            print(f"CourseWatcher: error autenticando en Moodle: {error}")
            return False

    async def _fetch_course_html(self, session: aiohttp.ClientSession, url: str) -> str:
        try:
            request_kwargs = self._cookie_request_kwargs()

            async with session.get(url, **request_kwargs) as response:
                if response.status != 200:
                    return ""
                return await response.text()
        except Exception:
            return ""

    def _cookie_request_kwargs(self):
        request_kwargs = {}
        cookie_header = os.getenv("CVIRTUAL_COOKIE", "").strip()
        if cookie_header:
            request_kwargs["headers"] = {"Cookie": cookie_header}
        return request_kwargs

    def _extract_login_token(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        token_input = soup.select_one("input[name='logintoken']")
        if token_input:
            return token_input.get("value", "")
        return ""

    def _extract_activities(
        self,
        course_name: str,
        course_url: str,
        html: str,
        forced_week_name: str | None = None,
    ):
        soup = BeautifulSoup(html, "html.parser")
        extracted = []
        global_week = forced_week_name or self._extract_global_current_week(soup)

        sections = soup.select(
            "li.section.main, li[id^='section-'], li.course-section, section.course-section, "
            "section[id*='section'], div.section, div[data-for='section']"
        )

        if sections:
            for section in sections:
                week_name = forced_week_name or self._extract_week_name(section)
                if week_name == "Semana no identificada" and global_week:
                    week_name = global_week

                activities = section.select("li.activity, div.activity, a[href*='/mod/forum/'], a[href*='/mod/assign/']")

                for activity in activities:
                    item = self._parse_activity_block(activity, course_name, course_url, week_name, global_week)
                    if item:
                        if forced_week_name:
                            item["week_name"] = forced_week_name
                        extracted.append(item)
        else:
            fallback_items = self._extract_fallback_links(soup, course_name, course_url, global_week)
            if forced_week_name:
                for item in fallback_items:
                    item["week_name"] = forced_week_name
            extracted.extend(fallback_items)

        return extracted

    def _resolve_target_week(self, soup: BeautifulSoup, course_url: str, requested_week: int | None = None):
        available_weeks = self._extract_available_weeks(soup, course_url)

        if requested_week is not None:
            selected = available_weeks.get(requested_week)
            if selected:
                return selected
            return {
                "week_number": requested_week,
                "week_name": f"Semana {requested_week}",
                "week_url": self._build_section_url(course_url, requested_week),
            }

        week_numbers = sorted(available_weeks.keys())
        if not week_numbers:
            return None

        filtered = [num for num in week_numbers if num >= MIN_WEEK_TO_SCAN]
        chosen_number = filtered[-1] if filtered else week_numbers[-1]
        return available_weeks[chosen_number]

    def _extract_available_weeks(self, soup: BeautifulSoup, course_url: str):
        weeks = {}

        for anchor in soup.select("a[href*='section='], a.nav-link[data-key]"):
            text = anchor.get_text(" ", strip=True)
            week_number = self._extract_week_number(text)
            if week_number is None:
                continue

            href = anchor.get("href", "")
            week_url = urljoin(course_url, href) if href else self._build_section_url(course_url, week_number)
            weeks[week_number] = {
                "week_number": week_number,
                "week_name": f"Semana {week_number}",
                "week_url": week_url,
            }

        for section in soup.select("li[id^='section-'], section[id^='section-']"):
            section_id = section.get("id", "")
            match = re.search(r"section-(\d+)", section_id, re.IGNORECASE)
            if not match:
                continue

            week_number = int(match.group(1))
            if week_number not in weeks:
                weeks[week_number] = {
                    "week_number": week_number,
                    "week_name": f"Semana {week_number}",
                    "week_url": self._build_section_url(course_url, week_number),
                }

        return weeks

    def _extract_week_number(self, text: str):
        match = WEEK_REGEX.search(text or "")
        if not match:
            return None

        number_match = re.search(r"\d+", match.group(0))
        if not number_match:
            return None

        return int(number_match.group(0))

    def _build_section_url(self, course_url: str, week_number: int):
        separator = "&" if "?" in course_url else "?"
        return f"{course_url}{separator}section={week_number}"

    def _extract_global_current_week(self, soup: BeautifulSoup):
        selectors = [
            ".nav-link.active",
            ".active[aria-selected='true']",
            "[aria-current='page']",
            ".courseindex-item.active",
            ".tab.active",
            ".week-navigation .active",
        ]

        for selector in selectors:
            for node in soup.select(selector):
                text = node.get_text(" ", strip=True)
                match = WEEK_REGEX.search(text)
                if match:
                    return match.group(0).title()

        return None

    def _extract_week_name(self, section) -> str:
        candidates = section.select(".sectionname, h3.sectionname, h4.sectionname, .section-title")
        for candidate in candidates:
            text = candidate.get_text(" ", strip=True)
            match = WEEK_REGEX.search(text)
            if match:
                return match.group(0).title()

        whole_text = section.get_text(" ", strip=True)
        match = WEEK_REGEX.search(whole_text)
        if match:
            return match.group(0).title()

        return "Semana no identificada"

    def _parse_activity_block(self, activity, course_name: str, course_url: str, week_name: str, global_week: str = None):
        classes = " ".join(activity.get("class", [])).lower()
        text = activity.get_text(" ", strip=True)

        activity_type = self._detect_activity_type(classes, text)
        if not activity_type:
            return None

        if getattr(activity, "name", "") == "a":
            anchor = activity
        else:
            anchor = activity.select_one("a.aalink, a.activityinstance, a[href*='/mod/']")

        if not anchor:
            return None

        href = anchor.get("href")
        if not href:
            return None

        title = anchor.get_text(" ", strip=True)
        if not title:
            title = text[:180]

        resolved_week = week_name
        if resolved_week == "Semana no identificada":
            resolved_week = self._infer_week_from_context(anchor, global_week)

        return {
            "course_name": course_name,
            "week_name": resolved_week,
            "activity_type": activity_type,
            "title": title,
            "url": urljoin(course_url, href),
        }

    def _extract_fallback_links(self, soup: BeautifulSoup, course_name: str, course_url: str, global_week: str = None):
        items = []
        links = soup.select("a[href*='/mod/forum/'], a[href*='/mod/assign/']")

        for anchor in links:
            href = anchor.get("href")
            if not href:
                continue

            text = anchor.get_text(" ", strip=True)
            lower_href = href.lower()

            if "/mod/forum/" in lower_href:
                activity_type = "FORO"
            elif "/mod/assign/" in lower_href:
                activity_type = "TAREA"
            else:
                activity_type = self._detect_activity_type("", text)

            if not activity_type:
                continue

            section = anchor.find_parent(["li", "section", "div"])
            week_name = self._extract_week_name(section) if section else "Semana no identificada"
            if week_name == "Semana no identificada":
                week_name = self._infer_week_from_context(anchor, global_week)

            items.append(
                {
                    "course_name": course_name,
                    "week_name": week_name,
                    "activity_type": activity_type,
                    "title": text or "Actividad sin título",
                    "url": urljoin(course_url, href),
                }
            )

        return items

    def _infer_week_from_context(self, node, default_week: str = None):
        current = node
        depth = 0
        while current is not None and depth < 7:
            text = current.get_text(" ", strip=True)
            match = WEEK_REGEX.search(text)
            if match:
                return match.group(0).title()
            current = current.parent
            depth += 1

        sibling = getattr(node, "previous_sibling", None)
        checks = 0
        while sibling is not None and checks < 8:
            try:
                text = sibling.get_text(" ", strip=True)
            except Exception:
                text = str(sibling)
            match = WEEK_REGEX.search(text)
            if match:
                return match.group(0).title()
            sibling = getattr(sibling, "previous_sibling", None)
            checks += 1

        return default_week or "Semana no identificada"

    def _detect_activity_type(self, classes_text: str, visible_text: str):
        normalized = f"{classes_text} {visible_text}".lower()

        if "forum" in normalized or "foro" in normalized:
            return "FORO"
        if "assign" in normalized or "tarea" in normalized:
            return "TAREA"
        return None

    def _hash_item(self, item: dict) -> str:
        payload = "|".join(
            [
                item["course_name"].strip().lower(),
                item["week_name"].strip().lower(),
                item["activity_type"].strip().lower(),
                item["title"].strip().lower(),
                item["url"].strip().lower(),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _resolve_updates_channel(self, guild: discord.Guild):
        preferred_queries = [
            CHANNELS.get("COURSE_UPDATES", ""),
            "aviso tareas",
            "avisos-tareas-pendientes",
        ]

        for query in preferred_queries:
            channel = find_channel(guild, query)
            if channel:
                return channel

        return None

    def _build_activity_embed(self, item: dict) -> discord.Embed:
        color = 0xF1C40F if item["activity_type"] == "FORO" else 0x3498DB
        embed = discord.Embed(title="📌 Nueva actividad detectada", color=color)
        embed.add_field(name="Curso", value=item["course_name"], inline=False)
        embed.add_field(name="Semana", value=item["week_name"], inline=True)
        embed.add_field(name="Tipo", value=item["activity_type"], inline=True)
        embed.add_field(name="Título", value=item["title"][:1024], inline=False)
        embed.add_field(name="Link", value=item["url"], inline=False)
        embed.set_footer(text="Monitor académico S4VI_BOT")
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(CourseWatcher(bot))
