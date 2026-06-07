"""Handler unit tests using PTB's Application test utilities."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, User, Chat, Message, CallbackQuery, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers import (
    start,
    handle_menu,
    handle_trips_list,
    handle_trip_itinerary,
    handle_location_detail,
    handle_location_docs,
    handle_search_go,
    handle_search_text,
    handle_date_go,
    handle_date_text,
    SEARCHING,
    DATING,
)


# ─── helpers ─────────────────────────────────────────────────────────────────

def make_user():
    return User(id=1, first_name="Tomer", is_bot=False, username="tomer")


def make_update_with_message(text: str = "/start") -> Update:
    user = make_user()
    chat = MagicMock(spec=Chat)
    chat.id = 100
    msg = MagicMock(spec=Message)
    msg.from_user = user
    msg.chat = chat
    msg.text = text
    msg.reply_text = AsyncMock()
    upd = MagicMock(spec=Update)
    upd.effective_user = user
    upd.effective_chat = chat
    upd.message = msg
    upd.callback_query = None
    return upd


def make_update_with_callback(data: str) -> Update:
    user = make_user()
    chat = MagicMock(spec=Chat)
    chat.id = 100
    msg = MagicMock(spec=Message)
    msg.from_user = user
    msg.chat = chat
    msg.edit_text = AsyncMock()
    cq = MagicMock(spec=CallbackQuery)
    cq.from_user = user
    cq.data = data
    cq.answer = AsyncMock()
    cq.message = msg
    cq.edit_message_text = AsyncMock()
    upd = MagicMock(spec=Update)
    upd.effective_user = user
    upd.effective_chat = chat
    upd.message = None
    upd.callback_query = cq
    return upd


def make_context(client=None):
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.bot = AsyncMock()
    ctx.user_data = {}
    ctx.bot_data = {"client": client or AsyncMock()}
    return ctx


def make_client(collections=None, locations=None, visits=None, search_result=None):
    cl = AsyncMock()
    cl.get_collections.return_value = collections or []
    cl.get_locations.return_value = locations or []
    cl.get_visits.return_value = visits or []
    cl.get_location.return_value = {}
    cl.search.return_value = search_result or {"locations": [], "collections": [], "countries": []}
    # find_visit_for_date is synchronous
    cl.find_visit_for_date = MagicMock(return_value=(None, None))
    return cl


# ─── tests ───────────────────────────────────────────────────────────────────

async def test_start_sends_main_menu():
    upd = make_update_with_message("/start")
    ctx = make_context()
    result = await start(upd, ctx)
    upd.message.reply_text.assert_awaited_once()
    args, kwargs = upd.message.reply_text.call_args
    assert isinstance(kwargs.get("reply_markup") or args[1] if len(args) > 1 else kwargs.get("reply_markup"), InlineKeyboardMarkup)


async def test_handle_menu_back_to_main():
    upd = make_update_with_callback("menu:main")
    ctx = make_context()
    await handle_menu(upd, ctx)
    upd.callback_query.answer.assert_awaited()
    upd.callback_query.edit_message_text.assert_awaited()


async def test_handle_trips_list_shows_trips():
    collections = [{"id": "c1", "name": "Poland 2026", "start_date": "2026-07-01", "end_date": "2026-07-14"}]
    client = make_client(collections=collections)
    upd = make_update_with_callback("trips:list")
    ctx = make_context(client=client)
    await handle_trips_list(upd, ctx)
    upd.callback_query.edit_message_text.assert_awaited()
    client.get_collections.assert_awaited_once()


async def test_handle_trip_itinerary_shows_card():
    locations = [{"id": "l1", "name": "Hotel A"}]
    visits = [{"id": "v1", "location": "l1", "start_date": "2026-07-01", "end_date": "2026-07-03"}]
    client = make_client(locations=locations, visits=visits)
    upd = make_update_with_callback("tl:c1:0")
    ctx = make_context(client=client)
    await handle_trip_itinerary(upd, ctx)
    upd.callback_query.edit_message_text.assert_awaited()


async def test_handle_location_detail_shows_card():
    location = {"id": "l1", "name": "Hotel A", "description": "Nice", "rating": 4.5,
                "latitude": 50.0, "longitude": 20.0, "link": ""}
    client = make_client()
    client.get_location.return_value = location
    upd = make_update_with_callback("ld:l1")
    ctx = make_context(client=client)
    ctx.user_data["trip_id"] = "c1"
    ctx.user_data["trip_index"] = 0
    await handle_location_detail(upd, ctx)
    upd.callback_query.edit_message_text.assert_awaited()
    client.get_location.assert_awaited_once_with("l1")


async def test_handle_location_docs_no_docs():
    client = make_client()
    client.get_location.return_value = {"id": "l1", "name": "Hotel A", "attachments": []}
    upd = make_update_with_callback("ldoc:l1")
    ctx = make_context(client=client)
    await handle_location_docs(upd, ctx)
    upd.callback_query.answer.assert_awaited()


async def test_handle_search_go_enters_state():
    upd = make_update_with_callback("search:go")
    ctx = make_context()
    result = await handle_search_go(upd, ctx)
    assert result == SEARCHING
    upd.callback_query.edit_message_text.assert_awaited()


async def test_handle_search_text_shows_results():
    result_data = {"locations": [{"id": "l1", "name": "Zakopane Hotel"}], "collections": [], "countries": []}
    client = make_client(search_result=result_data)
    upd = make_update_with_message("zakopane")
    ctx = make_context(client=client)
    result = await handle_search_text(upd, ctx)
    assert result == ConversationHandler.END
    upd.message.reply_text.assert_awaited()
    client.search.assert_awaited_once_with("zakopane")


async def test_handle_date_go_enters_state():
    upd = make_update_with_callback("date:go")
    ctx = make_context()
    result = await handle_date_go(upd, ctx)
    assert result == DATING
    upd.callback_query.edit_message_text.assert_awaited()


async def test_handle_date_text_found():
    locations = [{"id": "l1", "name": "Hotel A"}]
    visits = [{"id": "v1", "location": "l1", "start_date": "2026-08-06", "end_date": "2026-08-08"}]
    client = make_client(locations=locations, visits=visits)
    client.find_visit_for_date = MagicMock(return_value=(locations[0], visits[0]))
    upd = make_update_with_message("07.08.2026")
    ctx = make_context(client=client)
    result = await handle_date_text(upd, ctx)
    assert result == ConversationHandler.END
    upd.message.reply_text.assert_awaited()


async def test_handle_date_text_invalid():
    client = make_client()
    upd = make_update_with_message("not a date")
    ctx = make_context(client=client)
    result = await handle_date_text(upd, ctx)
    assert result == DATING
    upd.message.reply_text.assert_awaited()


async def test_handle_date_text_no_visit():
    client = make_client()
    client.find_visit_for_date.return_value = (None, None)
    upd = make_update_with_message("07.08.2026")
    ctx = make_context(client=client)
    result = await handle_date_text(upd, ctx)
    assert result == ConversationHandler.END
    upd.message.reply_text.assert_awaited()


@pytest.mark.asyncio
async def test_handle_location_detail_passes_coords_to_keyboard(monkeypatch):
    """When the location has lat/lon, the keyboard should contain map URL buttons."""
    from bot import handlers
    from unittest.mock import AsyncMock, MagicMock

    loc = {
        "id": "l1",
        "name": "Amalfi Coast",
        "description": "",
        "rating": 5,
        "latitude": "40.634",
        "longitude": "14.6027",
        "link": "",
        "attachments": [],
    }

    mock_client = MagicMock()
    mock_client.get_location = AsyncMock(return_value=loc)
    monkeypatch.setattr(handlers, "_client", lambda ctx: mock_client)

    update = MagicMock()
    update.callback_query.data = "ld:l1"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()

    ctx = MagicMock()
    ctx.user_data = {"trip_id": "c1", "trip_index": 0}

    await handlers.handle_location_detail(update, ctx)

    call_kwargs = update.callback_query.edit_message_text.call_args.kwargs
    markup = call_kwargs["reply_markup"]
    all_urls = [btn.url for row in markup.inline_keyboard for btn in row if btn.url]

    assert any("maps.apple.com" in u and "q=40.634,14.6027" in u for u in all_urls)
    assert any("maps.google.com" in u and "q=40.634,14.6027" in u for u in all_urls)
    assert any("maps.apple.com" in u and "daddr=40.634,14.6027" in u for u in all_urls)
    assert any("maps.google.com" in u and "daddr=40.634,14.6027" in u for u in all_urls)


@pytest.mark.asyncio
async def test_handle_location_detail_no_coords_has_no_map_buttons(monkeypatch):
    """When the location has no coordinates, the keyboard must not contain map URL buttons."""
    from bot import handlers
    from unittest.mock import AsyncMock, MagicMock

    loc = {
        "id": "l1",
        "name": "Unknown Place",
        "description": "",
        "rating": None,
        "latitude": None,
        "longitude": None,
        "link": "",
        "attachments": [],
    }

    mock_client = MagicMock()
    mock_client.get_location = AsyncMock(return_value=loc)
    monkeypatch.setattr(handlers, "_client", lambda ctx: mock_client)

    update = MagicMock()
    update.callback_query.data = "ld:l1"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()

    ctx = MagicMock()
    ctx.user_data = {"trip_id": "c1", "trip_index": 0}

    await handlers.handle_location_detail(update, ctx)

    call_kwargs = update.callback_query.edit_message_text.call_args.kwargs
    markup = call_kwargs["reply_markup"]
    all_urls = [btn.url for row in markup.inline_keyboard for btn in row]
    assert all(u is None for u in all_urls)
