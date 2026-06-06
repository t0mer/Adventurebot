from datetime import date
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ─── date helpers ────────────────────────────────────────────────────────────

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_date(text: str) -> Optional[date]:
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d.%m.%y", "%d/%m/%y"):
        try:
            from datetime import datetime
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def fmt_date(d: date) -> str:
    return f"{d.day:02d} {_MONTHS[d.month - 1]} {d.year}"


def fmt_date_range(start: date, end: date) -> str:
    if start.year == end.year:
        return f"{start.day:02d} {_MONTHS[start.month - 1]} – {end.day:02d} {_MONTHS[end.month - 1]} {end.year}"
    return f"{fmt_date(start)} – {fmt_date(end)}"


# ─── keyboard builders ───────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("My Trips", callback_data="trips:list")],
        [InlineKeyboardButton("Search by keyword", callback_data="search:go")],
        [InlineKeyboardButton("Where was I on…", callback_data="date:go")],
    ])


def trips_list(collections: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for col in collections:
        label = col.get("name", "Trip")
        start = col.get("start_date", "")[:10]
        end = col.get("end_date", "")[:10]
        if start and end:
            try:
                s = date.fromisoformat(start)
                e = date.fromisoformat(end)
                label = f"{label}  ({fmt_date_range(s, e)})"
            except ValueError:
                pass
        rows.append([InlineKeyboardButton(label, callback_data=f"tl:{col['id']}:0")])
    rows.append([InlineKeyboardButton("« Back", callback_data="menu:main")])
    return InlineKeyboardMarkup(rows)


def trip_itinerary(
    trip_id: str,
    locations: list[dict],
    visits: list[dict],
    index: int,
) -> InlineKeyboardMarkup:
    loc_index = {loc["id"]: loc for loc in locations}
    rows = []

    if visits and 0 <= index < len(visits):
        visit = visits[index]
        loc = loc_index.get(visit.get("location", ""), {})
        loc_id = loc.get("id", "")
        rows.append([InlineKeyboardButton(
            f"Details: {loc.get('name', 'Location')}",
            callback_data=f"ld:{loc_id}",
        )])

    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton("‹ Prev", callback_data=f"tl:{trip_id}:{index - 1}:prev"))
    if index < len(visits) - 1:
        nav.append(InlineKeyboardButton("Next ›", callback_data=f"tl:{trip_id}:{index + 1}:next"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("« Trips", callback_data="trips:list")])
    return InlineKeyboardMarkup(rows)


def location_detail(loc_id: str, trip_id: str, index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Download docs", callback_data=f"ldoc:{loc_id}")],
        [InlineKeyboardButton("« Itinerary", callback_data=f"tl:{trip_id}:{index}")],
        [InlineKeyboardButton("« Trips", callback_data="trips:list")],
    ])


def search_prompt() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Cancel", callback_data="menu:main")],
    ])


def date_prompt() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Cancel", callback_data="menu:main")],
    ])
