"""Config flow Setecna REG."""
from __future__ import annotations
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import SetecnaClient, SetecnaAuthError, SetecnaApiError
from .const import DOMAIN, CONF_SYSTEM_ID


class SetecnaConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = SetecnaClient(session, user_input[CONF_SYSTEM_ID],
                                   user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            try:
                await client.login()
                await client.fetch()
            except SetecnaAuthError:
                errors["base"] = "invalid_auth"
            except SetecnaApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_SYSTEM_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Setecna {user_input[CONF_SYSTEM_ID]}", data=user_input)
        schema = vol.Schema({
            vol.Required(CONF_SYSTEM_ID): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
