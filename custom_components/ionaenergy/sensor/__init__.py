"""The iONA Energy sensor platform."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .sensor import (
    IONAEnergyConnectionSensor,
    IONAEnergyTokenRefreshSensor,
    IONAEnergyPowerSensor,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iONA Energy sensor platform."""
    api_client = config_entry.runtime_data

    async_add_entities(
        [
            IONAEnergyConnectionSensor(api_client, config_entry),
            IONAEnergyTokenRefreshSensor(api_client, config_entry, hass),
            IONAEnergyPowerSensor(api_client, config_entry),
        ],
        True,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
