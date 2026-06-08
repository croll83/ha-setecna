"""Climate per-zona Setecna (porting di models/climate.go).

Una entità termostato per zona abilitata: temperatura corrente Z{i}_TEMP,
banda comfort/economy stagionale (estate=CS/ES, inverno=EW/CW), preset da
Z{i}_FORCING, umidità Z{i}_RH/SET_RH se presente.
"""
from __future__ import annotations
import logging
from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction, PRESET_NONE)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, CONF_SYSTEM_ID
from .params import build_param_map

_LOGGER = logging.getLogger(__name__)
PRESET_FORCED_OFF = "forced off"
PRESET_FORCED_ECONOMY = "forced economy"
PRESET_FORCED_COMFORT = "forced comfort"
_FORCING_TO_PRESET = {"1": PRESET_FORCED_OFF, "2": PRESET_FORCED_ECONOMY,
                      "3": PRESET_FORCED_COMFORT, "0": PRESET_NONE}
_PRESET_TO_FORCING = {PRESET_FORCED_OFF: "1", PRESET_FORCED_ECONOMY: "2",
                      PRESET_FORCED_COMFORT: "3", PRESET_NONE: "0"}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddEntitiesCallback) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    sid = entry.data[CONF_SYSTEM_ID]
    pmap = build_param_map(coord.data or {})
    zones = sorted({p.zone for p in pmap.values() if p.zone})
    has_rh = {z: f"Z{z}_RH" in pmap for z in zones}
    add(SetecnaZoneClimate(coord, sid, z, has_rh[z]) for z in zones)


def _t10(raw):
    try:
        return round(int(raw) / 10, 1)
    except (TypeError, ValueError):
        return None


class SetecnaZoneClimate(CoordinatorEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 15
    _attr_max_temp = 30
    _attr_min_humidity = 45
    _attr_max_humidity = 75
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
    _attr_preset_modes = [PRESET_NONE, PRESET_FORCED_OFF, PRESET_FORCED_ECONOMY, PRESET_FORCED_COMFORT]
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, system_id: str, zone: int, has_humidity: bool) -> None:
        super().__init__(coordinator)
        self._sid = system_id
        self._z = zone
        self._has_rh = has_humidity
        self._attr_unique_id = f"{system_id}_zone_{zone}"
        desc = (coordinator.data or {}).get(f"_FREEDESC{zone}")
        self._attr_name = desc or f"Zone {zone}"
        feats = ClimateEntityFeature.TARGET_TEMPERATURE_RANGE | ClimateEntityFeature.PRESET_MODE
        if has_humidity:
            feats |= ClimateEntityFeature.TARGET_HUMIDITY
        self._attr_supported_features = feats
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_id)}, manufacturer="Setecna",
            model="REG system", name=f"Setecna {system_id}")

    # --- helpers ---
    @property
    def _d(self) -> dict:
        return self.coordinator.data or {}

    @property
    def _summer(self) -> bool:
        return self._d.get("GLOBAL_SEASON") == "1"

    def _k(self, suffix: str) -> str:
        return f"Z{self._z}_{suffix}"

    @property
    def _low_key(self) -> str:
        return self._k("SET_CS") if self._summer else self._k("SET_EW")

    @property
    def _high_key(self) -> str:
        return self._k("SET_ES") if self._summer else self._k("SET_CW")

    # --- read ---
    @property
    def current_temperature(self):
        return _t10(self._d.get(self._k("TEMP")))

    @property
    def current_humidity(self):
        return _t10(self._d.get(self._k("RH"))) if self._has_rh else None

    @property
    def target_humidity(self):
        return _t10(self._d.get(self._k("SET_RH"))) if self._has_rh else None

    @property
    def target_temperature_low(self):
        return _t10(self._d.get(self._low_key))

    @property
    def target_temperature_high(self):
        return _t10(self._d.get(self._high_key))

    @property
    def hvac_mode(self):
        if self._d.get(self._k("OUTPUT")) != "1":
            return HVACMode.OFF
        return HVACMode.COOL if self._summer else HVACMode.HEAT

    @property
    def hvac_action(self):
        if self._d.get(self._k("OUTPUT")) == "1":
            return HVACAction.COOLING if self._summer else HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self):
        return _FORCING_TO_PRESET.get(self._d.get(self._k("FORCING")), PRESET_NONE)

    # --- write ---
    async def _push(self, key: str, raw: str) -> None:
        await self.coordinator.async_push(key, raw)

    async def async_set_temperature(self, **kwargs) -> None:
        low = kwargs.get("target_temp_low")
        high = kwargs.get("target_temp_high")
        if low is not None:
            await self._push(self._low_key, str(int(round(low * 10))))
        if high is not None:
            await self._push(self._high_key, str(int(round(high * 10))))

    async def async_set_humidity(self, humidity: int) -> None:
        if self._has_rh:
            await self._push(self._k("SET_RH"), str(int(round(humidity * 10))))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._push(self._k("FORCING"), _PRESET_TO_FORCING.get(preset_mode, "0"))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        # Il modo riscaldamento/raffrescamento segue la stagione del sistema
        # (non comandabile per-zona). OFF = preset "forced off".
        if hvac_mode == HVACMode.OFF:
            await self._push(self._k("FORCING"), "1")
        else:
            await self._push(self._k("FORCING"), "0")
