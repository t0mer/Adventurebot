import re
import httpx
from datetime import date


class AdventureLogClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._session_id: str | None = None

    async def _ensure_auth(self) -> None:
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._base}/login",
                data={"username": self._username, "password": self._password},
                headers={
                    "Origin": self._base,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                follow_redirects=False,
            )
        cookie_header = resp.headers.get("set-cookie", "")
        m = re.search(r"sessionid=([^;]+)", cookie_header)
        if m:
            self._session_id = m.group(1)

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        if not self._session_id:
            await self._ensure_auth()
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base}/{path.lstrip('/')}",
                params=params,
                headers={"Cookie": f"sessionid={self._session_id}"},
            )
        if resp.status_code == 401:
            self._session_id = None
            await self._ensure_auth()
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"{self._base}/{path.lstrip('/')}",
                    params=params,
                    headers={"Cookie": f"sessionid={self._session_id}"},
                )
        return resp

    async def get_collections(self) -> list[dict]:
        resp = await self._get("/api/collections")
        return resp.json().get("results", [])

    async def get_locations(self) -> list[dict]:
        resp = await self._get("/api/locations")
        return resp.json().get("results", [])

    async def get_location(self, location_id: str) -> dict:
        resp = await self._get(f"/api/locations/{location_id}")
        return resp.json()

    async def get_visits(self) -> list[dict]:
        resp = await self._get("/api/visits")
        data = resp.json()
        return data if isinstance(data, list) else data.get("results", [])

    async def search(self, query: str) -> dict:
        resp = await self._get("/api/search", params={"query": query})
        return resp.json()

    def find_visit_for_date(
        self, visits: list[dict], locations: list[dict], target: date
    ) -> tuple[dict | None, dict | None]:
        loc_index = {loc["id"]: loc for loc in locations}
        for visit in visits:
            start = date.fromisoformat(visit["start_date"][:10])
            end = date.fromisoformat(visit["end_date"][:10])
            if start <= target <= end:
                loc = loc_index.get(visit["location"])
                if loc:
                    return loc, visit
        return None, None
