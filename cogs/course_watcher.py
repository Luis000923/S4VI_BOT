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
from utils.date_ai import DueDateAI
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
        self.due_date_ai = DueDateAI(default_hour=12, default_minute=0)
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
    @app_commands.checks.cooldown(1, 1800.0, key=lambda interaction: interaction.guild_id or interaction.user.id)
    async def tareas_nuevas(
        self,
        interaction: discord.Interaction,
        semana: app_commands.Range[int, 1, 60] | None = None,
    ):
        await interaction.response.defer(ephemeral=True)

        new_items_total = 0
        created_tasks_total = 0
        updated_tasks_total = 0
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
            updated_tasks_total += report.get("updated_tasks", 0)
            already_assigned_items.extend(report["already_assigned"])

        if new_items_total == 0 and created_tasks_total == 0 and updated_tasks_total == 0 and not already_assigned_items:
            week_text = f" en Semana {semana}" if semana is not None else ""
            await interaction.followup.send(
                f"No se detectaron actividades nuevas (Foro/Tarea){week_text}.",
                ephemeral=True,
            )
            return

        summary_lines = [
            f"Escaneo completado: {new_items_total} actividades nuevas detectadas.",
            f"Tareas programadas en canales de materia: {created_tasks_total}.",
            f"Tareas existentes actualizadas por cambios en CVirtual: {updated_tasks_total}.",
        ]

        if already_assigned_items:
            summary_lines.append("\nTareas ya asignadas (mostradas solo para ti):")
            for item in already_assigned_items[:12]:
                summary_lines.append(f"- {item['subject']}: {item['title']}")
            if len(already_assigned_items) > 12:
                summary_lines.append(f"- ... y {len(already_assigned_items) - 12} más")

        await interaction.followup.send("\n".join(summary_lines), ephemeral=True)

    @tareas_nuevas.error
    async def tareas_nuevas_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            wait_seconds = max(1, int(error.retry_after))
            minutes = wait_seconds // 60
            seconds = wait_seconds % 60
            await interaction.response.send_message(
                f"Este comando puede usarse 1 vez cada 30 minutos. Intenta de nuevo en {minutes}m {seconds}s.",
                ephemeral=True,
            )
            return
        raise error

    async def _scan_and_notify(
        self,
        guild: discord.Guild,
        requested_week: int | None = None,
        command_user_id: int | None = None,
    ) -> dict:
        channel = self._resolve_updates_channel(guild)
        scan_result = await self._scan_courses_for_guild(guild.id, requested_week=requested_week)
        new_items = scan_result["new_items"]
        detected_items = scan_result["detected_items"]

        if channel:
            for item in new_items:
                embed = self._build_activity_embed(item)
                await channel.send(embed=embed)

        task_report = await self._schedule_detected_tasks(
            guild,
            detected_items,
            command_user_id=command_user_id,
        )

        return {
            "new_activities": len(new_items),
            "created_tasks": task_report["created_tasks"],
            "updated_tasks": task_report.get("updated_tasks", 0),
            "already_assigned": task_report["already_assigned"],
        }

    async def _scan_courses_for_guild(self, guild_id: int, requested_week: int | None = None):
        new_items = []
        detected_items = []

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
                        details = await self._extract_assignment_details(session, item["url"])
                        item["due_date"] = details["due_date"]
                        item["instructions"] = details["instructions"]

                    detected_items.append(item)

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

        return {
            "new_items": new_items,
            "detected_items": detected_items,
        }

    async def _schedule_detected_tasks(self, guild: discord.Guild, items: list[dict], command_user_id: int | None = None):
        created_tasks = 0
        updated_tasks = 0
        already_assigned = []
        channel_cache = {}

        def resolve_channel(name: str):
            key = (name or "").strip().lower()
            if key not in channel_cache:
                channel_cache[key] = find_channel(guild, name)
            return channel_cache[key]

        if not items:
            return {"created_tasks": 0, "updated_tasks": 0, "already_assigned": []}

        tasks_cache = self.bot.db.get_tasks(guild.id)
        existing_by_key = {}
        existing_by_source_url = {}
        for task in tasks_cache:
            subject = (task[1] or "").strip().lower()
            normalized_title = self._normalize_task_title(task[2] or "")
            existing_by_key[(subject, normalized_title)] = task
            source_url = ""
            if len(task) > 9 and task[9]:
                source_url = str(task[9]).strip()
            if source_url:
                existing_by_source_url[source_url] = task

        actor_id = command_user_id or getattr(self.bot.user, "id", 0) or 0

        for item in items:
            if item.get("activity_type") != "TAREA":
                continue

            subject = COURSE_SUBJECT_MAP.get(item.get("course_name", ""), item.get("course_name", "").title())
            title = (item.get("title") or "").strip()
            if not title:
                continue

            task_key = (subject.strip().lower(), self._normalize_task_title(title))
            due_date = item.get("due_date") or "No asignada"
            instructions = item.get("instructions")
            source_url = item.get("url")

            existing_task = None
            if source_url:
                existing_task = existing_by_source_url.get(source_url)
            if not existing_task:
                existing_task = existing_by_key.get(task_key)

            if existing_task:
                task_id = existing_task[0]
                current_subject = existing_task[1] or ""
                current_title = existing_task[2] or ""
                current_due = existing_task[3] or ""
                current_source_url = ""
                if len(existing_task) > 9 and existing_task[9]:
                    current_source_url = str(existing_task[9]).strip()

                should_update_title = current_title.strip() != title.strip()
                should_update_subject = current_subject.strip() != subject.strip()
                should_update_due = current_due.strip() != due_date.strip()
                should_update_source_url = bool(source_url) and current_source_url != source_url

                if should_update_title or should_update_subject or should_update_due or should_update_source_url:
                    self.bot.db.update_task(
                        task_id,
                        title=title if should_update_title else None,
                        due_date=due_date if should_update_due else None,
                        subject=subject if should_update_subject else None,
                        source_url=source_url if should_update_source_url else None,
                    )

                    await self._refresh_task_messages(
                        guild,
                        task_id,
                        subject,
                        title,
                        due_date,
                        source_url=source_url,
                        instructions=instructions,
                    )

                    updated_tasks += 1
                elif command_user_id:
                    already_assigned.append({"subject": subject, "title": title})

                continue

            target_channel = resolve_channel(subject)
            if not target_channel:
                target_channel = resolve_channel(CHANNELS.get("PENDING", ""))
            if not target_channel:
                continue

            embed = create_task_embed(
                title,
                subject,
                due_date,
                source_url=item.get("url"),
                instructions=item.get("instructions"),
            )
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
                source_url=source_url,
            )
            self.bot.db.add_task_message(task_id, target_channel.id, msg.id)

            embed.set_footer(text=f"ID: {task_id} | Estado: Pendiente")
            try:
                await msg.edit(embed=embed)
            except Exception:
                pass

            dates_channel = resolve_channel("fechas-de-entrega")
            if dates_channel:
                try:
                    date_msg = await dates_channel.send(embed=embed)
                    self.bot.db.add_task_message(task_id, dates_channel.id, date_msg.id)
                except Exception:
                    pass

            created_tasks += 1
            existing_by_key[task_key] = (
                task_id,
                subject,
                title,
                due_date,
                None,
                None,
                None,
                None,
                None,
                source_url,
            )
            if source_url:
                existing_by_source_url[source_url] = existing_by_key[task_key]

        return {
            "created_tasks": created_tasks,
            "updated_tasks": updated_tasks,
            "already_assigned": already_assigned,
        }

    async def _refresh_task_messages(
        self,
        guild: discord.Guild,
        task_id: int,
        subject: str,
        title: str,
        due_date: str,
        source_url: str | None = None,
        instructions: str | None = None,
    ):
        tracked_messages = self.bot.db.get_task_messages(task_id)
        if not tracked_messages:
            return

        updated_embed = create_task_embed(
            title,
            subject,
            due_date,
            source_url=source_url,
            instructions=instructions,
        )
        updated_embed.set_footer(text=f"ID: {task_id} | Estado: Pendiente")

        for channel_id, message_id in tracked_messages:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=updated_embed)
            except Exception:
                continue

    async def _extract_assignment_details(self, session: aiohttp.ClientSession, assignment_url: str):
        html = await self._fetch_course_html(session, assignment_url)
        if not html:
            return {
                "due_date": "No asignada",
                "instructions": None,
            }

        detected_due_date = self._extract_due_date_from_html(html)
        detected_instructions = self._extract_instructions_from_html(html)
        return {
            "due_date": detected_due_date or "No asignada",
            "instructions": detected_instructions,
        }

    def _extract_instructions_from_html(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        selectors = [
            "#intro .no-overflow",
            "#intro",
            ".activity-description .no-overflow",
            ".activity-description",
            "div.assignintro",
            ".assignintro",
            "[data-region='activity-description']",
        ]

        for selector in selectors:
            node = soup.select_one(selector)
            if not node:
                continue

            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            if not text:
                continue

            cleaned = re.sub(r"^(indicaciones|instrucciones|description)\s*:\s*", "", text, flags=re.IGNORECASE)
            if cleaned:
                return cleaned

        return None

    def _extract_due_date_from_html(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        date_candidates = []

        due_label_priority = {
            "fecha de entrega": 1,
            "fecha de cierre": 1,
            "fecha límite": 1,
            "fecha limite": 1,
            "vencimiento": 1,
            "cierre": 2,
            "due date": 1,
            "cut-off date": 1,
            "closing date": 1,
        }

        def get_label_priority(label: str):
            normalized = (label or "").strip().lower()
            for key, priority in due_label_priority.items():
                if key in normalized:
                    return priority
            return None

        for row in soup.select("tr"):
            header = row.select_one("th")
            value_cell = row.select_one("td")
            if not header or not value_cell:
                continue

            header_text = header.get_text(" ", strip=True)
            priority = get_label_priority(header_text)
            if priority is None:
                continue
            date_candidates.append((priority, value_cell.get_text(" ", strip=True)))

        for strong_node in soup.select("strong"):
            label_text = strong_node.get_text(" ", strip=True)
            priority = get_label_priority(label_text)
            if priority is None:
                continue

            parent = strong_node.parent
            if not parent:
                continue

            row_text = parent.get_text(" ", strip=True)
            value_text = re.sub(r"^\s*[^:]{1,80}:\s*", "", row_text).strip()
            if not value_text:
                continue

            date_candidates.append((priority, value_text))

        date_candidates.sort(key=lambda item: item[0])

        for _, candidate in date_candidates:
            parsed = self._parse_due_date_text(candidate)
            if parsed:
                return parsed

        return None

    def _parse_due_date_text(self, raw_text: str):
        return self.due_date_ai.normalize(raw_text)

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
                    print(f"CourseWatcher: status {response.status} al obtener login page")
                    return False
                login_html = await response.text()
                
                # Detectar si Cloudflare o Moodle devolvió una página de error
                if self._is_cloudflare_or_error_page(login_html):
                    print("CourseWatcher: respuesta bloqueada o error (posible Cloudflare)")
                    return False

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
                
                # Validar respuesta
                if self._is_cloudflare_or_error_page(html):
                    print("CourseWatcher: respuesta post bloqueada o error")
                    return False

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
                    print(f"CourseWatcher: status {response.status} en {url}")
                    return ""
                
                html = await response.text()
                
                # Detectar si es página de Cloudflare o error
                if self._is_cloudflare_or_error_page(html):
                    print(f"CourseWatcher: página bloqueada/error en {url}")
                    return ""
                
                return html
        except Exception as error:
            print(f"CourseWatcher: excepción al cargar {url}: {error}")
            return ""
    
    def _is_cloudflare_or_error_page(self, html: str) -> bool:
        """Detecta si la respuesta es una página de error/bloqueo de Cloudflare"""
        if not html:
            return False
        html_lower = html.lower()
        # Detectar características de error Cloudflare
        if "cloudflare" in html_lower and ("error" in html_lower or "challenge" in html_lower):
            return True
        # Detectar error pages generales
        if any(phrase in html_lower for phrase in ["error 1015", "error 429", "error 403", "you are being rate limited"]):
            return True
        return False

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
