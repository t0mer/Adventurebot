import datetime
import logging
import os
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from . import scheduler_store
from .keyboards import schedulers_menu, scheduler_detail
from .scheduler_jobs import checklist_reminder_job, evening_digest_job

logger = logging.getLogger(__name__)

SETTING_SCHED_TIME = 10
SETTING_SCHED_TZ = 11

_JOB_FUNCTIONS = {
    "checklist_reminder": checklist_reminder_job,
    "evening_digest": evening_digest_job,
}

_DISPLAY_NAMES = {
    "checklist_reminder": "📋 Checklist reminder",
    "evening_digest": "🌙 Evening digest",
}


def _reschedule(app, name: str) -> None:
    for job in app.job_queue.get_jobs_by_name(name):
        job.schedule_removal()

    config = scheduler_store.load()
    entry = scheduler_store.get_scheduler(config, name)

    if not entry.get("enabled"):
        return

    tz_name = entry.get("timezone") or os.environ.get("TZ", "UTC")
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Invalid timezone %r for %r, falling back to TZ env", tz_name, name)
        tz = ZoneInfo(os.environ.get("TZ", "UTC"))

    hh, mm = map(int, entry["time"].split(":"))
    t = datetime.time(hh, mm, tzinfo=tz)
    app.job_queue.run_daily(_JOB_FUNCTIONS[name], time=t, name=name)
    logger.info("Scheduled %s at %s %s", name, entry["time"], tz_name)


def _detail_text(name: str, entry: dict) -> str:
    tz = entry.get("timezone") or os.environ.get("TZ", "UTC")
    status = "✓ Enabled" if entry["enabled"] else "✗ Disabled"
    return f"{_DISPLAY_NAMES[name]}\nStatus: {status}\nTime: {entry['time']}\nTimezone: {tz}"


async def handle_schedulers_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    config = scheduler_store.load()
    text = "⏰ Schedulers\nTap a scheduler to configure it."
    markup = schedulers_menu(config)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)


async def handle_scheduler_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    name = update.callback_query.data.split(":")[2]
    config = scheduler_store.load()
    entry = scheduler_store.get_scheduler(config, name)
    await update.callback_query.edit_message_text(
        _detail_text(name, entry),
        reply_markup=scheduler_detail(name, entry),
    )


async def handle_scheduler_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    name = update.callback_query.data.split(":")[2]
    config = scheduler_store.load()
    entry = scheduler_store.get_scheduler(config, name)
    config = scheduler_store.update_scheduler(config, name, enabled=not entry["enabled"])
    scheduler_store.save(config)
    _reschedule(ctx.application, name)
    entry = scheduler_store.get_scheduler(config, name)
    await update.callback_query.edit_message_text(
        _detail_text(name, entry),
        reply_markup=scheduler_detail(name, entry),
    )


async def handle_scheduler_set_time_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    name = update.callback_query.data.split(":")[2]
    ctx.user_data["sched_name"] = name
    await update.callback_query.edit_message_text(
        "Send me the new time in HH:MM (24h) format."
    )
    return SETTING_SCHED_TIME


async def handle_scheduler_set_time_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    name = ctx.user_data.get("sched_name", "")
    match = re.match(r"^(\d{2}):(\d{2})$", text)
    if not match or not (0 <= int(match.group(1)) <= 23 and 0 <= int(match.group(2)) <= 59):
        await update.message.reply_text("Invalid time. Please use HH:MM format (e.g. 08:30).")
        return SETTING_SCHED_TIME
    config = scheduler_store.load()
    config = scheduler_store.update_scheduler(config, name, time=text)
    scheduler_store.save(config)
    _reschedule(ctx.application, name)
    await update.message.reply_text(f"✅ Time set to {text}.")
    return ConversationHandler.END


async def handle_scheduler_set_tz_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    name = update.callback_query.data.split(":")[2]
    ctx.user_data["sched_name"] = name
    await update.callback_query.edit_message_text(
        "Send me the timezone name (e.g. Asia/Jerusalem, Europe/London)."
    )
    return SETTING_SCHED_TZ


async def handle_scheduler_set_tz_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    from zoneinfo import available_timezones
    tz = update.message.text.strip()
    name = ctx.user_data.get("sched_name", "")
    if tz not in available_timezones():
        await update.message.reply_text(
            "Unknown timezone. Try a name like Asia/Jerusalem or Europe/London."
        )
        return SETTING_SCHED_TZ
    config = scheduler_store.load()
    config = scheduler_store.update_scheduler(config, name, timezone=tz)
    scheduler_store.save(config)
    _reschedule(ctx.application, name)
    await update.message.reply_text(f"✅ Timezone set to {tz}.")
    return ConversationHandler.END
