"""The iONA Energy sensors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import callback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..coordinator import IONAEnergyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class IONAEnergyConnectionSensor(
    CoordinatorEntity[IONAEnergyDataUpdateCoordinator], SensorEntity
):
    """Representation of an iONA Energy connection status sensor."""

    def __init__(
        self,
        coordinator: IONAEnergyDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the connection status sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = "iONA Energy Connection Status"
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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._attr_available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        err = data.get("initialisation_error")
        if err is not None:
            self._attr_native_value = "Disconnected"
            self._attr_available = False
        elif data.get("initialisation") is not None:
            self._attr_native_value = "Connected"
            self._attr_available = True
        else:
            self._attr_native_value = "Unknown"
            self._attr_available = False
        super()._handle_coordinator_update()


class IONAEnergyTokenRefreshSensor(
    CoordinatorEntity[IONAEnergyDataUpdateCoordinator], SensorEntity
):
    """Representation of an iONA Energy token refresh timestamp sensor."""

    def __init__(
        self,
        coordinator: IONAEnergyDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the token refresh sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = "iONA Energy Last Token Refresh"
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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._attr_available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        try:
            if self.coordinator.api.access_token:
                try:
                    import zoneinfo

                    local_tz = zoneinfo.ZoneInfo(self.coordinator.hass.config.time_zone)
                except (ImportError, zoneinfo.ZoneInfoNotFoundError):
                    local_tz = datetime.now().astimezone().tzinfo

                utc_time = datetime.fromtimestamp(
                    self.coordinator.api.last_token_refresh, tz=timezone.utc
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
        super()._handle_coordinator_update()


class IONAEnergyPowerSensor(
    CoordinatorEntity[IONAEnergyDataUpdateCoordinator], SensorEntity
):
    """Representation of an iONA Energy current power consumption sensor."""

    def __init__(
        self,
        coordinator: IONAEnergyDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the power consumption sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = "iONA Energy Current Power"
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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._attr_available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        err = data.get("power_error")
        power_data = data.get("power")
        if err is not None:
            self._attr_native_value = None
            self._attr_available = False
        elif power_data and "power" in power_data:
            self._attr_native_value = power_data["power"]
            self._attr_available = True
        else:
            self._attr_native_value = None
            self._attr_available = False
            _LOGGER.warning("No power data available")
        super()._handle_coordinator_update()


class IONAEnergyGrossShareSensor(
    CoordinatorEntity[IONAEnergyDataUpdateCoordinator], SensorEntity
):
    """Dynamic-tariff gross_share (ct/kWh) from SDACe hub."""

    _attr_suggested_display_precision = 5

    def __init__(
        self,
        coordinator: IONAEnergyDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize gross_share sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = "iONA Energy Gross Share"
        self._attr_unique_id = f"{config_entry.entry_id}_gross_share"
        self._attr_native_value: float | None = None
        self._attr_native_unit_of_measurement = "ct/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_available = False
        self._attr_extra_state_attributes: dict[str, str | None] = {}

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def native_value(self) -> StateType:
        """Return gross_share value."""
        return self._attr_native_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit."""
        return self._attr_native_unit_of_measurement

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._attr_available

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Last update time and meter id from API."""
        return self._attr_extra_state_attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        err = data.get("gross_share_error")
        payload = data.get("gross_share")

        if err is not None:
            self._attr_native_value = None
            self._attr_available = False
            self._attr_extra_state_attributes = {}
        elif payload and "gross_share" in payload:
            try:
                self._attr_native_value = float(payload["gross_share"])
            except (TypeError, ValueError):
                self._attr_native_value = None
                self._attr_available = False
                self._attr_extra_state_attributes = {}
                super()._handle_coordinator_update()
                return
            self._attr_available = True
            self._attr_extra_state_attributes = {
                "last_updated": payload.get("last_updated"),
                "meter_serial_number": payload.get("meter_serial_number"),
            }
        else:
            self._attr_native_value = None
            self._attr_available = False
            self._attr_extra_state_attributes = {}
        super()._handle_coordinator_update()


class IONAEnergyEexSpotPriceSensor(
    CoordinatorEntity[IONAEnergyDataUpdateCoordinator], SensorEntity
):
    """Current EEX day-ahead spot (15-minute slot), API value / 10 → ct/kWh."""

    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: IONAEnergyDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize EEX spot price sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = "iONA Energy EEX Spot Price"
        self._attr_unique_id = f"{config_entry.entry_id}_eex_spot_price"
        self._attr_native_value: float | None = None
        self._attr_native_unit_of_measurement = "ct/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_available = False
        self._attr_extra_state_attributes: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def native_value(self) -> StateType:
        """Return spot price in ct/kWh."""
        return self._attr_native_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit."""
        return self._attr_native_unit_of_measurement

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._attr_available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Interval, day average, raw API price for the slot."""
        return self._attr_extra_state_attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        err = self.coordinator.data.get("spot_prices_error")
        payload = self.coordinator.data.get("spot_price")

        if err is not None:
            self._attr_native_value = None
            self._attr_available = False
            self._attr_extra_state_attributes = {}
        elif isinstance(payload, dict) and payload.get("ct_per_kwh") is not None:
            try:
                self._attr_native_value = float(payload["ct_per_kwh"])
            except (TypeError, ValueError):
                self._attr_native_value = None
                self._attr_available = False
                self._attr_extra_state_attributes = {}
                super()._handle_coordinator_update()
                return
            self._attr_available = True
            self._attr_extra_state_attributes = {
                k: payload.get(k)
                for k in (
                    "time_slice",
                    "average_ct_per_kwh",
                    "interval_start",
                    "interval_end",
                    "raw_price",
                )
            }
        else:
            self._attr_native_value = None
            self._attr_available = False
            self._attr_extra_state_attributes = (
                {k: payload.get(k) for k in ("time_slice", "average_ct_per_kwh")}
                if isinstance(payload, dict)
                else {}
            )
        super()._handle_coordinator_update()


class IONAEnergyTotalEnergySensor(
    CoordinatorEntity[IONAEnergyDataUpdateCoordinator], SensorEntity
):
    """Representation of an iONA Energy total energy consumption sensor (kWh)."""

    def __init__(
        self,
        coordinator: IONAEnergyDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the total energy sensor."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_name = "iONA Energy Total Energy"
        self._attr_unique_id = f"{config_entry.entry_id}_total_energy"
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._attr_available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        err = data.get("meter_error")
        meter_info = data.get("meter")
        if err is not None:
            self._attr_native_value = None
            self._attr_available = False
        elif (
            meter_info
            and meter_info.get("status") == "ok"
            and meter_info.get("data", {}).get("Electricity", {}).get("CSD") is not None
        ):
            csd_wh = meter_info["data"]["Electricity"]["CSD"]
            self._attr_native_value = csd_wh / 1000.0
            self._attr_available = True
        else:
            self._attr_native_value = None
            self._attr_available = False
            _LOGGER.warning("No meter info available or invalid format")
        super()._handle_coordinator_update()
