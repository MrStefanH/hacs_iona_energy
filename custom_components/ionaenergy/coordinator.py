"""DataUpdateCoordinator for iONA Energy (single poll cycle, shared API state)."""

from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import IONAEnergyAPI
from .const import DOMAIN, GROSS_SHARE_URL

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

_INITIALISATION_ENDPOINT = "GET https://api.n2g-iona.net/v2/initialisation"


def _log_coordinator_api_error(
    logger: logging.Logger,
    human_label: str,
    technical_detail: str,
    ex: BaseException,
) -> None:
    """Log API/update failures with type + message; full traceback when debug enabled."""
    msg = str(ex).strip() or repr(ex)
    logger.error(
        "%s (%s): [%s] %s",
        human_label,
        technical_detail,
        type(ex).__name__,
        msg,
        exc_info=logger.isEnabledFor(logging.DEBUG),
    )


def _meter_serial_from_meter(meter: dict[str, Any] | None) -> str | None:
    """Extract meter serial from N2G /v2/meter/info payload."""
    if not meter or meter.get("status") != "ok":
        return None
    data = meter.get("data") or {}
    serial = data.get("Serialnumber")
    if serial is not None and str(serial).strip():
        return str(serial).strip()
    return None


def _find_nested_value(obj: Any, key: str, _depth: int = 0) -> Any:
    """Return first dict[key] found by shallow DFS (initialisation payloads)."""
    if _depth > 12:
        return None
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_nested_value(v, key, _depth + 1)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_nested_value(item, key, _depth + 1)
            if found is not None:
                return found
    return None


def _hash_meter_serial_sha256(clear_serial: str) -> str:
    """Iona dynamic-tariff API expects SHA-256 hex (64 chars) of UTF-8 serial."""
    return hashlib.sha256(clear_serial.strip().encode("utf-8")).hexdigest()


def _meter_serial_param_for_gross_share(
    initialisation: dict[str, Any] | None,
    meter: dict[str, Any] | None,
) -> tuple[str | None, str]:
    """Resolve meter_serial_number query param: init hash or SHA-256(clear serial)."""
    hashed = _find_nested_value(initialisation, "hashedMeterSerialNumber")
    if hashed is not None and str(hashed).strip():
        return str(hashed).strip(), "hashedMeterSerialNumber"
    clear = _meter_serial_from_meter(meter)
    if clear:
        return _hash_meter_serial_sha256(clear), "sha256(Serialnumber)"
    return None, ""


def _route_to_enviam_test(initialisation: dict[str, Any] | None) -> bool:
    """Match Iona meterInfos.routeToEnviamApiTest for gross_share ?is_test=."""
    raw = _find_nested_value(initialisation, "routeToEnviamApiTest")
    if raw is None:
        return False
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes")


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
            _log_coordinator_api_error(
                _LOGGER,
                "iONA Energy connection sensor update failed",
                _INITIALISATION_ENDPOINT,
                ex,
            )

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
            _log_coordinator_api_error(
                _LOGGER,
                "iONA Energy power sensor update failed",
                "GET https://api.n2g-iona.net/v2/power/…",
                ex,
            )

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
            _log_coordinator_api_error(
                _LOGGER,
                "iONA Energy total energy sensor update failed",
                "GET https://api.n2g-iona.net/v2/meter/info",
                ex,
            )

        data["gross_share"] = None
        data["gross_share_error"] = None
        meter_param, param_source = _meter_serial_param_for_gross_share(
            data.get("initialisation"),
            data.get("meter"),
        )
        is_test = _route_to_enviam_test(data.get("initialisation"))
        if meter_param:
            try:
                data["gross_share"] = await self.api.get_gross_share(
                    meter_param, is_test=is_test
                )
                gs = data["gross_share"]
                if isinstance(gs, dict):
                    _LOGGER.debug(
                        "iONA Energy gross_share: %s (%s, id %s…)",
                        gs.get("gross_share"),
                        param_source,
                        meter_param[:8],
                    )
            except Exception as ex:  # pylint: disable=broad-except
                data["gross_share_error"] = ex
                _log_coordinator_api_error(
                    _LOGGER,
                    "iONA Energy gross_share (dynamic tariff) fetch failed",
                    f"GET {GROSS_SHARE_URL}",
                    ex,
                )
        else:
            _LOGGER.debug(
                "Skipping gross_share: no hashedMeterSerialNumber in init "
                "and no Serialnumber in /v2/meter/info"
            )

        return data
