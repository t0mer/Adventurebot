from datetime import date
from bot.keyboards import (
    parse_date,
    fmt_date,
    fmt_date_range,
    main_menu,
    trips_list,
    trip_itinerary,
    location_detail,
    search_prompt,
    date_prompt,
)
from telegram import InlineKeyboardMarkup


def test_parse_date_iso():
    assert parse_date("2026-08-15") == date(2026, 8, 15)


def test_parse_date_ddmmyyyy():
    assert parse_date("15.08.2026") == date(2026, 8, 15)


def test_parse_date_ddmmyy():
    assert parse_date("15/08/26") == date(2026, 8, 15)


def test_parse_date_invalid_returns_none():
    assert parse_date("not-a-date") is None


def test_fmt_date():
    assert fmt_date(date(2026, 8, 5)) == "05 Aug 2026"


def test_fmt_date_range():
    assert fmt_date_range(date(2026, 8, 1), date(2026, 8, 7)) == "01 Aug – 07 Aug 2026"


def test_fmt_date_range_cross_year():
    assert fmt_date_range(date(2025, 12, 28), date(2026, 1, 3)) == "28 Dec 2025 – 03 Jan 2026"


def test_main_menu_returns_markup():
    kb = main_menu()
    assert isinstance(kb, InlineKeyboardMarkup)
    flat = [btn for row in kb.inline_keyboard for btn in row]
    data = {btn.callback_data for btn in flat}
    assert "trips:list" in data
    assert "search:go" in data
    assert "date:go" in data


def test_trips_list_empty():
    kb = trips_list([])
    assert isinstance(kb, InlineKeyboardMarkup)


def test_trips_list_has_back_button():
    kb = trips_list([{"id": "c1", "name": "Poland 2026", "start_date": "2026-07-01", "end_date": "2026-07-14"}])
    flat = [btn for row in kb.inline_keyboard for btn in row]
    data = [btn.callback_data for btn in flat]
    assert "menu:main" in data


def test_trips_list_has_trip_button():
    kb = trips_list([{"id": "c1", "name": "Poland 2026", "start_date": "2026-07-01", "end_date": "2026-07-14"}])
    flat = [btn for row in kb.inline_keyboard for btn in row]
    data = [btn.callback_data for btn in flat]
    assert any(d.startswith("tc:c1") for d in data)


def test_trip_itinerary_has_nav_and_back():
    locations = [
        {"id": "l1", "name": "Hotel A"},
        {"id": "l2", "name": "Hotel B"},
    ]
    visits = [
        {"id": "v1", "location": "l1", "start_date": "2026-07-01", "end_date": "2026-07-03"},
        {"id": "v2", "location": "l2", "start_date": "2026-07-04", "end_date": "2026-07-07"},
    ]
    kb = trip_itinerary("c1", locations, visits, index=0)
    flat = [btn for row in kb.inline_keyboard for btn in row]
    data = [btn.callback_data for btn in flat]
    assert any(d == "tc:c1" for d in data)
    assert any(d.startswith("ld:") for d in data)


def test_trip_itinerary_next_prev():
    locations = [{"id": f"l{i}", "name": f"Hotel {i}"} for i in range(3)]
    visits = [
        {"id": f"v{i}", "location": f"l{i}", "start_date": "2026-07-01", "end_date": "2026-07-03"}
        for i in range(3)
    ]
    kb0 = trip_itinerary("c1", locations, visits, index=0)
    flat0 = [btn.callback_data for row in kb0.inline_keyboard for btn in row]
    assert any("next" in d for d in flat0)
    assert not any("prev" in d for d in flat0)

    kb1 = trip_itinerary("c1", locations, visits, index=1)
    flat1 = [btn.callback_data for row in kb1.inline_keyboard for btn in row]
    assert any("next" in d for d in flat1)
    assert any("prev" in d for d in flat1)

    kb2 = trip_itinerary("c1", locations, visits, index=2)
    flat2 = [btn.callback_data for row in kb2.inline_keyboard for btn in row]
    assert not any("next" in d for d in flat2)
    assert any("prev" in d for d in flat2)


def test_location_detail_returns_markup():
    loc = {"id": "l1", "name": "Hotel A", "description": "Nice place", "rating": 4.5}
    kb = location_detail("l1", trip_id="c1", index=0)
    assert isinstance(kb, InlineKeyboardMarkup)
    flat = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert any(d.startswith("ldoc:l1") for d in flat)


def test_search_prompt_returns_markup():
    kb = search_prompt()
    assert isinstance(kb, InlineKeyboardMarkup)
    flat = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "menu:main" in flat


def test_date_prompt_returns_markup():
    kb = date_prompt()
    assert isinstance(kb, InlineKeyboardMarkup)
    flat = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "menu:main" in flat
