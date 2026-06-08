"""Binary sensor Setecna."""
from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, CONF_SYSTEM_ID
from .entity import SetecnaEntity
from .params import build_param_map, display_value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    sid = entry.data[CONF_SYSTEM_ID]
    pmap = build_param_map(coord.data or {})
    add(SetecnaBinarySensor(coord, sid, p) for p in pmap.values() if p.entity_type == "binary_sensor")


class SetecnaBinarySensor(SetecnaEntity, BinarySensorEntity):
    @property
    def is_on(self):
        raw = self._raw
        return None if raw is None else display_value(self._param, raw)
