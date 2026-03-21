import logging
from discord.ext import commands, tasks


class Stability(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("s4vi.stability")
        if not self.watchdog.is_running():
            self.watchdog.start()

    def cog_unload(self):
        self.watchdog.cancel()

    @tasks.loop(minutes=2)
    async def watchdog(self):
        try:
            await self._ensure_course_watcher_loop()
            await self._ensure_reminders_loop()
        except Exception:
            self.logger.exception("Watchdog detectó un error inesperado")

    @watchdog.before_loop
    async def before_watchdog(self):
        await self.bot.wait_until_ready()

    @watchdog.error
    async def watchdog_error(self, error: Exception):
        self.logger.exception("Loop watchdog se detuvo por error: %s", error)

    async def _ensure_course_watcher_loop(self):
        cog = self.bot.get_cog("CourseWatcher")
        if cog is None:
            return

        loop_task = getattr(cog, "scan_courses_task", None)
        if loop_task is None:
            return

        if not loop_task.is_running():
            self.logger.warning("Watchdog reiniciando loop scan_courses_task")
            loop_task.restart()
            return

        if loop_task.failed():
            self.logger.warning("Watchdog detectó loop scan_courses_task en estado failed; reiniciando")
            loop_task.restart()

    async def _ensure_reminders_loop(self):
        cog = self.bot.get_cog("Reminders")
        if cog is None:
            return

        loop_task = getattr(cog, "check_reminders", None)
        if loop_task is None:
            return

        if not loop_task.is_running():
            self.logger.warning("Watchdog reiniciando loop check_reminders")
            loop_task.restart()
            return

        if loop_task.failed():
            self.logger.warning("Watchdog detectó loop check_reminders en estado failed; reiniciando")
            loop_task.restart()


async def setup(bot: commands.Bot):
    await bot.add_cog(Stability(bot))
