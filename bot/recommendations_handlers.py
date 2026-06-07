import logging

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .keyboards import reco_category_keyboard, reco_radius_keyboard

logger = logging.getLogger(__name__)


def _esc(text: str) -> str:
    for ch in ('\\', '_', '*', '`', '['):
        text = text.replace(ch, f'\\{ch}')
    return text

RECO_AWAITING_LOCATION = 12
RECO_CATEGORY = 13
RECO_RADIUS = 14

_CATEGORY_LABELS = {"food": "🍔 Food", "lodging": "🛌 Lodging", "tourism": "🏛 Tourism"}


def _client(ctx: ContextTypes.DEFAULT_TYPE):
    return ctx.bot_data["client"]


# ─── Entry A: from location detail ───────────────────────────────────────────

async def handle_reco_from_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    loc_id = update.callback_query.data.split(":", 2)[2]
    try:
        location = await _client(ctx).get_location(loc_id)
    except httpx.HTTPError as exc:
        logger.error("get_location failed: %s", exc)
        await update.callback_query.edit_message_text(
            "Could not fetch location details. Please try again."
        )
        return ConversationHandler.END

    try:
        lat = float(location["latitude"])
        lon = float(location["longitude"])
    except (TypeError, ValueError, KeyError):
        await update.callback_query.edit_message_text(
            "This location has no coordinates — recommendations unavailable."
        )
        return ConversationHandler.END

    ctx.user_data["reco_lat"] = lat
    ctx.user_data["reco_lon"] = lon
    ctx.user_data["reco_origin_type"] = "location"
    ctx.user_data["reco_origin_id"] = loc_id

    name = location.get("name", "this location")
    await update.callback_query.edit_message_text(
        f"📍 Recommendations near *{name}*\n\nChoose a category:",
        parse_mode="Markdown",
        reply_markup=reco_category_keyboard(),
    )
    return RECO_CATEGORY


# ─── Entry B: from trip overview ─────────────────────────────────────────────

async def handle_reco_from_trip(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    trip_id = update.callback_query.data.split(":", 2)[2]
    ctx.user_data["reco_origin_type"] = "trip"
    ctx.user_data["reco_origin_id"] = trip_id

    await update.callback_query.edit_message_text(
        "📍 Please share your current location using the 📎 attachment button.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Cancel", callback_data="reco:cancel")]
        ]),
    )
    return RECO_AWAITING_LOCATION


async def handle_reco_trip_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    ctx.user_data["reco_lat"] = update.message.location.latitude
    ctx.user_data["reco_lon"] = update.message.location.longitude

    await update.message.reply_text(
        "Got it! Now choose a category:",
        reply_markup=reco_category_keyboard(),
    )
    return RECO_CATEGORY


async def handle_reco_location_wrong_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Please use the 📎 attachment button to share your location."
    )
    return RECO_AWAITING_LOCATION


# ─── Shared: category ────────────────────────────────────────────────────────

async def handle_reco_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    category = update.callback_query.data.split(":", 2)[2]
    ctx.user_data["reco_category"] = category

    await update.callback_query.edit_message_text(
        f"Category: {_CATEGORY_LABELS.get(category, category)}\n\nChoose a search radius:",
        reply_markup=reco_radius_keyboard(),
    )
    return RECO_RADIUS


# ─── Shared: radius + fetch ───────────────────────────────────────────────────

async def handle_reco_radius(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    km = int(update.callback_query.data.split(":", 2)[2])
    radius_m = km * 1000

    lat = ctx.user_data.get("reco_lat")
    lon = ctx.user_data.get("reco_lon")
    category = ctx.user_data.get("reco_category")
    origin_type = ctx.user_data.get("reco_origin_type", "location")
    origin_id = ctx.user_data.get("reco_origin_id", "")

    if lat is None or lon is None or category is None:
        await update.callback_query.edit_message_text(
            "Session expired. Please start over."
        )
        return ConversationHandler.END

    back_callback = f"ld:{origin_id}" if origin_type == "location" else f"tc:{origin_id}"
    back_label = "« Back"
    back_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(back_label, callback_data=back_callback)]
    ])

    try:
        results = await _client(ctx).get_recommendations(
            lat=lat, lon=lon, radius_m=radius_m, category=category
        )
    except httpx.HTTPError as exc:
        logger.error("get_recommendations failed: %s", exc)
        await update.callback_query.edit_message_text(
            "Could not fetch recommendations. Please try again.",
            reply_markup=back_markup,
        )
        return ConversationHandler.END

    cat_label = _CATEGORY_LABELS.get(category, category)

    if not results:
        await update.callback_query.edit_message_text(
            f"No recommendations found for {cat_label} within {km} km.\n"
            "Try a larger radius or a different category.",
            reply_markup=back_markup,
        )
        return ConversationHandler.END

    lines = [f"{cat_label} · {km} km radius · {len(results)} result{'s' if len(results) != 1 else ''}\n"]
    for i, r in enumerate(results, 1):
        name = r.get("name", "Unknown")
        rating = r.get("rating")
        reviews = r.get("review_count") or 0
        dist = r.get("distance_km")
        url = r.get("google_maps_url", "")

        rating_str = f"⭐ {rating}" if rating is not None else ""
        reviews_str = f"({reviews:,})" if reviews else ""
        dist_str = f"· {dist:.2f} km" if dist is not None else ""

        parts = " ".join(filter(None, [rating_str, reviews_str, dist_str]))
        link = f"[{_esc(name)}]({url})" if url else _esc(name)
        lines.append(f"{i}. {link}" + (f" — {parts}" if parts else ""))

    await update.callback_query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=back_markup,
        disable_web_page_preview=True,
    )
    return ConversationHandler.END


# ─── Cancel ───────────────────────────────────────────────────────────────────

async def handle_reco_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Cancelled.")
    return ConversationHandler.END


# ─── ConversationHandler factory ─────────────────────────────────────────────

def build_reco_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_reco_from_location, pattern=r"^reco:loc:"),
            CallbackQueryHandler(handle_reco_from_trip, pattern=r"^reco:trip:"),
        ],
        states={
            RECO_AWAITING_LOCATION: [
                MessageHandler(filters.LOCATION, handle_reco_trip_location),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reco_location_wrong_type),
            ],
            RECO_CATEGORY: [
                CallbackQueryHandler(handle_reco_category, pattern=r"^reco:cat:"),
            ],
            RECO_RADIUS: [
                CallbackQueryHandler(handle_reco_radius, pattern=r"^reco:rad:"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_reco_cancel, pattern=r"^reco:cancel$"),
        ],
    )
