"""API for iONA Energy."""

from __future__ import annotations

import logging
import ssl
import time
from typing import Any

import aiohttp
from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import AUTH_URL, CONF_ACCESS_TOKEN, CONF_REFRESH_TOKEN, CONF_EXPIRES_IN

_LOGGER = logging.getLogger(__name__)


class IONAEnergyAPI:
    """iONA Energy API client."""

    def __init__(self, hass: HomeAssistant, config_data: dict[str, Any]) -> None:
        """Initialize the API client."""
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.access_token = config_data.get(CONF_ACCESS_TOKEN)
        self.refresh_token = config_data.get(CONF_REFRESH_TOKEN)
        self.expires_in = config_data.get(CONF_EXPIRES_IN)
        self.config_entry = None  # Will be set by the integration

        # Track token creation time for expiration checking
        self.token_created_at = time.time()

        # Track last token refresh time for sensor
        self.last_token_refresh = time.time()

        # Create SSL context that skips certificate verification
        # This is a temporary workaround for SSL certificate issues
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    def set_config_entry(self, config_entry: ConfigEntry) -> None:
        """Set the config entry for token updates."""
        self.config_entry = config_entry

    def _is_token_expired(self) -> bool:
        """Check if the current access token is expired or will expire soon."""
        if not self.access_token or not self.expires_in:
            return True

        # Check if token expires in the next 5 minutes
        time_until_expiry = (self.token_created_at + self.expires_in) - time.time()
        return time_until_expiry < 300  # 5 minutes buffer

    async def _update_tokens_in_config_entry(self, new_tokens: dict[str, Any]) -> None:
        """Update tokens in the config entry."""
        if self.config_entry is None:
            _LOGGER.warning("No config entry set, cannot update tokens")
            return

        # Prepare updated data without mutating config_entry.data directly
        updated_data = {
            **self.config_entry.data,
            CONF_ACCESS_TOKEN: new_tokens.get("access_token"),
            CONF_REFRESH_TOKEN: new_tokens.get("refresh_token"),
            CONF_EXPIRES_IN: new_tokens.get("expires_in"),
        }

        # Update the runtime data first
        self.access_token = new_tokens.get("access_token")
        self.refresh_token = new_tokens.get("refresh_token")
        self.expires_in = new_tokens.get("expires_in")
        self.token_created_at = time.time()
        self.last_token_refresh = time.time()

        # Save the updated config entry using the supported API
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=updated_data
        )
        _LOGGER.debug("Updated tokens in config entry")

    async def _ensure_valid_token(self) -> None:
        """Ensure we have a valid access token, refresh if necessary."""
        if not self.access_token:
            raise ValueError("No access token available")

        # Check if token is expired or will expire soon
        if self._is_token_expired():
            _LOGGER.debug("Token expired or expiring soon, refreshing")
            try:
                await self.refresh_access_token()
            except Exception as ex:
                _LOGGER.error("Failed to refresh access token: %s", ex)
                raise

    async def authenticate(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate with iONA Energy."""
        auth_data = {
            "method": "login",
            "username": username,
            "password": password,
        }

        connector = aiohttp.TCPConnector(ssl=self.ssl_context)

        async with aiohttp.ClientSession(
            connector=connector, timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            async with session.post(AUTH_URL, json=auth_data) as response:
                if response.status == 200:
                    tokens = await response.json()
                    # Set token creation time for new tokens
                    self.token_created_at = time.time()
                    self.last_token_refresh = time.time()
                    return tokens
                else:
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"Authentication failed: {response.status}",
                    )

    async def refresh_access_token(self) -> dict[str, Any]:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        refresh_data = {
            "method": "refresh",
            "refresh_token": self.refresh_token,
        }

        _LOGGER.debug("Refreshing access token")

        connector = aiohttp.TCPConnector(ssl=self.ssl_context)

        async with aiohttp.ClientSession(
            connector=connector, timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            async with session.post(AUTH_URL, json=refresh_data) as response:
                if response.status == 200:
                    new_tokens = await response.json()
                    _LOGGER.debug("Token refresh successful")

                    # Update tokens in config entry
                    await self._update_tokens_in_config_entry(new_tokens)

                    return new_tokens
                else:
                    response_text = await response.text()
                    _LOGGER.error(
                        "Token refresh failed with status %s: %s",
                        response.status,
                        response_text,
                    )
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"Token refresh failed: {response.status}",
                    )

    async def get_initialisation_data(self) -> dict[str, Any]:
        """Get initialisation data from iONA Energy."""
        # Ensure we have a valid token before making the request
        await self._ensure_valid_token()

        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Use the correct iONA Energy API endpoint
        connector = aiohttp.TCPConnector(ssl=self.ssl_context)

        async with aiohttp.ClientSession(
            connector=connector, timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            async with session.get(
                "https://api.n2g-iona.net/v2/initialisation",
                headers=headers,
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Token might be expired, try to refresh
                    _LOGGER.debug("Received 401, attempting token refresh")
                    await self._ensure_valid_token()

                    # Retry the request with new token
                    headers = {"Authorization": f"Bearer {self.access_token}"}
                    async with session.get(
                        "https://api.n2g-iona.net/v2/initialisation",
                        headers=headers,
                    ) as retry_response:
                        if retry_response.status == 200:
                            return await retry_response.json()
                        else:
                            raise aiohttp.ClientResponseError(
                                retry_response.request_info,
                                retry_response.history,
                                status=retry_response.status,
                                message=f"Failed to get initialisation data after token refresh: {retry_response.status}",
                            )
                else:
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"Failed to get initialisation data: {response.status}",
                    )

    async def get_current_power(self) -> dict[str, Any]:
        """Get current power consumption from iONA Energy."""
        # Ensure we have a valid token before making the request
        await self._ensure_valid_token()

        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Calculate time range: 5 minutes ago to current time
        from datetime import datetime, timedelta
        import urllib.parse

        now = datetime.utcnow()
        end_time = now
        start_time = now - timedelta(minutes=5)

        # Format timestamps for API
        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        end_str = end_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        # Build URL with time parameters
        url = f"https://api.n2g-iona.net/v2/power/{urllib.parse.quote(start_str)}/{urllib.parse.quote(end_str)}/"

        connector = aiohttp.TCPConnector(ssl=self.ssl_context)

        async with aiohttp.ClientSession(
            connector=connector, timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()

                    # Get the latest power reading (last entry in results)
                    if data.get("status") == "ok" and data.get("data", {}).get(
                        "results"
                    ):
                        results = data["data"]["results"]
                        if results:
                            # Return the latest power reading
                            latest = results[-1]
                            return {
                                "power": latest.get("power", 0),
                                "timestamp": latest.get("timestamp", ""),
                                "unit": "W",
                            }
                        else:
                            raise ValueError("No power data available")
                    else:
                        raise ValueError("Invalid response format")

                elif response.status == 401:
                    # Token might be expired, try to refresh
                    _LOGGER.debug("Received 401, attempting token refresh")
                    await self._ensure_valid_token()

                    # Retry the request with new token
                    headers = {"Authorization": f"Bearer {self.access_token}"}
                    async with session.get(url, headers=headers) as retry_response:
                        if retry_response.status == 200:
                            data = await retry_response.json()

                            # Get the latest power reading (last entry in results)
                            if data.get("status") == "ok" and data.get("data", {}).get(
                                "results"
                            ):
                                results = data["data"]["results"]
                                if results:
                                    # Return the latest power reading
                                    latest = results[-1]
                                    return {
                                        "power": latest.get("power", 0),
                                        "timestamp": latest.get("timestamp", ""),
                                        "unit": "W",
                                    }
                                else:
                                    raise ValueError("No power data available")
                            else:
                                raise ValueError("Invalid response format")
                        else:
                            raise aiohttp.ClientResponseError(
                                retry_response.request_info,
                                retry_response.history,
                                status=retry_response.status,
                                message=f"Failed to get power data after token refresh: {retry_response.status}",
                            )
                else:
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"Failed to get power data: {response.status}",
                    )

    async def get_meter_info(self) -> dict[str, Any]:
        """Get meter info data (includes total consumption in Wh)."""
        # Ensure we have a valid token before making the request
        await self._ensure_valid_token()

        headers = {"Authorization": f"Bearer {self.access_token}"}

        url = "https://api.n2g-iona.net/v2/meter/info"

        connector = aiohttp.TCPConnector(ssl=self.ssl_context)

        async with aiohttp.ClientSession(
            connector=connector, timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    _LOGGER.debug("Received 401 on meter info, attempting token refresh")
                    await self._ensure_valid_token()
                    headers = {"Authorization": f"Bearer {self.access_token}"}
                    async with session.get(url, headers=headers) as retry_response:
                        if retry_response.status == 200:
                            return await retry_response.json()
                        else:
                            raise aiohttp.ClientResponseError(
                                retry_response.request_info,
                                retry_response.history,
                                status=retry_response.status,
                                message=f"Failed to get meter info after token refresh: {retry_response.status}",
                            )
                else:
                    raise aiohttp.ClientResponseError(
                        response.request_info,
                        response.history,
                        status=response.status,
                        message=f"Failed to get meter info: {response.status}",
                    )
