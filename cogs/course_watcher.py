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

COURSES = {
    "INFRAESTRUCTURA DE RED": "https://www.cvirtualuees.edu.sv/course/view.php?id=23879",
    "ETICA": "https://www.cvirtualuees.edu.sv/course/view.php?id=23881",
    "FUNDAMENTOS DE PROGRAMACION": "https://www.cvirtualuees.edu.sv/course/view.php?id=23880",
    "MATEMATICA": "https://www.cvirtualuees.edu.sv/course/view.php?id=23878",
    "SEGURIDAD DE LA INFORMACION": "https://www.cvirtualuees.edu.sv/course/view.php?id=23877",
}

SCHEDULE_SLOTS = {
    (0, 6, 0),   # Lunes 06:00
    (2, 18, 0),  # Miércoles 18:00
    (4, 23, 0),  # Viernes 23:00
}

TIMEZONE_NAME = "America/El_Salvador"
WEEK_REGEX = re.compile(r"semana\s*\d+", re.IGNORECASE)


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
    async def tareas_nuevas(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        new_items_total = 0
        for guild in self.bot.guilds:
            if interaction.guild and guild.id != interaction.guild.id:
                continue

            created = await self._scan_and_notify(guild)
            new_items_total += created

        if new_items_total == 0:
            await interaction.followup.send("No se detectaron actividades nuevas (Foro/Tarea).", ephemeral=True)
            return

        await interaction.followup.send(
            f"Escaneo completado. Se detectaron {new_items_total} actividades nuevas y se publicaron en el canal de avisos.",
            ephemeral=True,
        )

    async def _scan_and_notify(self, guild: discord.Guild) -> int:
        channel = self._resolve_updates_channel(guild)
        if not channel:
            return 0

        new_items = await self._scan_courses_for_guild(guild.id)
        for item in new_items:
            embed = self._build_activity_embed(item)
            await channel.send(embed=embed)

        return len(new_items)

    async def _scan_courses_for_guild(self, guild_id: int):
        new_items = []

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for course_name, course_url in COURSES.items():
                html = await self._fetch_course_html(session, course_url)
                if not html:
                    continue

                items = self._extract_activities(course_name, course_url, html)
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

    async def _fetch_course_html(self, session: aiohttp.ClientSession, url: str) -> str:
        try:
            request_kwargs = {}
            cookie_header = os.getenv("CVIRTUAL_COOKIE", "").strip()
            if cookie_header:
                request_kwargs["headers"] = {"Cookie": cookie_header}

            async with session.get(url, **request_kwargs) as response:
                if response.status != 200:
                    return ""
                return await response.text()
        except Exception:
            return ""

    def _extract_activities(self, course_name: str, course_url: str, html: str):
        soup = BeautifulSoup(html, "html.parser")
        extracted = []

        sections = soup.select("li.section.main, li[id^='section-'], section.course-section")

        if sections:
            for section in sections:
                week_name = self._extract_week_name(section)
                activities = section.select("li.activity, div.activity")

                for activity in activities:
                    item = self._parse_activity_block(activity, course_name, course_url, week_name)
                    if item:
                        extracted.append(item)
        else:
            extracted.extend(self._extract_fallback_links(soup, course_name, course_url))

        return extracted

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

    def _parse_activity_block(self, activity, course_name: str, course_url: str, week_name: str):
        classes = " ".join(activity.get("class", [])).lower()
        text = activity.get_text(" ", strip=True)

        activity_type = self._detect_activity_type(classes, text)
        if not activity_type:
            return None

        anchor = activity.select_one("a.aalink, a.activityinstance, a[href*='/mod/']")
        if not anchor:
            return None

        href = anchor.get("href")
        if not href:
            return None

        title = anchor.get_text(" ", strip=True)
        if not title:
            title = text[:180]

        return {
            "course_name": course_name,
            "week_name": week_name,
            "activity_type": activity_type,
            "title": title,
            "url": urljoin(course_url, href),
        }

    def _extract_fallback_links(self, soup: BeautifulSoup, course_name: str, course_url: str):
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
