import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Chat, Message, CallbackQuery
from telegram.ext import ContextTypes, ConversationHandler

from bot import scheduler_handlers


def make_callback_update(data: str) -> Update:
    chat = MagicMock(spec=Chat)
    chat.id = 100
    msg = MagicMock(spec=Message)
    msg.chat = chat
    msg.edit_text = AsyncMock()
    cq = MagicMock(spec=CallbackQuery)
    cq.data = data
    cq.answer = AsyncMock()
    cq.message = msg
    cq.edit_message_text = AsyncMock()
    upd = MagicMock(spec=Update)
    upd.effective_chat = chat
    upd.callback_query = cq
    upd.message = None
    return upd


def make_message_update(text: str) -> Update:
    chat = MagicMock(spec=Chat)
    chat.id = 100
    msg = MagicMock(spec=Message)
    msg.chat = chat
    msg.text = text
    msg.reply_text = AsyncMock()
    upd = MagicMock(spec=Update)
    upd.effective_chat = chat
    upd.callback_query = None
    upd.message = msg
    return upd


def make_context():
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.user_data = {}
    ctx.application = MagicMock()
    ctx.application.job_queue.get_jobs_by_name.return_value = []
    ctx.application.job_queue.run_daily = MagicMock()
    return ctx


# ─── schedulers menu ─────────────────────────────────────────────────────────

async def test_handle_schedulers_menu_from_callback(tmp_path):
    from bot import scheduler_store
    with patch.object(scheduler_store, "CONFIG_PATH", str(tmp_path / "s.json")):
        upd = make_callback_update("sched:menu")
        ctx = make_context()
        await scheduler_handlers.handle_schedulers_menu(upd, ctx)
    upd.callback_query.edit_message_text.assert_awaited_once()
    _, kwargs = upd.callback_query.edit_message_text.call_args
    assert kwargs["reply_markup"] is not None


async def test_handle_schedulers_menu_from_command(tmp_path):
    from bot import scheduler_store
    with patch.object(scheduler_store, "CONFIG_PATH", str(tmp_path / "s.json")):
        upd = make_message_update("/schedulers")
        ctx = make_context()
        await scheduler_handlers.handle_schedulers_menu(upd, ctx)
    upd.message.reply_text.assert_awaited_once()


# ─── scheduler detail ────────────────────────────────────────────────────────

async def test_handle_scheduler_detail_shows_settings(tmp_path):
    from bot import scheduler_store
    with patch.object(scheduler_store, "CONFIG_PATH", str(tmp_path / "s.json")):
        upd = make_callback_update("sched:detail:checklist_reminder")
        ctx = make_context()
        await scheduler_handlers.handle_scheduler_detail(upd, ctx)
    upd.callback_query.edit_message_text.assert_awaited_once()
    text = upd.callback_query.edit_message_text.call_args.args[0]
    assert "09:00" in text
    assert "Disabled" in text or "Enabled" in text


# ─── toggle ──────────────────────────────────────────────────────────────────

async def test_handle_scheduler_toggle_flips_enabled(tmp_path):
    from bot import scheduler_store
    path = str(tmp_path / "s.json")
    with patch.object(scheduler_store, "CONFIG_PATH", path):
        upd = make_callback_update("sched:toggle:checklist_reminder")
        ctx = make_context()
        await scheduler_handlers.handle_scheduler_toggle(upd, ctx)
        config = scheduler_store.load()
    assert config["checklist_reminder"]["enabled"] is True


# ─── set time conversation ───────────────────────────────────────────────────

async def test_handle_set_time_go_enters_conversation(tmp_path):
    from bot import scheduler_store
    with patch.object(scheduler_store, "CONFIG_PATH", str(tmp_path / "s.json")):
        upd = make_callback_update("sched:settime:checklist_reminder")
        ctx = make_context()
        result = await scheduler_handlers.handle_scheduler_set_time_go(upd, ctx)
    assert result == scheduler_handlers.SETTING_SCHED_TIME
    assert ctx.user_data["sched_name"] == "checklist_reminder"


async def test_handle_set_time_text_valid_saves_and_ends(tmp_path):
    from bot import scheduler_store
    path = str(tmp_path / "s.json")
    with patch.object(scheduler_store, "CONFIG_PATH", path):
        upd = make_message_update("08:30")
        ctx = make_context()
        ctx.user_data["sched_name"] = "checklist_reminder"
        result = await scheduler_handlers.handle_scheduler_set_time_text(upd, ctx)
        config = scheduler_store.load()
    assert result == ConversationHandler.END
    assert config["checklist_reminder"]["time"] == "08:30"


async def test_handle_set_time_text_invalid_stays_in_state():
    upd = make_message_update("99:99")
    ctx = make_context()
    ctx.user_data["sched_name"] = "checklist_reminder"
    result = await scheduler_handlers.handle_scheduler_set_time_text(upd, ctx)
    assert result == scheduler_handlers.SETTING_SCHED_TIME
    upd.message.reply_text.assert_awaited_once()
    text = upd.message.reply_text.call_args.args[0]
    assert "HH:MM" in text


# ─── set timezone conversation ───────────────────────────────────────────────

async def test_handle_set_tz_go_enters_conversation():
    upd = make_callback_update("sched:settz:evening_digest")
    ctx = make_context()
    result = await scheduler_handlers.handle_scheduler_set_tz_go(upd, ctx)
    assert result == scheduler_handlers.SETTING_SCHED_TZ
    assert ctx.user_data["sched_name"] == "evening_digest"


async def test_handle_set_tz_text_valid_saves_and_ends(tmp_path):
    from bot import scheduler_store
    path = str(tmp_path / "s.json")
    with patch.object(scheduler_store, "CONFIG_PATH", path):
        upd = make_message_update("Europe/London")
        ctx = make_context()
        ctx.user_data["sched_name"] = "evening_digest"
        result = await scheduler_handlers.handle_scheduler_set_tz_text(upd, ctx)
        config = scheduler_store.load()
    assert result == ConversationHandler.END
    assert config["evening_digest"]["timezone"] == "Europe/London"


async def test_handle_set_tz_text_invalid_stays_in_state():
    upd = make_message_update("Not/ATimezone")
    ctx = make_context()
    ctx.user_data["sched_name"] = "evening_digest"
    result = await scheduler_handlers.handle_scheduler_set_tz_text(upd, ctx)
    assert result == scheduler_handlers.SETTING_SCHED_TZ
    upd.message.reply_text.assert_awaited_once()


# ─── _reschedule ─────────────────────────────────────────────────────────────

def test_reschedule_registers_job_when_enabled(tmp_path):
    from bot import scheduler_store
    path = str(tmp_path / "s.json")
    with patch.object(scheduler_store, "CONFIG_PATH", path):
        config = scheduler_store.load()
        config = scheduler_store.update_scheduler(config, "checklist_reminder", enabled=True)
        scheduler_store.save(config)
        app = MagicMock()
        app.job_queue.get_jobs_by_name.return_value = []
        scheduler_handlers._reschedule(app, "checklist_reminder")
    app.job_queue.run_daily.assert_called_once()


def test_reschedule_does_not_register_when_disabled(tmp_path):
    from bot import scheduler_store
    with patch.object(scheduler_store, "CONFIG_PATH", str(tmp_path / "s.json")):
        app = MagicMock()
        app.job_queue.get_jobs_by_name.return_value = []
        scheduler_handlers._reschedule(app, "checklist_reminder")
    app.job_queue.run_daily.assert_not_called()


def test_reschedule_removes_existing_job(tmp_path):
    from bot import scheduler_store
    with patch.object(scheduler_store, "CONFIG_PATH", str(tmp_path / "s.json")):
        existing_job = MagicMock()
        app = MagicMock()
        app.job_queue.get_jobs_by_name.return_value = [existing_job]
        scheduler_handlers._reschedule(app, "checklist_reminder")
    existing_job.schedule_removal.assert_called_once()
