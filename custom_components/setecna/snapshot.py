"""Servizi setecna.snapshot_save / snapshot_restore (PATCH 2026-09-03).

Salvano/ripristinano in modo PERSISTENTE (Store HA) i parametri Setecna delle zone
(forzatura, 4 setpoint, umidità), la stagione, il preset calendario, la velocità dei
deumidificatori, più lo stato di entità HA extra (select/number/switch, es. MAXA).
Usati dagli script "Fuori casa" / "In casa": al ritorno tutto torna com'era.
"""
from __future__ import annotations
import asyncio
import logging
import time
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
STORE_KEY = f"{DOMAIN}_snapshot"
STORE_VERSION = 1

ZONE_KEYS = ("FORCING", "SET_CS", "SET_ES", "SET_CW", "SET_EW", "SET_RH")
GLOBAL_KEYS = ("GLOBAL_SEASON", "MT1_FORCING", "D1_USER_SPEED_CONTROL", "D2_USER_SPEED_CONTROL", "D3_USER_SPEED_CONTROL")

SAVE_SCHEMA = vol.Schema({
    vol.Optional("name", default="default"): cv.string,
    vol.Optional("extra_entities", default=[]): cv.entity_ids,
})
RESTORE_SCHEMA = vol.Schema({
    vol.Optional("name", default="default"): cv.string,
    vol.Optional("setecna", default=True): cv.boolean,
    vol.Optional("extra", default=True): cv.boolean,
})


def _zone_indexes(data: dict) -> list[int]:
    return [i for i in range(1, 33) if data.get(f"Z{i}_SENSOR_CHN", "0") not in ("0", None, "") and f"Z{i}_FORCING" in data]


async def async_register_snapshot_services(hass: HomeAssistant, coordinator) -> None:
    if hass.services.has_service(DOMAIN, "snapshot_save"):
        return
    store: Store = Store(hass, STORE_VERSION, STORE_KEY)

    async def _load() -> dict:
        return (await store.async_load()) or {}

    async def snapshot_save(call: ServiceCall) -> None:
        data = coordinator.data or {}
        params: dict[str, str] = {}
        for i in _zone_indexes(data):
            for k in ZONE_KEYS:
                v = data.get(f"Z{i}_{k}")
                if v is not None:
                    params[f"Z{i}_{k}"] = v
        for k in GLOBAL_KEYS:
            if data.get(k) is not None:
                params[k] = data[k]
        extra: dict[str, dict] = {}
        for eid in call.data["extra_entities"]:
            st = hass.states.get(eid)
            if st is None or st.state in ("unknown", "unavailable"):
                continue
            extra[eid] = {"state": st.state}
        snaps = await _load()
        snaps[call.data["name"]] = {"ts": time.time(), "params": params, "extra": extra}
        await store.async_save(snaps)
        _LOGGER.info("Setecna snapshot '%s' salvato: %d parametri, %d entità extra", call.data["name"], len(params), len(extra))

    async def snapshot_restore(call: ServiceCall) -> None:
        snaps = await _load()
        snap = snaps.get(call.data["name"])
        if not snap:
            _LOGGER.warning("Setecna snapshot '%s' non trovato", call.data["name"])
            return
        if call.data["setecna"]:
            data = coordinator.data or {}
            n = 0
            for key, val in snap["params"].items():
                if data.get(key) == val:
                    continue
                await coordinator.client.push(key, val)
                n += 1
                await asyncio.sleep(0.3)
            _LOGGER.info("Setecna snapshot '%s': %d parametri ripristinati", call.data["name"], n)
            await coordinator.async_request_refresh()
        if call.data["extra"]:
            for eid, info in snap.get("extra", {}).items():
                domain = eid.split(".")[0]
                val = info["state"]
                try:
                    if domain == "select":
                        await hass.services.async_call("select", "select_option", {"entity_id": eid, "option": val}, blocking=True)
                    elif domain in ("input_select",):
                        await hass.services.async_call("input_select", "select_option", {"entity_id": eid, "option": val}, blocking=True)
                    elif domain in ("number", "input_number"):
                        await hass.services.async_call(domain, "set_value", {"entity_id": eid, "value": float(val)}, blocking=True)
                    elif domain in ("switch", "input_boolean", "light", "fan", "automation"):
                        await hass.services.async_call(domain, "turn_on" if val == "on" else "turn_off", {"entity_id": eid}, blocking=True)
                    elif domain == "climate":
                        await hass.services.async_call("climate", "set_hvac_mode", {"entity_id": eid, "hvac_mode": val}, blocking=True)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Ripristino %s=%s fallito: %s", eid, val, err)

    hass.services.async_register(DOMAIN, "snapshot_save", snapshot_save, schema=SAVE_SCHEMA)
    hass.services.async_register(DOMAIN, "snapshot_restore", snapshot_restore, schema=RESTORE_SCHEMA)
