"""Config flow for iONA Energy."""

from __future__ import annotations

import logging
import ssl
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class IONAEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iONA Energy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Test the credentials by making a login request
                session = async_get_clientsession(self.hass)
                auth_data = {
                    "method": "login",
                    "username": user_input[CONF_USERNAME],
                    "password": user_input[CONF_PASSWORD],
                }

                _LOGGER.debug("Attempting to authenticate with iONA Energy")

                # Create SSL context that skips certificate verification
                # This is a temporary workaround for SSL certificate issues
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                connector = aiohttp.TCPConnector(ssl=ssl_context)

                async with aiohttp.ClientSession(
                    connector=connector, timeout=aiohttp.ClientTimeout(total=30)
                ) as session:
                    async with session.post(
                        "https://webapp.iona-energy.com/auth",
                        json=auth_data,
                    ) as response:
                        _LOGGER.debug("Response status: %s", response.status)

                        if response.status == 200:
                            auth_response = await response.json()
                            _LOGGER.debug("Authentication successful")

                            # Store the tokens
                            user_input["access_token"] = auth_response.get(
                                "access_token"
                            )
                            user_input["refresh_token"] = auth_response.get(
                                "refresh_token"
                            )
                            user_input["expires_in"] = auth_response.get("expires_in")

                            # Create unique ID based on username
                            await self.async_set_unique_id(user_input[CONF_USERNAME])
                            self._abort_if_unique_id_configured()

                            return self.async_create_entry(
                                title=f"iONA Energy ({user_input[CONF_USERNAME]})",
                                data=user_input,
                            )
                        else:
                            response_text = await response.text()
                            _LOGGER.error(
                                "Authentication failed with status %s: %s",
                                response.status,
                                response_text,
                            )
                            errors["base"] = "invalid_auth"

            except aiohttp.ClientConnectorError as ex:
                _LOGGER.error("Connection error: %s", ex)
                errors["base"] = "cannot_connect"
            except aiohttp.ClientTimeout as ex:
                _LOGGER.error("Timeout error: %s", ex)
                errors["base"] = "cannot_connect"
            except aiohttp.ClientError as ex:
                _LOGGER.error("Client error: %s", ex)
                errors["base"] = "cannot_connect"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", ex)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
