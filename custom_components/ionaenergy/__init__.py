"""The iONA Energy integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import api

_PLATFORMS: list[Platform] = [Platform.SENSOR]

type IONAEnergyConfigEntry = ConfigEntry[api.IONAEnergyAPI]


async def async_setup_entry(hass: HomeAssistant, entry: IONAEnergyConfigEntry) -> bool:
    """Set up iONA Energy from a config entry."""
    # Create API client and set the config entry for token updates
    api_client = api.IONAEnergyAPI(hass, entry.data)
    api_client.set_config_entry(entry)
    entry.runtime_data = api_client

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IONAEnergyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
