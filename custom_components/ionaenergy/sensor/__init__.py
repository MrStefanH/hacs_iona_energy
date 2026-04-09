"""The iONA Energy sensor platform."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .sensor import (
    IONAEnergyConnectionSensor,
    IONAEnergyPowerSensor,
    IONAEnergyTokenRefreshSensor,
    IONAEnergyTotalEnergySensor,
)
from ..coordinator import IONAEnergyDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iONA Energy sensor platform."""
    coordinator: IONAEnergyDataUpdateCoordinator = config_entry.runtime_data

    async_add_entities(
        [
            IONAEnergyConnectionSensor(coordinator, config_entry),
            IONAEnergyTokenRefreshSensor(coordinator, config_entry),
            IONAEnergyPowerSensor(coordinator, config_entry),
            IONAEnergyTotalEnergySensor(coordinator, config_entry),
        ],
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
