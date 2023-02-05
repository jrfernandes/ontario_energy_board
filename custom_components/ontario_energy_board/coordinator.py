"""Utility methods used by the Ontario Energy Board integration.
"""
import async_timeout
import logging
import xml.etree.ElementTree as ET
from typing import Final

import holidays
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import Throttle

from .const import (
    DOMAIN,
    ELECTRICITY_RATES_URL,
    ENERGY_SECTORS,
    NATUR_GAS_RATES_URL,
    REFRESH_RATES_INTERVAL,
    XML_KEY_MAPPINGS,
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
            name = DOMAIN,
            update_interval = REFRESH_RATES_INTERVAL,
            update_method = self._async_update_data,
        )
        self.websession = async_get_clientsession(hass)
        self.energy_company = self.config_entry.unique_id
        self.ontario_holidays = holidays.Canada(prov="ON", observed=True)

    @Throttle(REFRESH_RATES_INTERVAL)
    async def _async_update_data(self) -> None:
        """Parses the official XML document extracting the rates for
        the selected energy company.
        """

        for sector in ENERGY_SECTORS:
            async with async_timeout.timeout(self._timeout):
                response = await self.websession.get(ELECTRICITY_RATES_URL if sector == 'electricity' else NATUR_GAS_RATES_URL)

            content = await response.text()
            tree = ET.fromstring(content)

            for company in tree.findall("BillDataRow" if sector == "electricity" else "GasBillData"):
                current_company = "{company_name} ({company_class}) [{company_sector}]".format(
                    company_name = company.find("Dist").text,
                    company_class = company.find("Class" if sector == "electricity" else "SA").text,
                    company_sector = sector.replace('_', ' ').title(),
                )

                if current_company == self.energy_company:
                    for element in company.iter():
                        if element.tag in ['BillDataRow', 'GasBillData', 'Lic', 'ExtID']:
                            continue

                        value = element.text

                        if element.text is not None:
                            try:
                                value = float(value)
                            except ValueError:
                                value = element.text
                        else:
                            value = ''

                        if element.tag in XML_KEY_MAPPINGS[sector]:
                            self.company_data[XML_KEY_MAPPINGS[sector][element.tag]] = value

                    self.energy_sector = sector

                    return

        self.logger.error("Could not find energy rates for %s", self.energy_company)
