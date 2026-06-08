"""Coordinator: askrefresh + fetch periodico con re-login (no MQTT)."""
from __future__ import annotations
from datetime import timedelta
import logging
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api import SetecnaClient, SetecnaApiError
from .const import DOMAIN, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SetecnaCoordinator(DataUpdateCoordinator):
    """Tiene aggiornati i parametri del sistema Setecna."""

    def __init__(self, hass: HomeAssistant, client: SetecnaClient) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        self.client = client

    async def _async_update_data(self) -> dict[str, str]:
        try:
            await self.client.async_refresh_station()
            return await self.client.fetch()
        except SetecnaApiError as err:
            raise UpdateFailed(str(err)) from err

    async def async_push(self, key: str, raw: str) -> None:
        """Invia un comando, aggiorna ottimisticamente e conferma dopo la propagazione."""
        await self.client.push(key, raw)
        if self.data is not None:
            self.data[key] = raw  # ottimistico: la UI riflette subito
            self.async_set_updated_data(self.data)
        # il controller propaga in ~10s; confermo col valore reale dopo 30s
        async_call_later(self.hass, 30, self._delayed_refresh)

    @callback
    def _delayed_refresh(self, _now) -> None:
        self.hass.async_create_task(self.async_request_refresh())
