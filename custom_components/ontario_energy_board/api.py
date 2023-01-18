"""Utility methods used by the Ontario Energy Board integration.

TECH-DEBT: This class is not being in use anymore. At the moment it's only being
used for unit tests. These tests should instead be against the sensor component itself.
"""
import aiohttp
import async_timeout
import logging
import xml.etree.ElementTree as ET
from datetime import date
from typing import Final

import holidays
from homeassistant.util.dt import as_local, now

from .const import (
    STATE_MID_PEAK,
    STATE_OFF_PEAK,
    STATE_ON_PEAK,
    RATES_URL,
    XML_KEY_OFF_PEAK_RATE,
    XML_KEY_MID_PEAK_RATE,
    XML_KEY_ON_PEAK_RATE,
)


_LOGGER: Final = logging.getLogger(__name__)


async def get_energy_companies() -> list[str]:
    """Generates a list of all energy companies available
    in the XML document including the available classes.
    """

    async with aiohttp.ClientSession() as session:
        async with session.get(RATES_URL) as response:
            content = await response.text()

    tree = ET.fromstring(content)

    all_companies = [
        "{company_name} ({company_class})".format(
            company_name=company.find("Dist").text,
            company_class=company.find("Class").text,
        )
        for company in tree.findall("BillDataRow")
    ]
    all_companies.sort()

    return all_companies


class OntarioEnergyBoard:
    """Class to communication with the Ontario Energy Rate services."""

    _timeout = 10
    off_peak_rate = None
    mid_peak_rate = None
    on_peak_rate = None

    def __init__(self, energy_company, websession):
        self.energy_company = energy_company
        self.websession = websession
        self.ontario_holidays = holidays.Canada(prov="ON", observed=True)

    async def get_rates(self):
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
                return

        _LOGGER.error("Could not find energy rates for %s", self.energy_company)

    @property
    def active_peak(self):
        """
        Find the active peak based on the current day and hour.

        According to OEB, weekends and holidays are 24-hour off peak periods.
        During summer (observed from May 1st to Oct 31st), the morning and evening
        periods are mid-peak, and the afternoon is on-peak. This flips during winter
        time, where morning and evening are on-peak and afternoons mid-peak.
        """
        current_time = as_local(now())

        is_summer = (
            date(current_time.year, 5, 1)
            <= current_time.date()
            <= date(current_time.year, 10, 31)
        )
        is_holiday = current_time.date() in self.ontario_holidays
        is_weekend = current_time.weekday() >= 5

        if is_holiday or is_weekend:
            return STATE_OFF_PEAK

        current_hour = int(current_time.strftime("%H"))
        if (7 <= current_hour < 11) or (17 <= current_hour < 19):
            return STATE_MID_PEAK if is_summer else STATE_ON_PEAK
        if 11 <= current_hour < 17:
            return STATE_ON_PEAK if is_summer else STATE_MID_PEAK

        return STATE_OFF_PEAK

    @property
    def active_peak_rate(self):
        """Returns the current peak's rate."""
        return getattr(self, f"{self.active_peak}_rate")
