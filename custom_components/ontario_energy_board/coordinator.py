"""Data update coordinator for the Ontario Energy Board integration."""

from collections.abc import Container
from datetime import date
import logging
from typing import Final

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import (
    closest_company,
    effective_ulo_enabled,
    energy_sector_from_company_name,
    get_energy_companies,
    get_energy_company_data,
)
from .const import CONF_ENERGY_COMPANY, DOMAIN, REFRESH_RATES_INTERVAL

_LOGGER: Final = logging.getLogger(__name__)


class OntarioEnergyBoardDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator to manage Ontario Energy Board data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        ontario_holidays: Container[date],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=REFRESH_RATES_INTERVAL,
        )
        self.websession = async_get_clientsession(hass)
        self.ontario_holidays = ontario_holidays
        self.energy_company = config_entry.data[CONF_ENERGY_COMPANY]
        self.ulo_enabled = effective_ulo_enabled(config_entry)
        # Derived from the stored company name, which carries the sector as a
        # suffix. It is a property of the configuration, not of the fetch.
        self.energy_sector = energy_sector_from_company_name(self.energy_company)

    @property
    def company_data(self) -> dict:
        """The most recently fetched rates, empty before the first refresh."""
        return self.data or {}

    async def _async_update_data(self) -> dict:
        """Fetch the rates for the selected energy company."""

        company_data = await get_energy_company_data(
            self.websession, self.energy_sector, self.energy_company
        )

        if company_data is None:
            # The company has left the document. Ontario distributors are
            # regularly renamed or merged into rate zones, and no amount of
            # retrying brings the old name back, so this is reported as
            # something the user has to act on rather than retried forever.
            await self._async_report_company_missing()

            raise ConfigEntryError(
                f"{self.energy_company} is no longer published by the Ontario "
                "Energy Board, and the entry needs to be pointed at its "
                "current name"
            )

        self._async_clear_company_missing()

        return company_data

    async def _async_report_company_missing(self) -> None:
        """Raise a repair explaining the entry needs re-pointing."""
        suggestion = ""

        try:
            available = await get_energy_companies(self.websession, self.energy_sector)
        except (aiohttp.ClientError, TimeoutError):
            available = []

        if match := closest_company(self.energy_company, available):
            suggestion = match

        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._company_missing_issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="company_suggestion" if suggestion else "company_missing",
            translation_placeholders={
                "energy_company": self.energy_company,
                "suggestion": suggestion,
            },
        )

    def _async_clear_company_missing(self) -> None:
        ir.async_delete_issue(self.hass, DOMAIN, self._company_missing_issue_id)

    @property
    def _company_missing_issue_id(self) -> str:
        return f"company_missing_{self.config_entry.entry_id}"
