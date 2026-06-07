import io

from telegram import InputFile, Update
from telegram.ext import ContextTypes, ConversationHandler

from .keyboards import (
    main_menu, trips_list, trip_itinerary,
    location_detail, search_prompt, date_prompt,
    parse_date, fmt_date, fmt_date_range,
)

SEARCHING = 0
DATING = 1


def _client(ctx: ContextTypes.DEFAULT_TYPE):
    return ctx.bot_data["client"]


# ─── entry point ─────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome! What would you like to do?",
        reply_markup=main_menu(),
    )


# ─── main menu ───────────────────────────────────────────────────────────────

async def handle_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "What would you like to do?",
        reply_markup=main_menu(),
    )


# ─── trips ───────────────────────────────────────────────────────────────────

async def handle_trips_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    collections = await _client(ctx).get_collections()
    await update.callback_query.edit_message_text(
        "Your trips:" if collections else "No trips found.",
        reply_markup=trips_list(collections),
    )


async def handle_trip_itinerary(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    data = update.callback_query.data  # tl:{trip_id}:{index}[:{dir}]
    parts = data.split(":")
    trip_id = parts[1]
    index = int(parts[2])

    ctx.user_data["trip_id"] = trip_id
    ctx.user_data["trip_index"] = index

    locations = await _client(ctx).get_locations()
    loc_index = {loc["id"]: loc for loc in locations}

    trip_locs = [loc for loc in locations if trip_id in loc.get("collections", [])]
    visits = sorted(
        (v for loc in trip_locs for v in loc.get("visits", [])),
        key=lambda v: v.get("start_date", ""),
    )

    if not visits:
        text = "No itinerary found for this trip."
    else:
        visit = visits[index] if 0 <= index < len(visits) else visits[0]
        loc = loc_index.get(visit.get("location", ""), {})
        from datetime import date as _date
        try:
            s = _date.fromisoformat(visit["start_date"][:10])
            e = _date.fromisoformat(visit["end_date"][:10])
            dates = fmt_date_range(s, e)
        except (KeyError, ValueError):
            dates = ""
        text = (
            f"Stop {index + 1}/{len(visits)}: {loc.get('name', 'Unknown')}\n"
            f"{dates}"
        )

    await update.callback_query.edit_message_text(
        text,
        reply_markup=trip_itinerary(trip_id, locations, visits, index),
    )


# ─── location detail ─────────────────────────────────────────────────────────

async def handle_location_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    loc_id = update.callback_query.data.split(":")[1]
    trip_id = ctx.user_data.get("trip_id", "")
    index = ctx.user_data.get("trip_index", 0)

    loc = await _client(ctx).get_location(loc_id)
    name = loc.get("name", "Unknown")
    desc = loc.get("description") or ""
    rating = loc.get("rating")
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    link = loc.get("link") or ""

    lines = [f"*{name}*"]
    if rating is not None:
        lines.append(f"Rating: {rating}/5")
    if desc:
        lines.append(desc[:300])
    if lat and lon:
        lat, lon = float(lat), float(lon)
        lines.append(f"📍 [{lat:.4f}, {lon:.4f}](https://maps.google.com/?q={lat},{lon})")
    if link:
        lines.append(f"[More info]({link})")

    await update.callback_query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=location_detail(loc_id, trip_id, index),
    )


async def handle_location_docs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    loc_id = update.callback_query.data.split(":")[1]
    loc = await _client(ctx).get_location(loc_id)
    attachments = loc.get("attachments") or []

    if not attachments:
        await update.callback_query.answer("No documents available.", show_alert=True)
        return

    chat_id = update.effective_chat.id
    for att in attachments:
        url = att.get("file") or att.get("url") or ""
        name = att.get("name") or "document"
        if not url:
            continue
        data = await _client(ctx).download_url(url)
        filename = url.split("/")[-1] or name
        await ctx.bot.send_document(
            chat_id=chat_id,
            document=InputFile(io.BytesIO(data), filename=filename),
            caption=name,
        )


# ─── search conversation ──────────────────────────────────────────────────────

async def handle_search_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Type a keyword to search for locations or trips:",
        reply_markup=search_prompt(),
    )
    return SEARCHING


async def handle_search_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    query = (update.message.text or "").strip()
    results = await _client(ctx).search(query)
    locs = results.get("locations") or []
    cols = results.get("collections") or []

    if not locs and not cols:
        await update.message.reply_text(
            f'No results for "{query}".',
            reply_markup=main_menu(),
        )
        return ConversationHandler.END

    lines = [f'Results for "{query}":']
    if locs:
        lines.append("\n*Locations:*")
        for loc in locs[:10]:
            lines.append(f"• {loc.get('name', '')}")
    if cols:
        lines.append("\n*Trips:*")
        for col in cols[:5]:
            lines.append(f"• {col.get('name', '')}")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END


# ─── date conversation ────────────────────────────────────────────────────────

async def handle_date_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Enter a date (DD.MM.YYYY) to see where you were:",
        reply_markup=date_prompt(),
    )
    return DATING


async def handle_date_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    target = parse_date(text)

    if target is None:
        await update.message.reply_text(
            "Couldn't parse that date. Try DD.MM.YYYY (e.g. 15.08.2026):",
            reply_markup=date_prompt(),
        )
        return DATING

    visits = await _client(ctx).get_visits()
    locations = await _client(ctx).get_locations()
    loc, visit = _client(ctx).find_visit_for_date(visits, locations, target)

    if loc is None:
        await update.message.reply_text(
            f"No visit found for {fmt_date(target)}.",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END

    from datetime import date as _date
    try:
        s = _date.fromisoformat(visit["start_date"][:10])
        e = _date.fromisoformat(visit["end_date"][:10])
        dates = fmt_date_range(s, e)
    except (KeyError, ValueError):
        dates = ""

    await update.message.reply_text(
        f"On {fmt_date(target)} you were at *{loc.get('name', 'Unknown')}*\n{dates}",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END
