"""DataUpdateCoordinator for iONA Energy (single poll cycle, shared API state)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import IONAEnergyAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)


class IONAEnergyDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches initialisation, power, and meter data once per update interval."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: IONAEnergyAPI,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api_client

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh all endpoints; partial success keeps last_update_success True."""
        data: dict[str, Any] = {}

        try:
            data["initialisation"] = await self.api.get_initialisation_data()
            data["initialisation_error"] = None
            _LOGGER.debug("iONA Energy connection status: Connected")
        except Exception as ex:  # pylint: disable=broad-except
            data["initialisation"] = None
            data["initialisation_error"] = ex
            _LOGGER.error("Error updating iONA Energy connection sensor: %s", ex)

        try:
            power = await self.api.get_current_power()
            data["power"] = power
            data["power_error"] = None
            if power and "power" in power:
                _LOGGER.debug(
                    "iONA Energy current power: %s W (timestamp: %s)",
                    power["power"],
                    power.get("timestamp", "unknown"),
                )
        except Exception as ex:  # pylint: disable=broad-except
            data["power"] = None
            data["power_error"] = ex
            _LOGGER.error("Error updating iONA Energy power sensor: %s", ex)

        try:
            meter = await self.api.get_meter_info()
            data["meter"] = meter
            data["meter_error"] = None
            if (
                meter
                and meter.get("status") == "ok"
                and meter.get("data", {}).get("Electricity", {}).get("CSD") is not None
            ):
                energy_kwh = meter["data"]["Electricity"]["CSD"] / 1000.0
                _LOGGER.debug(
                    "iONA Energy total energy: %s kWh (serial: %s)",
                    energy_kwh,
                    meter.get("data", {}).get("Serialnumber", "unknown"),
                )
        except Exception as ex:  # pylint: disable=broad-except
            data["meter"] = None
            data["meter_error"] = ex
            _LOGGER.error("Error updating iONA Energy total energy sensor: %s", ex)

        return data
