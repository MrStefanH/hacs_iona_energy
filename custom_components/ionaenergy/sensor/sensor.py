"""The iONA Energy sensors."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .. import api
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iONA Energy sensor platform."""
    api_client: api.IONAEnergyAPI = config_entry.runtime_data

    async_add_entities(
        [
            IONAEnergyConnectionSensor(api_client, config_entry),
            IONAEnergyTokenRefreshSensor(api_client, config_entry, hass),
            IONAEnergyPowerSensor(api_client, config_entry),
        ],
        True,
    )


class IONAEnergyConnectionSensor(SensorEntity):
    """Representation of an iONA Energy connection status sensor."""

    def __init__(
        self, api_client: api.IONAEnergyAPI, config_entry: ConfigEntry
    ) -> None:
        """Initialize the connection status sensor."""
        self.api_client = api_client
        self.config_entry = config_entry
        self._attr_name = f"iONA Energy Connection Status"
        self._attr_unique_id = f"{config_entry.entry_id}_connection_status"
        self._attr_native_value = "Unknown"
        self._attr_available = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._attr_native_value

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            # Test the connection by attempting to get initialisation data
            await self.api_client.get_initialisation_data()
            self._attr_native_value = "Connected"
            self._attr_available = True
            _LOGGER.debug("iONA Energy connection status: Connected")
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Error updating iONA Energy connection sensor: %s", ex)
            self._attr_native_value = "Disconnected"
            self._attr_available = False


class IONAEnergyTokenRefreshSensor(SensorEntity):
    """Representation of an iONA Energy token refresh timestamp sensor."""

    def __init__(
        self,
        api_client: api.IONAEnergyAPI,
        config_entry: ConfigEntry,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the token refresh sensor."""
        self.api_client = api_client
        self.config_entry = config_entry
        self.hass = hass
        self._attr_name = f"iONA Energy Last Token Refresh"
        self._attr_unique_id = f"{config_entry.entry_id}_token_refresh"
        self._attr_native_value = None
        self._attr_available = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._attr_native_value

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            # Check if we have a valid token and get the last refresh time
            if self.api_client.access_token:
                # Convert the last token refresh timestamp to a readable datetime
                # Convert from UTC to local timezone
                from datetime import timezone

                # Get the local timezone from Home Assistant configuration
                # Use the system's local timezone as fallback
                try:
                    import zoneinfo

                    local_tz = zoneinfo.ZoneInfo(self.hass.config.time_zone)
                except (ImportError, zoneinfo.ZoneInfoNotFoundError):
                    # Fallback to system local timezone
                    local_tz = datetime.now().astimezone().tzinfo

                # Convert UTC timestamp to local time
                utc_time = datetime.fromtimestamp(
                    self.api_client.last_token_refresh, tz=timezone.utc
                )
                local_time = utc_time.astimezone(local_tz)

                self._attr_native_value = local_time.strftime("%Y-%m-%d %H:%M:%S")
                self._attr_available = True
                _LOGGER.debug(
                    "iONA Energy last token refresh: %s", self._attr_native_value
                )
            else:
                self._attr_native_value = "No token available"
                self._attr_available = False
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Error updating iONA Energy token refresh sensor: %s", ex)
            self._attr_native_value = "Error"
            self._attr_available = False


class IONAEnergyPowerSensor(SensorEntity):
    """Representation of an iONA Energy current power consumption sensor."""

    def __init__(
        self, api_client: api.IONAEnergyAPI, config_entry: ConfigEntry
    ) -> None:
        """Initialize the power consumption sensor."""
        self.api_client = api_client
        self.config_entry = config_entry
        self._attr_name = f"iONA Energy Current Power"
        self._attr_unique_id = f"{config_entry.entry_id}_current_power"
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_available = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self._attr_native_value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._attr_native_unit_of_measurement

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            # Get current power consumption data
            power_data = await self.api_client.get_current_power()

            if power_data and "power" in power_data:
                self._attr_native_value = power_data["power"]
                self._attr_available = True
                _LOGGER.debug(
                    "iONA Energy current power: %s W (timestamp: %s)",
                    power_data["power"],
                    power_data.get("timestamp", "unknown"),
                )
            else:
                self._attr_native_value = None
                self._attr_available = False
                _LOGGER.warning("No power data available")

        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Error updating iONA Energy power sensor: %s", ex)
            self._attr_native_value = None
            self._attr_available = False
