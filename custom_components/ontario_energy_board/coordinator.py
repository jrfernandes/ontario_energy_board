"""Utility methods used by the Ontario Energy Board integration."""

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle

from .common import energy_sector_from_company_name, get_energy_company_data
from .const import CONF_ENERGY_COMPANY, CONF_ULO_ENABLED, DOMAIN, REFRESH_RATES_INTERVAL

_LOGGER: Final = logging.getLogger(__name__)


class OntarioEnergyBoardDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Ontario Energy Board data."""

    energy_sector = None
    company_data = {}

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=REFRESH_RATES_INTERVAL,
            update_method=self._async_update_data,
        )
        self.websession = async_get_clientsession(hass)
        self.energy_company = config_entry.data[CONF_ENERGY_COMPANY]
        self.ulo_enabled = config_entry.data[CONF_ULO_ENABLED]
        # Derived from the stored company name, which carries the sector as a
        # suffix. It is a property of the configuration, not of the fetch.
        self.energy_sector = energy_sector_from_company_name(self.energy_company)

    @Throttle(REFRESH_RATES_INTERVAL)
    async def _async_update_data(self) -> None:
        """Fetch the rates for the selected energy company."""

        company_data = await get_energy_company_data(
            self.websession, self.energy_sector, self.energy_company
        )

        if company_data is None:
            raise UpdateFailed(f"Could not find energy rates for {self.energy_company}")

        self.company_data = company_data
