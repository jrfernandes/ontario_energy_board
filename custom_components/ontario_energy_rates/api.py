"""Utility methods used by the Ontario Energy Board integration.
"""
import aiohttp
import async_timeout
import logging
import xml.etree.ElementTree as ET
from typing import Final

from bs4 import BeautifulSoup

from .const import (
    CURRENT_PEAK_URL,
    RATES_URL,
    CLASS_IS_OFF_PEAK,
    CLASS_IS_MID_PEAK,
    CLASS_IS_ON_PEAK,
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
    _active_peak = None
    off_peak_rate = None
    mid_peak_rate = None
    on_peak_rate = None

    def __init__(self, energy_company, websession):
        self.energy_company = energy_company
        self.websession = websession

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

    async def refresh_current_peak_data(self):
        """Parses the OER website to find what is the current peak."""
        async with async_timeout.timeout(self._timeout):
            response = await self.websession.get(CURRENT_PEAK_URL)
        content = await response.text()

        soup = BeautifulSoup(content, "html.parser")
        peak_classes = {
            "off_peak": CLASS_IS_OFF_PEAK,
            "mid_peak": CLASS_IS_MID_PEAK,
            "on_peak": CLASS_IS_ON_PEAK,
        }
        for peak_id, peak_class in peak_classes.items():
            if soup.select(f"li.{peak_class}"):
                self._active_peak = peak_id
                return

        _LOGGER.error(
            "Could not find active peak. Perhaps the webpage layout has changed"
        )

    @property
    def active_peak(self):
        """Returns the current peak."""
        return self._active_peak

    @property
    def active_peak_rate(self):
        """Returns the current peak's rate."""
        return getattr(self, f"{self.active_peak}_rate")
