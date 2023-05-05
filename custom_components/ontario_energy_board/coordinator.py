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
    RATES_URL,
    REFRESH_RATES_INTERVAL,
    XML_KEY_OFF_PEAK_RATE,
    XML_KEY_MID_PEAK_RATE,
    XML_KEY_ON_PEAK_RATE,
    XML_KEY_TIER_THRESHOLD,
    XML_KEY_TIER_1_RATE,
    XML_KEY_TIER_2_RATE,
    XML_KEY_SERVICE_CHARGE,
    XML_KEY_LOSS_ADJUSTMENT_FACTOR,
    XML_KEY_NETWORK_SERVICE_RATE,
    XML_KEY_CONNECTION_SERVICE_RATE,
    XML_KEY_WHOLESALE_MARKET_SERVICE_RATE,
    XML_KEY_RURAL_REMOTE_RATE_PROTECTION_CHARGE,
    XML_KEY_STANDARD_SUPPLY_SERVICE,
    XML_KEY_GST,
    XML_KEY_REBATE,
    XML_KEY_ONE_TIME_FIXED_CHARGE,
)


_LOGGER: Final = logging.getLogger(__name__)


class OntarioEnergyBoardDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Ontario Energy Board data."""

    _timeout = 10
    off_peak_rate = None
    mid_peak_rate = None
    on_peak_rate = None
    tier_threshold = None
    tier_1_rate = None
    tier_2_rate = None
    service_charge = None
    loss_adjustment_factor = None
    network_service_rate = None
    connection_service_rate = None
    wholesale_market_service_rate = None
    rural_remote_rate_protection_charge = None
    standard_supply_service = None
    gst = None
    rebate = None
    one_time_fixed_charge = None

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
        self.ontario_holidays = holidays.Canada(prov="ON", observed=True)

    @Throttle(REFRESH_RATES_INTERVAL)
    async def _async_update_data(self) -> None:
        """Parses the official XML document extracting the rates for
        the selected energy company.
        """
        async with async_timeout.timeout(self._timeout):
            response = await self.websession.get(RATES_URL)

        content = await response.text()
        tree = ET.fromstring(content)

        for company in tree.findall("BillDataRow"):
            current_company = "{company_name} ({company_class})".format(
                company_name=company.find("Dist").text,
                company_class=company.find("Class").text,
            )
            if current_company == self.energy_company:
                self.off_peak_rate = float(company.find(XML_KEY_OFF_PEAK_RATE).text)
                self.mid_peak_rate = float(company.find(XML_KEY_MID_PEAK_RATE).text)
                self.on_peak_rate = float(company.find(XML_KEY_ON_PEAK_RATE).text)
                self.tier_threshold = float(company.find(XML_KEY_TIER_THRESHOLD).text)
                self.tier_1_rate = float(company.find(XML_KEY_TIER_1_RATE).text)
                self.tier_2_rate = float(company.find(XML_KEY_TIER_2_RATE).text)
                self.service_charge = float(company.find(XML_KEY_SERVICE_CHARGE).text)
                self.loss_adjustment_factor = float(
                    company.find(XML_KEY_LOSS_ADJUSTMENT_FACTOR).text
                )
                self.network_service_rate = float(
                    company.find(XML_KEY_NETWORK_SERVICE_RATE).text
                )
                self.connection_service_rate = float(
                    company.find(XML_KEY_CONNECTION_SERVICE_RATE).text
                )
                self.wholesale_market_service_rate = float(
                    company.find(XML_KEY_WHOLESALE_MARKET_SERVICE_RATE).text
                )
                self.rural_remote_rate_protection_charge = float(
                    company.find(XML_KEY_RURAL_REMOTE_RATE_PROTECTION_CHARGE).text
                )
                self.standard_supply_service = float(
                    company.find(XML_KEY_STANDARD_SUPPLY_SERVICE).text
                )
                self.gst = float(company.find(XML_KEY_GST).text)
                self.rebate = float(company.find(XML_KEY_REBATE).text)
                self.one_time_fixed_charge = float(
                    company.find(XML_KEY_ONE_TIME_FIXED_CHARGE).text
                )
                return

        self.logger.error("Could not find energy rates for %s", self.energy_company)
