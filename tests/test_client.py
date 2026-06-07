import pytest
import httpx
from datetime import date
from bot.client import AdventureLogClient

BASE = "https://al.test"


def make_client():
    return AdventureLogClient(base_url=BASE, username="admin", password="secret")


async def test_login_sets_session_cookie(respx_mock):
    respx_mock.post(f"{BASE}/login").mock(
        return_value=httpx.Response(
            200,
            headers={"Set-Cookie": "sessionid=abc123; Path=/; HttpOnly"},
        )
    )
    client = make_client()
    await client._ensure_auth()
    assert client._session_id == "abc123"


async def test_get_collections_returns_list(respx_mock):
    respx_mock.post(f"{BASE}/login").mock(
        return_value=httpx.Response(200, headers={"Set-Cookie": "sessionid=tok; Path=/"})
    )
    respx_mock.get(f"{BASE}/api/collections").mock(
        return_value=httpx.Response(
            200,
            json={"count": 1, "results": [{"id": "abc", "name": "Poland 2026"}]},
        )
    )
    client = make_client()
    result = await client.get_collections()
    assert len(result) == 1
    assert result[0]["name"] == "Poland 2026"


async def test_get_locations_returns_list(respx_mock):
    respx_mock.post(f"{BASE}/login").mock(
        return_value=httpx.Response(200, headers={"Set-Cookie": "sessionid=tok; Path=/"})
    )
    respx_mock.get(f"{BASE}/api/locations").mock(
        return_value=httpx.Response(
            200,
            json={"count": 2, "results": [{"id": "loc1", "name": "Hotel A"}, {"id": "loc2", "name": "Hotel B"}]},
        )
    )
    client = make_client()
    result = await client.get_locations()
    assert len(result) == 2


async def test_get_location_returns_dict(respx_mock):
    respx_mock.post(f"{BASE}/login").mock(
        return_value=httpx.Response(200, headers={"Set-Cookie": "sessionid=tok; Path=/"})
    )
    respx_mock.get(f"{BASE}/api/locations/loc1").mock(
        return_value=httpx.Response(200, json={"id": "loc1", "name": "Hotel A", "rating": 4.5})
    )
    client = make_client()
    result = await client.get_location("loc1")
    assert result["rating"] == 4.5


async def test_search_returns_structured_dict(respx_mock):
    respx_mock.post(f"{BASE}/login").mock(
        return_value=httpx.Response(200, headers={"Set-Cookie": "sessionid=tok; Path=/"})
    )
    respx_mock.get(f"{BASE}/api/search").mock(
        return_value=httpx.Response(
            200,
            json={"locations": [{"id": "x", "name": "Zakopane Hotel"}], "collections": [], "countries": []},
        )
    )
    client = make_client()
    result = await client.search("zakopane")
    assert result["locations"][0]["name"] == "Zakopane Hotel"


async def test_reauthenticates_on_401(respx_mock):
    login_route = respx_mock.post(f"{BASE}/login").mock(
        return_value=httpx.Response(200, headers={"Set-Cookie": "sessionid=newtoken; Path=/"})
    )
    respx_mock.get(f"{BASE}/api/collections").mock(
        side_effect=[
            httpx.Response(401, json={}),
            httpx.Response(200, json={"count": 0, "results": []}),
        ]
    )
    client = make_client()
    client._session_id = "expired"
    result = await client.get_collections()
    assert login_route.called
    assert result == []


def test_find_visit_for_date_matches():
    client = make_client()
    visits = [{"id": "v1", "start_date": "2026-08-06T00:00:00Z", "end_date": "2026-08-08T00:00:00Z", "location": "loc1"}]
    locations = [{"id": "loc1", "name": "Hotel A"}]
    loc, visit = client.find_visit_for_date(visits, locations, date(2026, 8, 7))
    assert loc["name"] == "Hotel A"
    assert visit["id"] == "v1"


def test_find_visit_for_date_no_match():
    client = make_client()
    visits = [{"id": "v1", "start_date": "2026-08-06T00:00:00Z", "end_date": "2026-08-08T00:00:00Z", "location": "loc1"}]
    locations = [{"id": "loc1", "name": "Hotel A"}]
    loc, visit = client.find_visit_for_date(visits, locations, date(2026, 8, 20))
    assert loc is None
    assert visit is None


async def test_get_recommendations_returns_first_10(respx_mock):
    respx_mock.post(f"{BASE}/login").mock(
        return_value=httpx.Response(200, headers={"Set-Cookie": "sessionid=tok; Path=/"})
    )
    results = [{"name": f"Place {i}", "rating": 4.0, "review_count": 100, "distance_km": i * 0.1, "google_maps_url": "https://g.co/map"} for i in range(15)]
    respx_mock.get(f"{BASE}/api/recommendations/query/").mock(
        return_value=httpx.Response(200, json={"count": 15, "results": results})
    )
    client = make_client()
    out = await client.get_recommendations(lat=32.0, lon=34.8, radius_m=10000, category="food")
    assert len(out) == 10
    assert out[0]["name"] == "Place 0"


async def test_get_recommendations_passes_correct_params(respx_mock):
    respx_mock.post(f"{BASE}/login").mock(
        return_value=httpx.Response(200, headers={"Set-Cookie": "sessionid=tok; Path=/"})
    )
    route = respx_mock.get(f"{BASE}/api/recommendations/query/").mock(
        return_value=httpx.Response(200, json={"count": 0, "results": []})
    )
    client = make_client()
    await client.get_recommendations(lat=32.1, lon=34.9, radius_m=5000, category="tourism")
    params = dict(route.calls[0].request.url.params)
    assert params["lat"] == "32.1"
    assert params["lon"] == "34.9"
    assert params["radius"] == "5000"
    assert params["category"] == "tourism"
    assert params["sources"] == "google"
