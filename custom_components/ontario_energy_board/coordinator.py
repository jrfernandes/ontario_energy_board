"""Utility methods used by the Ontario Energy Board integration.
"""

import async_timeout
import logging
import xml.etree.ElementTree as ET
import re
from typing import Final

import holidays
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import Throttle

from .const import (
    DOMAIN,
    CONF_ULO_ENABLED,
    ELECTRICITY_RATES_URL,
    NATUR_GAS_RATES_URL,
    REFRESH_RATES_INTERVAL,
    XML_KEY_MAPPINGS,
    XML_KEY_OFF_PEAK_RATE,
    XML_KEY_MID_PEAK_RATE,
    XML_KEY_ON_PEAK_RATE,
    XML_KEY_ULO_OVERNIGHT_RATE,
    XML_KEY_ULO_OFF_PEAK_RATE,
    XML_KEY_ULO_MID_PEAK_RATE,
    XML_KEY_ULO_ON_PEAK_RATE,
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
        self.ontario_holidays = holidays.Canada(prov="ON", observed=True)

    @Throttle(REFRESH_RATES_INTERVAL)
    async def _async_update_data(self) -> None:
        """Parses the official XML document extracting the rates for
        the selected energy company.
        """

        self.company_data = {}

        company_energy_sector_search = re.search(
            ".*(Natural Gas|Electricity).*", self.energy_company
        )
        company_energy_sector = company_energy_sector_search.group(1)
        self.energy_sector = company_energy_sector
        company_energy_sector_key = company_energy_sector.lower().replace(" ", "_")

        async with async_timeout.timeout(self._timeout):
            response = await self.websession.get(
                ELECTRICITY_RATES_URL
                if company_energy_sector_key == "electricity"
                else NATUR_GAS_RATES_URL
            )

        content = await response.text()
        tree = ET.fromstring(content)

        for company in tree.findall(
            "BillDataRow"
            if company_energy_sector_key == "electricity"
            else "GasBillData"
        ):
            current_company = (
                "{company_name} ({company_class}) [{company_sector}]".format(
                    company_name=company.find("Dist").text,
                    company_class=company.find(
                        "Class" if company_energy_sector_key == "electricity" else "SA"
                    ).text,
                    company_sector=company_energy_sector,
                )
            )

            if current_company == self.energy_company:
                if company_energy_sector_key == "electricity":
                    self.company_data["off_peak_rate"] = float(
                        company.find(XML_KEY_OFF_PEAK_RATE).text
                    )
                    self.company_data["mid_peak_rate"] = float(
                        company.find(XML_KEY_MID_PEAK_RATE).text
                    )
                    self.company_data["on_peak_rate"] = float(
                        company.find(XML_KEY_ON_PEAK_RATE).text
                    )
                    self.company_data["ulo_overnight_rate"] = float(
                        company.find(XML_KEY_ULO_OVERNIGHT_RATE).text
                    )
                    self.company_data["ulo_off_peak_rate"] = float(
                        company.find(XML_KEY_ULO_OFF_PEAK_RATE).text
                    )
                    self.company_data["ulo_mid_peak_rate"] = float(
                        company.find(XML_KEY_ULO_MID_PEAK_RATE).text
                    )
                    self.company_data["ulo_on_peak_rate"] = float(
                        company.find(XML_KEY_ULO_ON_PEAK_RATE).text
                    )

                for element in company.iter():
                    if element.tag in ["BillDataRow", "GasBillData", "Lic", "ExtID"]:
                        continue

                    value = element.text

                    if element.text is not None:
                        try:
                            value = float(value)
                        except ValueError:
                            value = element.text
                    else:
                        value = ""

                    if element.tag in XML_KEY_MAPPINGS[company_energy_sector_key]:
                        self.company_data[
                            XML_KEY_MAPPINGS[company_energy_sector_key][element.tag]
                        ] = value

                self.energy_sector = company_energy_sector_key

                return

        self.logger.error("Could not find energy rates for %s", self.energy_company)
