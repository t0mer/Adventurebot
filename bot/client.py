import logging
import httpx
from datetime import date

logger = logging.getLogger(__name__)


class AdventureLogClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key

    @property
    def _auth_headers(self) -> dict:
        return {"X-Api-Key": self._api_key}

    async def _write(self, method: str, path: str, data: dict) -> httpx.Response:
        url = f"{self._base}/{path.lstrip('/')}"
        headers = {**self._auth_headers, "Content-Type": "application/json"}
        async with httpx.AsyncClient() as http:
            resp = await getattr(http, method)(url, json=data, headers=headers, follow_redirects=True)
        logger.info("_write %s %s -> %d", method.upper(), url, resp.status_code)
        return resp

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base}/{path.lstrip('/')}",
                params=params,
                headers=self._auth_headers,
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

    async def get_transportations(self) -> list[dict]:
        resp = await self._get("/api/transportations")
        data = resp.json()
        return data if isinstance(data, list) else data.get("results", [])

    async def get_checklists(self) -> list[dict]:
        resp = await self._get("/api/checklists")
        data = resp.json()
        return data if isinstance(data, list) else data.get("results", [])

    async def get_checklist(self, cl_id: str) -> dict:
        resp = await self._get(f"/api/checklists/{cl_id}")
        return resp.json()

    async def patch_checklist_items(self, cl_id: str, items: list[dict]) -> dict:
        resp = await self._write("patch", f"/api/checklists/{cl_id}/", {"items": items})
        return resp.json()

    async def search(self, query: str) -> dict:
        resp = await self._get("/api/search", params={"query": query})
        return resp.json()

    async def get_recommendations(
        self, lat: float, lon: float, radius_m: int, category: str
    ) -> list[dict]:
        resp = await self._get(
            "/api/recommendations/query",
            params={
                "lat": lat,
                "lon": lon,
                "radius": radius_m,
                "category": category,
                "sources": "google",
            },
        )
        resp.raise_for_status()
        return resp.json().get("results", [])[:10]

    async def download_url(self, url: str) -> bytes:
        from urllib.parse import urlparse
        base_host = urlparse(self._base).hostname or ""
        url_host = urlparse(url).hostname or ""
        if url_host.lower().rstrip(".") != base_host.lower().rstrip("."):
            raise ValueError(f"Refusing to fetch attachment from untrusted host: {url_host!r}")
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                url,
                headers=self._auth_headers,
                follow_redirects=False,
            )
        return resp.content

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
