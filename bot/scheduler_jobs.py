import asyncio
import datetime
import logging
import os

import httpx
from telegram.ext import CallbackContext
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import scheduler_store

logger = logging.getLogger(__name__)

_TRANSPORT_ICONS: dict[str, str] = {
    "plane": "✈️",
    "car": "🚗",
    "train": "🚂",
    "bus": "🚌",
    "boat": "⛴️",
    "ferry": "⛴️",
    "bike": "🚲",
    "walk": "🚶",
}


async def checklist_reminder_job(context: CallbackContext) -> None:
    chat_id = context.application.bot_data.get("chat_id")
    if not chat_id:
        logger.warning("checklist_reminder_job: no chat_id set, skipping")
        return

    client = context.application.bot_data["client"]
    try:
        checklists, collections = await asyncio.gather(
            client.get_checklists(),
            client.get_collections(),
        )
        details = await asyncio.gather(*[client.get_checklist(cl["id"]) for cl in checklists])
    except httpx.HTTPError as exc:
        logger.error("checklist_reminder_job: HTTP error: %s", exc)
        return

    col_name = {c["id"]: c.get("name", "Trip") for c in collections}

    groups: dict[str, list[dict]] = {}
    for cl in details:
        incomplete = [it for it in cl.get("items", []) if not it.get("is_checked")]
        if not incomplete:
            continue
        key = cl.get("collection") or "other"
        groups.setdefault(key, []).append({**cl, "_incomplete": incomplete})

    if not groups:
        return

    lines = ["📋 *Incomplete checklists*"]
    for key, cls in groups.items():
        group_name = col_name.get(key, "🗂 Other") if key != "other" else "🗂 Other"
        lines.append(f"\n🧳 *{group_name}*")
        for cl in cls:
            lines.append(f"  ☐ {cl['name']}")
            for it in cl["_incomplete"]:
                lines.append(f"    • {it['name']}")

    await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        parse_mode="Markdown",
    )


async def evening_digest_job(context: CallbackContext) -> None:
    chat_id = context.application.bot_data.get("chat_id")
    if not chat_id:
        logger.warning("evening_digest_job: no chat_id set, skipping")
        return

    config = scheduler_store.load()
    entry = scheduler_store.get_scheduler(config, "evening_digest")
    tz_name = entry.get("timezone") or os.environ.get("TZ", "UTC")
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")

    tomorrow = (datetime.datetime.now(tz) + datetime.timedelta(days=1)).date()

    client = context.application.bot_data["client"]
    try:
        visits, transports, locations = await asyncio.gather(
            client.get_visits(),
            client.get_transportations(),
            client.get_locations(),
        )
    except httpx.HTTPError as exc:
        logger.error("evening_digest_job: HTTP error: %s", exc)
        return

    loc_name = {loc["id"]: loc.get("name", "Location") for loc in locations}

    events: list[dict] = []

    for v in visits:
        try:
            start = datetime.date.fromisoformat(v.get("start_date", "")[:10])
            end_str = v.get("end_date", "")
            end = datetime.date.fromisoformat(end_str[:10]) if end_str else start
        except ValueError:
            continue
        if start <= tomorrow <= end:
            name = loc_name.get(v.get("location", ""), "Location")
            events.append({"sort_key": v.get("start_date", ""), "text": f"📍 {name}"})

    for t in transports:
        dep = t.get("date", "")
        if not dep:
            continue
        try:
            dep_date = datetime.date.fromisoformat(dep[:10])
        except ValueError:
            continue
        if dep_date != tomorrow:
            continue
        icon = _TRANSPORT_ICONS.get(t.get("type", ""), "🚀")
        name = t.get("name") or t.get("type", "Transport")
        frm = t.get("from_location") or ""
        to = t.get("to_location") or ""
        route = f" {frm} → {to}" if frm and to else ""
        events.append({"sort_key": dep, "text": f"{icon} {name}{route}"})

    if not events:
        return

    events.sort(key=lambda e: e["sort_key"])

    day_name = tomorrow.strftime("%a %-d %b")
    lines = [f"🌙 *Tomorrow — {day_name}*", ""]
    for e in events:
        lines.append(e["text"])

    await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        parse_mode="Markdown",
    )
