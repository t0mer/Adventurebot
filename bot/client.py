import logging
import re
import httpx
from datetime import date

logger = logging.getLogger(__name__)


class AdventureLogAuthError(RuntimeError):
    """Raised when authenticating against AdventureLog fails (bad credentials,
    lockout, etc.). Surfaced loudly so a sign-in problem is not silently shown
    to the user as an empty result."""


def _login_failure_reason(resp: httpx.Response) -> str:
    """Best-effort human-readable reason for a failed /login response."""
    try:
        data = resp.json()
    except ValueError:
        return (resp.text or "no response body").strip()[:200]
    if isinstance(data, dict):
        detail = data.get("data") or data.get("detail") or data.get("error")
        if detail:
            return str(detail)[:200]
    return str(data)[:200]


def _looks_unauthenticated(resp: httpx.Response) -> bool:
    """True when a response indicates the session is missing/expired.

    AdventureLog returns 400 with ``{"error": "User is not authenticated"}``
    (not 401) for an absent/expired session, so match that explicitly."""
    if resp.status_code == 401:
        return True
    if resp.status_code == 400:
        return "not authenticated" in resp.text.lower()
    return False


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
        if not m:
            reason = _login_failure_reason(resp)
            logger.error(
                "AdventureLog login failed for user %r (HTTP %d): %s "
                "— check AL_USERNAME/AL_PASSWORD.",
                self._username, resp.status_code, reason,
            )
            raise AdventureLogAuthError(
                f"AdventureLog login failed (HTTP {resp.status_code}): {reason}"
            )
        self._session_id = m.group(1)
        logger.info("AdventureLog login succeeded for user %r", self._username)

    async def _write(self, method: str, path: str, data: dict) -> httpx.Response:
        if not self._session_id:
            await self._ensure_auth()
        url = f"{self._base}/{path.lstrip('/')}"
        headers = {"Content-Type": "application/json"}
        async with httpx.AsyncClient(cookies={"sessionid": self._session_id}) as http:
            resp = await getattr(http, method)(url, json=data, headers=headers, follow_redirects=True)
        logger.info("_write %s %s -> %d", method.upper(), url, resp.status_code)
        if _looks_unauthenticated(resp):
            self._session_id = None
            await self._ensure_auth()
            async with httpx.AsyncClient(cookies={"sessionid": self._session_id}) as http:
                resp = await getattr(http, method)(url, json=data, headers=headers, follow_redirects=True)
            logger.info("_write retry %s %s -> %d", method.upper(), url, resp.status_code)
        return resp

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        if not self._session_id:
            await self._ensure_auth()
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base}/{path.lstrip('/')}",
                params=params,
                headers={"Cookie": f"sessionid={self._session_id}"},
            )
        if _looks_unauthenticated(resp):
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
        if not self._session_id:
            await self._ensure_auth()
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                url,
                headers={"Cookie": f"sessionid={self._session_id}"},
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
