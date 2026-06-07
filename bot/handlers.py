import asyncio
import io
import os

from telegram import InputFile, Update
from telegram.ext import ContextTypes, ConversationHandler

from .keyboards import (
    main_menu, trips_list, trip_category, trip_itinerary,
    calendar_list, transportation_item, location_detail,
    checklist_list, checklist_detail,
    search_prompt, date_prompt,
    parse_date, fmt_date, fmt_date_range, fmt_datetime, fmt_transport,
)

SEARCHING = 0
DATING = 1
ADDING_CL_ITEM = 2


def _client(ctx: ContextTypes.DEFAULT_TYPE):
    return ctx.bot_data["client"]


# ─── entry point ─────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    owner_id = os.environ.get("OWNER_CHAT_ID", "").strip()
    if owner_id and str(update.effective_chat.id) != owner_id:
        await update.message.reply_text("Sorry, this bot is private.")
        return
    ctx.bot_data["chat_id"] = update.effective_chat.id
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


async def handle_trip_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    trip_id = update.callback_query.data.split(":")[1]
    ctx.user_data["trip_id"] = trip_id

    locations, transports, checklists = await asyncio.gather(
        _client(ctx).get_locations(),
        _client(ctx).get_transportations(),
        _client(ctx).get_checklists(),
    )
    has_locations = any(trip_id in loc.get("collections", []) for loc in locations)
    has_transport = any(t.get("collection") == trip_id for t in transports)
    has_checklists = any(cl.get("collection") == trip_id for cl in checklists)

    if not has_locations and not has_transport and not has_checklists:
        await update.callback_query.edit_message_text(
            "This trip has no locations, transportation, or checklists yet.",
            reply_markup=trip_category(trip_id, False, False, False),
        )
        return

    await update.callback_query.edit_message_text(
        "What would you like to see?",
        reply_markup=trip_category(trip_id, has_locations, has_transport, has_checklists),
    )


_TRANSPORT_ICONS: dict[str, str] = {
    "plane": "✈️", "car": "🚗", "train": "🚂",
    "bus": "🚌", "boat": "⛴️", "ferry": "⛴️",
    "bike": "🚲", "walk": "🚶",
}


def _build_calendar(locations: list[dict], transports: list[dict], trip_id: str) -> list[dict]:
    from datetime import date as _date
    events = []

    # Visits — sorted first so indices match the tl: handler
    trip_locs = [loc for loc in locations if trip_id in loc.get("collections", [])]
    sorted_visits = sorted(
        ((visit, loc) for loc in trip_locs for visit in loc.get("visits", [])),
        key=lambda x: x[0].get("start_date", ""),
    )
    for idx, (visit, loc) in enumerate(sorted_visits):
        dt = visit.get("start_date", "")
        try:
            s = _date.fromisoformat(dt[:10])
            e = _date.fromisoformat(visit.get("end_date", "")[:10])
            date_str = fmt_date_range(s, e)
        except (ValueError, TypeError):
            date_str = dt[:10]
        events.append({
            "dt": dt,
            "label": f"📍 {loc.get('name', 'Unknown')} · {date_str}",
            "callback": f"tl:{trip_id}:{idx}",
        })

    # Transportation — sorted so indices match the tt: handler
    trip_transports = sorted(
        [t for t in transports if t.get("collection") == trip_id],
        key=lambda t: t.get("date", ""),
    )
    for idx, t in enumerate(trip_transports):
        dt = t.get("date", "")
        icon = _TRANSPORT_ICONS.get(t.get("type", ""), "🚌")
        frm = t.get("from_location") or ""
        to = t.get("to_location") or ""
        route = f"{frm} → {to}" if frm and to else frm or to
        dt_short = fmt_datetime(dt)
        label = f"{icon} {route} · {dt_short}" if route else f"{icon} {t.get('name', 'Transport')} · {dt_short}"
        events.append({
            "dt": dt,
            "label": label,
            "callback": f"tt:{trip_id}:{idx}",
        })

    return sorted(events, key=lambda e: e["dt"])


async def handle_calendar(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    trip_id = update.callback_query.data.split(":")[1]

    locations, transports = await asyncio.gather(
        _client(ctx).get_locations(),
        _client(ctx).get_transportations(),
    )
    events = _build_calendar(locations, transports, trip_id)

    if not events:
        await update.callback_query.edit_message_text(
            "No events found for this trip.",
            reply_markup=calendar_list(trip_id, []),
        )
        return

    await update.callback_query.edit_message_text(
        f"📅 {len(events)} event{'s' if len(events) != 1 else ''}, sorted by date:",
        reply_markup=calendar_list(trip_id, events),
    )


async def handle_transportation_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    parts = update.callback_query.data.split(":")
    trip_id = parts[1]
    index = int(parts[2])

    transports = await _client(ctx).get_transportations()
    items = sorted(
        [t for t in transports if t.get("collection") == trip_id],
        key=lambda t: t.get("date", ""),
    )

    if not items:
        await update.callback_query.edit_message_text(
            "No transportation found for this trip.",
            reply_markup=transportation_item(trip_id, 0, 0),
        )
        return

    index = max(0, min(index, len(items) - 1))
    text = fmt_transport(items[index], index, len(items))
    await update.callback_query.edit_message_text(
        text,
        reply_markup=transportation_item(trip_id, index, len(items)),
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
    raw_lat = loc.get("latitude")
    raw_lon = loc.get("longitude")
    link = loc.get("link") or ""

    lines = [f"*{name}*"]
    if rating is not None:
        lines.append(f"Rating: {rating}/5")
    if desc:
        lines.append(desc[:300])
    if raw_lat and raw_lon:
        lat_f = float(raw_lat)
        lon_f = float(raw_lon)
        lines.append(f"📍 [{lat_f:.4f}, {lon_f:.4f}](https://maps.google.com/?q={lat_f},{lon_f})")
    if link:
        lines.append(f"[More info]({link})")

    map_lat = float(raw_lat) if (raw_lat is not None and raw_lon is not None) else None
    map_lon = float(raw_lon) if (raw_lat is not None and raw_lon is not None) else None

    await update.callback_query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=location_detail(loc_id, trip_id, index, lat=map_lat, lon=map_lon),
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


# ─── checklists ───────────────────────────────────────────────────────────────

async def handle_checklist_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    trip_id = update.callback_query.data.split(":")[1]
    ctx.user_data["trip_id"] = trip_id

    all_cls = await _client(ctx).get_checklists()
    cls = [cl for cl in all_cls if cl.get("collection") == trip_id]

    if not cls:
        await update.callback_query.edit_message_text(
            "No checklists found for this trip.",
            reply_markup=checklist_list(trip_id, []),
        )
        return

    await update.callback_query.edit_message_text(
        f"📋 {len(cls)} checklist{'s' if len(cls) != 1 else ''}:",
        reply_markup=checklist_list(trip_id, cls),
    )


async def handle_checklist_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    cl_id = update.callback_query.data.split(":")[1]
    trip_id = ctx.user_data.get("trip_id", "")
    ctx.user_data["current_cl_id"] = cl_id

    cl = await _client(ctx).get_checklist(cl_id)
    items = cl.get("items", [])
    name = cl.get("name", "Checklist")
    done = sum(1 for it in items if it.get("is_checked"))

    await update.callback_query.edit_message_text(
        f"📋 *{name}* — {done}/{len(items)} done",
        parse_mode="Markdown",
        reply_markup=checklist_detail(cl_id, trip_id, items),
    )


async def handle_checklist_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    parts = update.callback_query.data.split(":")
    cl_id = parts[1]
    idx = int(parts[2])
    trip_id = ctx.user_data.get("trip_id", "")
    cl = await _client(ctx).get_checklist(cl_id)
    items = cl.get("items", [])

    if 0 <= idx < len(items):
        new_items = []
        for i, it in enumerate(items):
            entry = {"name": it["name"], "is_checked": it["is_checked"]}
            if "id" in it:
                entry["id"] = it["id"]
            if i == idx:
                entry["is_checked"] = not it["is_checked"]
            new_items.append(entry)
        cl = await _client(ctx).patch_checklist_items(cl_id, new_items)
        items = cl.get("items", [])

    name = cl.get("name", "Checklist")
    done = sum(1 for it in items if it.get("is_checked"))
    await update.callback_query.edit_message_text(
        f"📋 *{name}* — {done}/{len(items)} done",
        parse_mode="Markdown",
        reply_markup=checklist_detail(cl_id, trip_id, items),
    )


async def handle_checklist_remove_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    parts = update.callback_query.data.split(":")
    cl_id = parts[1]
    idx = int(parts[2])
    trip_id = ctx.user_data.get("trip_id", "")

    cl = await _client(ctx).get_checklist(cl_id)
    items = cl.get("items", [])

    new_items = []
    for i, it in enumerate(items):
        if i == idx:
            continue
        entry = {"name": it["name"], "is_checked": it["is_checked"]}
        if "id" in it:
            entry["id"] = it["id"]
        new_items.append(entry)

    cl = await _client(ctx).patch_checklist_items(cl_id, new_items)
    items = cl.get("items", [])
    name = cl.get("name", "Checklist")
    done = sum(1 for it in items if it.get("is_checked"))

    await update.callback_query.edit_message_text(
        f"📋 *{name}* — {done}/{len(items)} done",
        parse_mode="Markdown",
        reply_markup=checklist_detail(cl_id, trip_id, items),
    )


async def handle_checklist_add_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    cl_id = update.callback_query.data.split(":")[1]
    ctx.user_data["current_cl_id"] = cl_id

    await update.callback_query.edit_message_text(
        "Type the name for the new checklist item:",
    )
    return ADDING_CL_ITEM


async def handle_checklist_add_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    cl_id = ctx.user_data.get("current_cl_id", "")
    trip_id = ctx.user_data.get("trip_id", "")

    if not text or not cl_id:
        await update.message.reply_text("Something went wrong. Please try again.")
        return ConversationHandler.END

    cl = await _client(ctx).get_checklist(cl_id)
    items = cl.get("items", [])
    new_items = [
        {"id": it["id"], "name": it["name"], "is_checked": it["is_checked"]}
        if "id" in it else {"name": it["name"], "is_checked": it["is_checked"]}
        for it in items
    ]
    new_items.append({"name": text, "is_checked": False})

    cl = await _client(ctx).patch_checklist_items(cl_id, new_items)
    items = cl.get("items", [])
    name = cl.get("name", "Checklist")
    done = sum(1 for it in items if it.get("is_checked"))

    await update.message.reply_text(
        f"📋 *{name}* — {done}/{len(items)} done",
        parse_mode="Markdown",
        reply_markup=checklist_detail(cl_id, trip_id, items),
    )
    return ConversationHandler.END
