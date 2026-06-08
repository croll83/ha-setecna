"""Client per il portale cloud Setecna REG (s5a.eu) — porting di scraper.go."""
from __future__ import annotations
import asyncio
import logging
import re
from datetime import datetime
import aiohttp

_LOGGER = logging.getLogger(__name__)
BASE_URL = "https://s5a.eu"
_CSRF_RE = re.compile(r'name="csrf-token"\s+content="([^"]+)"')
_CSRF_RE2 = re.compile(r'content="([^"]+)"\s+name="csrf-token"')


class SetecnaAuthError(Exception):
    """Credenziali non valide."""


class SetecnaApiError(Exception):
    """Errore generico API/scraper."""


class SetecnaClient:
    """Login + fetch + push verso s5a.eu (cookie di sessione, re-login automatico)."""

    def __init__(self, session: aiohttp.ClientSession, system_id: str,
                 username: str, password: str) -> None:
        self._session = session
        self._sid = system_id
        self._user = username
        self._password = password
        self._logged_in = False
        self._last_fetch = ""
        self._state: dict[str, str] = {}  # stato accumulato (getres è incrementale)
        self._lock = asyncio.Lock()

    @property
    def _login_url(self) -> str:
        return f"{BASE_URL}/login"

    @property
    def _fetch_url(self) -> str:
        return f"{BASE_URL}/station/{self._sid}/getres?timestamp="

    @property
    def _refresh_url(self) -> str:
        return f"{BASE_URL}/station/{self._sid}/askrefresh?connrq=1"

    def _push_url(self, key: str, value: str) -> str:
        return (f"{BASE_URL}/station/{self._sid}/putmprop?statid={self._sid}"
                f"&userid=guest&pcount=1&p0={key}&nb0={value}")

    async def login(self) -> None:
        async with self._session.get(self._login_url, timeout=aiohttp.ClientTimeout(total=20)) as r:
            html = await r.text()
        m = _CSRF_RE.search(html) or _CSRF_RE2.search(html)
        if not m:
            raise SetecnaApiError("CSRF token non trovato nella pagina di login")
        token = m.group(1)
        data = {"_token": token, "email": self._user, "password": self._password}
        async with self._session.post(self._login_url, data=data,
                                       timeout=aiohttp.ClientTimeout(total=20)) as r:
            final = str(r.url)
        # s5a redirige a /home se ok, resta su /login se credenziali errate
        if final.rstrip("/").endswith("/login"):
            raise SetecnaAuthError("Login Setecna fallito (credenziali errate?)")
        self._logged_in = True
        _LOGGER.debug("Setecna login ok (-> %s)", final)

    async def async_refresh_station(self) -> None:
        try:
            async with self._session.get(self._refresh_url,
                                         timeout=aiohttp.ClientTimeout(total=20)) as r:
                await r.read()
        except aiohttp.ClientError:
            pass  # best-effort

    async def fetch(self) -> dict[str, str]:
        """Ritorna {param_id: value}. Re-login automatico se la sessione è scaduta."""
        async with self._lock:
            if not self._logged_in:
                await self.login()
            delta = await self._fetch_once()
            # sessione scaduta -> s5a torna HTML/login invece di JSON
            if delta is None:
                _LOGGER.info("Sessione Setecna scaduta, re-login")
                self._logged_in = False
                self._last_fetch = ""
                self._state = {}  # ri-seed completo dopo re-login (timestamp azzerato)
                await self.login()
                delta = await self._fetch_once()
                if delta is None:
                    raise SetecnaApiError("Fetch fallito anche dopo re-login")
            # getres è incrementale: fondo il delta nello stato accumulato
            self._state.update(delta)
            return dict(self._state)

    async def _fetch_once(self) -> dict[str, str] | None:
        url = self._fetch_url + (self._last_fetch or "")
        async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
            ct = r.headers.get("content-type", "")
            body = await r.text()
        if "json" not in ct and not body.lstrip().startswith("{"):
            return None  # probabilmente la pagina di login (sessione scaduta)
        import json
        try:
            j = json.loads(body)
        except ValueError:
            return None
        out: dict[str, str] = {}
        for item in j.get("Data", []):
            out[item.get("Id")] = str(item.get("V"))
        latest = j.get("Latest")
        if latest:
            out["LAST_UPDATE"] = self._parse_ts(latest)
        if j.get("Timestamp"):
            self._last_fetch = j["Timestamp"]
        return out

    @staticmethod
    def _parse_ts(v: str) -> str:
        """Parsing robusto del timestamp s5a (frazioni a lunghezza variabile + offset 2 cifre)."""
        m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\.(\d+))?([+-]\d{2})$", v.strip())
        if not m:
            return v
        base, frac, off = m.groups()
        iso = base.replace(" ", "T")
        if frac:
            iso += "." + frac[:6]
        iso += f"{off}:00"
        try:
            return datetime.fromisoformat(iso).isoformat()
        except ValueError:
            return v

    async def push(self, key: str, value: str) -> None:
        async with self._lock:
            if not self._logged_in:
                await self.login()
            async with self._session.get(self._push_url(key, value),
                                         timeout=aiohttp.ClientTimeout(total=20)) as r:
                await r.read()
