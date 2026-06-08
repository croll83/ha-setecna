"""Base entity Setecna."""
from __future__ import annotations
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
from .coordinator import SetecnaCoordinator
from .params import ParamDef


class SetecnaEntity(CoordinatorEntity[SetecnaCoordinator]):
    """Base: lega un ParamDef al coordinator + device del sistema."""

    def __init__(self, coordinator: SetecnaCoordinator, system_id: str, param: ParamDef) -> None:
        super().__init__(coordinator)
        self._param = param
        self._sid = system_id
        self._attr_unique_id = f"{system_id}_{param.key}"
        self._attr_name = param.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_id)},
            manufacturer="Setecna",
            model="REG system",
            name=f"Setecna {system_id}",
        )

    @property
    def _raw(self) -> str | None:
        return (self.coordinator.data or {}).get(self._param.key)

    @property
    def available(self) -> bool:
        return super().available and self._raw is not None
