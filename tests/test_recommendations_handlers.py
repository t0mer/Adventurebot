"""Unit tests for recommendations handlers."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Chat, Message, CallbackQuery, Location
from telegram.ext import ContextTypes, ConversationHandler

import bot.recommendations_handlers as rh


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


def make_location_update(latitude: float, longitude: float) -> Update:
    chat = MagicMock(spec=Chat)
    chat.id = 100
    loc = MagicMock(spec=Location)
    loc.latitude = latitude
    loc.longitude = longitude
    msg = MagicMock(spec=Message)
    msg.chat = chat
    msg.location = loc
    msg.text = None
    msg.reply_text = AsyncMock()
    upd = MagicMock(spec=Update)
    upd.effective_chat = chat
    upd.callback_query = None
    upd.message = msg
    return upd


def make_text_update(text: str) -> Update:
    chat = MagicMock(spec=Chat)
    chat.id = 100
    msg = MagicMock(spec=Message)
    msg.chat = chat
    msg.text = text
    msg.location = None
    msg.reply_text = AsyncMock()
    upd = MagicMock(spec=Update)
    upd.effective_chat = chat
    upd.callback_query = None
    upd.message = msg
    return upd


def make_context():
    ctx = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    ctx.user_data = {}
    client = AsyncMock()
    client.get_location.return_value = {
        "id": "loc1", "name": "Amalfi Coast",
        "latitude": "40.634", "longitude": "14.603",
    }
    client.get_recommendations.return_value = []
    ctx.bot_data = {"client": client}
    ctx.bot = AsyncMock()
    return ctx


# ─── Entry A: from location ───────────────────────────────────────────────────

async def test_reco_from_location_stores_coords_shows_category():
    upd = make_callback_update("reco:loc:loc1")
    ctx = make_context()
    result = await rh.handle_reco_from_location(upd, ctx)
    assert result == rh.RECO_CATEGORY
    assert ctx.user_data["reco_lat"] == pytest.approx(40.634)
    assert ctx.user_data["reco_lon"] == pytest.approx(14.603)
    assert ctx.user_data["reco_origin_type"] == "location"
    assert ctx.user_data["reco_origin_id"] == "loc1"
    upd.callback_query.edit_message_text.assert_awaited_once()


async def test_reco_from_location_no_coords_sends_error():
    upd = make_callback_update("reco:loc:loc1")
    ctx = make_context()
    ctx.bot_data["client"].get_location.return_value = {
        "id": "loc1", "name": "No Coords", "latitude": None, "longitude": None,
    }
    result = await rh.handle_reco_from_location(upd, ctx)
    assert result == ConversationHandler.END
    call_text = upd.callback_query.edit_message_text.call_args.args[0]
    assert "no coordinates" in call_text.lower()


# ─── Entry B: from trip ───────────────────────────────────────────────────────

async def test_reco_from_trip_prompts_for_location():
    upd = make_callback_update("reco:trip:trip1")
    ctx = make_context()
    result = await rh.handle_reco_from_trip(upd, ctx)
    assert result == rh.RECO_AWAITING_LOCATION
    assert ctx.user_data["reco_origin_type"] == "trip"
    assert ctx.user_data["reco_origin_id"] == "trip1"
    upd.callback_query.edit_message_text.assert_awaited_once()


async def test_reco_trip_location_message_stores_coords():
    upd = make_location_update(32.0654, 34.7748)
    ctx = make_context()
    result = await rh.handle_reco_trip_location(upd, ctx)
    assert result == rh.RECO_CATEGORY
    assert ctx.user_data["reco_lat"] == pytest.approx(32.0654)
    assert ctx.user_data["reco_lon"] == pytest.approx(34.7748)
    upd.message.reply_text.assert_awaited_once()


async def test_reco_trip_location_text_stays_in_state():
    upd = make_text_update("Tel Aviv")
    ctx = make_context()
    result = await rh.handle_reco_location_wrong_type(upd, ctx)
    assert result == rh.RECO_AWAITING_LOCATION
    upd.message.reply_text.assert_awaited_once()


# ─── Category selection ───────────────────────────────────────────────────────

async def test_reco_category_stores_and_shows_radius():
    upd = make_callback_update("reco:cat:food")
    ctx = make_context()
    result = await rh.handle_reco_category(upd, ctx)
    assert result == rh.RECO_RADIUS
    assert ctx.user_data["reco_category"] == "food"
    upd.callback_query.edit_message_text.assert_awaited_once()


# ─── Radius / results ─────────────────────────────────────────────────────────

async def test_reco_radius_calls_api_and_shows_results():
    upd = make_callback_update("reco:rad:10")
    ctx = make_context()
    ctx.user_data = {
        "reco_lat": 32.0, "reco_lon": 34.8,
        "reco_category": "food",
        "reco_origin_type": "location",
        "reco_origin_id": "loc1",
    }
    ctx.bot_data["client"].get_recommendations.return_value = [
        {"name": "Café Bauhaus", "rating": 4.5, "review_count": 800,
         "distance_km": 0.3, "google_maps_url": "https://g.co/1"},
    ]
    result = await rh.handle_reco_radius(upd, ctx)
    assert result == ConversationHandler.END
    ctx.bot_data["client"].get_recommendations.assert_awaited_once_with(
        lat=32.0, lon=34.8, radius_m=10_000, category="food"
    )
    upd.callback_query.edit_message_text.assert_awaited_once()
    text = upd.callback_query.edit_message_text.call_args.args[0]
    assert "Café Bauhaus" in text
    assert "4.5" in text


async def test_reco_radius_no_results_shows_empty_message():
    upd = make_callback_update("reco:rad:5")
    ctx = make_context()
    ctx.user_data = {
        "reco_lat": 32.0, "reco_lon": 34.8,
        "reco_category": "tourism",
        "reco_origin_type": "trip",
        "reco_origin_id": "trip1",
    }
    ctx.bot_data["client"].get_recommendations.return_value = []
    result = await rh.handle_reco_radius(upd, ctx)
    assert result == ConversationHandler.END
    text = upd.callback_query.edit_message_text.call_args.args[0]
    assert "no recommendations" in text.lower()


async def test_reco_radius_api_error_shows_error_message():
    import httpx
    upd = make_callback_update("reco:rad:20")
    ctx = make_context()
    ctx.user_data = {
        "reco_lat": 32.0, "reco_lon": 34.8,
        "reco_category": "lodging",
        "reco_origin_type": "location",
        "reco_origin_id": "loc1",
    }
    ctx.bot_data["client"].get_recommendations.side_effect = httpx.HTTPError("boom")
    result = await rh.handle_reco_radius(upd, ctx)
    assert result == ConversationHandler.END
    text = upd.callback_query.edit_message_text.call_args.args[0]
    assert "could not fetch" in text.lower()


# ─── Cancel ───────────────────────────────────────────────────────────────────

async def test_reco_cancel_ends_conversation():
    upd = make_callback_update("reco:cancel")
    ctx = make_context()
    result = await rh.handle_reco_cancel(upd, ctx)
    assert result == ConversationHandler.END
    upd.callback_query.edit_message_text.assert_awaited_once()
