import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_job_context(client, chat_id=100):
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.application.bot_data = {"client": client, "chat_id": chat_id}
    return ctx


def make_client(checklists=None, checklist_detail=None, collections=None,
                visits=None, transportations=None, locations=None):
    cl = AsyncMock()
    cl.get_checklists.return_value = checklists or []
    cl.get_checklist.return_value = checklist_detail or {}
    cl.get_collections.return_value = collections or []
    cl.get_visits.return_value = visits or []
    cl.get_transportations.return_value = transportations or []
    cl.get_locations.return_value = locations or []
    return cl


# ─── checklist_reminder_job ──────────────────────────────────────────────────

async def test_checklist_reminder_silent_when_no_chat_id():
    from bot.scheduler_jobs import checklist_reminder_job
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.application.bot_data = {"client": make_client()}  # no chat_id key
    await checklist_reminder_job(ctx)
    ctx.bot.send_message.assert_not_awaited()


async def test_checklist_reminder_silent_when_all_complete():
    from bot.scheduler_jobs import checklist_reminder_job
    client = make_client(
        checklists=[{"id": "cl1", "name": "Packing", "collection": "trip1"}],
        checklist_detail={"id": "cl1", "name": "Packing", "collection": "trip1",
                          "items": [{"name": "Passport", "is_checked": True}]},
        collections=[{"id": "trip1", "name": "Europe Trip"}],
    )
    ctx = make_job_context(client)
    await checklist_reminder_job(ctx)
    ctx.bot.send_message.assert_not_awaited()


async def test_checklist_reminder_sends_when_incomplete_items():
    from bot.scheduler_jobs import checklist_reminder_job
    client = make_client(
        checklists=[{"id": "cl1", "name": "Packing", "collection": "trip1"}],
        checklist_detail={"id": "cl1", "name": "Packing", "collection": "trip1",
                          "items": [
                              {"name": "Passport", "is_checked": False},
                              {"name": "Adapter", "is_checked": True},
                          ]},
        collections=[{"id": "trip1", "name": "Europe Trip"}],
    )
    ctx = make_job_context(client)
    await checklist_reminder_job(ctx)
    ctx.bot.send_message.assert_awaited_once()
    text = ctx.bot.send_message.call_args.kwargs["text"]
    assert "Passport" in text
    assert "Packing" in text
    assert "Europe Trip" in text


async def test_checklist_reminder_groups_uncollected_under_other():
    from bot.scheduler_jobs import checklist_reminder_job
    client = make_client(
        checklists=[{"id": "cl1", "name": "Misc", "collection": None}],
        checklist_detail={"id": "cl1", "name": "Misc", "collection": None,
                          "items": [{"name": "Book hotel", "is_checked": False}]},
        collections=[],
    )
    ctx = make_job_context(client)
    await checklist_reminder_job(ctx)
    text = ctx.bot.send_message.call_args.kwargs["text"]
    assert "Other" in text
    assert "Book hotel" in text


# ─── evening_digest_job ──────────────────────────────────────────────────────

async def test_evening_digest_silent_when_no_chat_id():
    from bot.scheduler_jobs import evening_digest_job
    ctx = MagicMock()
    ctx.bot.send_message = AsyncMock()
    ctx.application.bot_data = {"client": make_client()}
    await evening_digest_job(ctx)
    ctx.bot.send_message.assert_not_awaited()


async def test_evening_digest_silent_when_nothing_tomorrow():
    from bot.scheduler_jobs import evening_digest_job
    # All visits are in the past
    past = (datetime.date.today() - datetime.timedelta(days=5)).isoformat()
    client = make_client(
        visits=[{"id": "v1", "location": "loc1", "start_date": past, "end_date": past}],
        locations=[{"id": "loc1", "name": "Old Place"}],
        transportations=[],
    )
    ctx = make_job_context(client)
    await evening_digest_job(ctx)
    ctx.bot.send_message.assert_not_awaited()


async def test_evening_digest_sends_tomorrows_visits():
    from bot.scheduler_jobs import evening_digest_job
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    client = make_client(
        visits=[{"id": "v1", "location": "loc1", "start_date": tomorrow, "end_date": tomorrow}],
        locations=[{"id": "loc1", "name": "Eiffel Tower"}],
        transportations=[],
    )
    ctx = make_job_context(client)
    await evening_digest_job(ctx)
    ctx.bot.send_message.assert_awaited_once()
    text = ctx.bot.send_message.call_args.kwargs["text"]
    assert "Eiffel Tower" in text
    assert "📍" in text


async def test_evening_digest_sends_tomorrows_transport():
    from bot.scheduler_jobs import evening_digest_job
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    client = make_client(
        visits=[],
        locations=[],
        transportations=[{
            "id": "t1", "name": "Flight TLV-CDG", "type": "plane",
            "date": f"{tomorrow}T10:30:00Z",
            "from_location": "TLV", "to_location": "CDG",
        }],
    )
    ctx = make_job_context(client)
    await evening_digest_job(ctx)
    ctx.bot.send_message.assert_awaited_once()
    text = ctx.bot.send_message.call_args.kwargs["text"]
    assert "✈️" in text
    assert "Flight TLV-CDG" in text
