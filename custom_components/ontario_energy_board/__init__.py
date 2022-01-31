"""The Ontario Energy Board component.
"""
import logging
from datetime import timedelta
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import OntarioEnergyBoard
from .const import DOMAIN, REFRESH_CURRENT_PEAK_TIMEOUT


_LOGGER: Final = logging.getLogger(__name__)


PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass, entry: ConfigEntry):
    """Set up the Ontario Energy Board component."""
    hass.data.setdefault(DOMAIN, {})

    ontario_energy_board = OntarioEnergyBoard(
        entry.unique_id,
        async_get_clientsession(hass),
    )
    await ontario_energy_board.get_rates()

    coordinator = OntarioEnergyBoardDataUpdateCoordinator(
        hass, ontario_energy_board=ontario_energy_board
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class OntarioEnergyBoardDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Ontario Energy Board data."""

    def __init__(
        self, hass: HomeAssistant, *, ontario_energy_board: OntarioEnergyBoard
    ) -> None:
        self.ontario_energy_board = ontario_energy_board

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=REFRESH_CURRENT_PEAK_TIMEOUT),
        )

    async def _async_update_data(self) -> None:
        data = await self.ontario_energy_board.refresh_current_peak_data()
        return data
