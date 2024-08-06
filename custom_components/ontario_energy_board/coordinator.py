"""Utility methods used by the Ontario Energy Board integration."""

import logging
import re
from typing import Final

import holidays
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import Throttle

from .common import get_energy_company_data

from .const import (
    DOMAIN,
    CONF_ULO_ENABLED,
    REFRESH_RATES_INTERVAL,
)

_LOGGER: Final = logging.getLogger(__name__)


class OntarioEnergyBoardDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Ontario Energy Board data."""

    _timeout = 10
    energy_sector = None
    company_data = {}

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=REFRESH_RATES_INTERVAL,
            update_method=self._async_update_data,
        )
        self.websession = async_get_clientsession(hass)
        self.energy_company = self.config_entry.unique_id
        self.ulo_enabled = self.config_entry.data[CONF_ULO_ENABLED]
        self.ontario_holidays = holidays.Canada(
            prov="ON", observed=True, categories={"public", "optional"}
        )

    @Throttle(REFRESH_RATES_INTERVAL)
    async def _async_update_data(self) -> None:
        """Parses the official XML document extracting the rates for
        the selected energy company.
        """

        self.company_data = {}

        company_energy_sector_search = re.search(
            ".*(Natural Gas|Electricity).*", self.energy_company
        )
        self.energy_sector = (
            company_energy_sector_search.group(1).lower().replace(" ", "_")
        )

        self.company_data = await get_energy_company_data(
            self.energy_sector, self.energy_company
        )

        if self.company_data is not None:
            return

        self.logger.error("Could not find energy rates for %s", self.energy_company)
