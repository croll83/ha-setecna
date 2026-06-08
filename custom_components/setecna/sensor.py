"""Sensori Setecna."""
from __future__ import annotations
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from .const import DOMAIN, CONF_SYSTEM_ID
from .entity import SetecnaEntity
from .params import build_param_map, display_value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    sid = entry.data[CONF_SYSTEM_ID]
    pmap = build_param_map(coord.data or {})
    add(SetecnaSensor(coord, sid, p) for p in pmap.values() if p.entity_type == "sensor")


class SetecnaSensor(SetecnaEntity, SensorEntity):
    def __init__(self, coordinator, system_id, param) -> None:
        super().__init__(coordinator, system_id, param)
        self._attr_device_class = param.device_class
        self._attr_native_unit_of_measurement = param.unit
        self._attr_state_class = param.state_class
        if param.transform == "enum" and param.enum_map:
            self._attr_options = list(dict.fromkeys(param.enum_map.values()))

    @property
    def native_value(self):
        raw = self._raw
        if raw is None:
            return None
        if self._param.transform == "timestamp":
            return dt_util.parse_datetime(raw)
        return display_value(self._param, raw)
