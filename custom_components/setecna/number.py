"""Number Setecna (setpoint scrivibili)."""
from __future__ import annotations
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import DOMAIN, CONF_SYSTEM_ID
from .entity import SetecnaEntity
from .params import build_param_map, display_value, command_value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    sid = entry.data[CONF_SYSTEM_ID]
    pmap = build_param_map(coord.data or {})
    add(SetecnaNumber(coord, sid, p) for p in pmap.values() if p.entity_type == "number")


class SetecnaNumber(SetecnaEntity, NumberEntity):
    def __init__(self, coordinator, system_id, param) -> None:
        super().__init__(coordinator, system_id, param)
        self._attr_device_class = param.device_class
        self._attr_native_unit_of_measurement = param.unit
        self._attr_native_min_value = param.min
        self._attr_native_max_value = param.max
        self._attr_native_step = param.step
        self._attr_mode = "box"

    @property
    def native_value(self):
        raw = self._raw
        return None if raw is None else display_value(self._param, raw)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_push(self._param.key, command_value(self._param, value))
