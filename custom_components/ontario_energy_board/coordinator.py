"""Data update coordinator for the Ontario Energy Board integration."""

from collections.abc import Container
from datetime import date
import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .common import (
    async_fetch_rates_document,
    closest_company,
    effective_ulo_enabled,
    energy_sector_from_company_name,
    parse_energy_companies,
    parse_energy_company_data,
)
from .const import CONF_ENERGY_COMPANY, DOMAIN, REFRESH_RATES_INTERVAL

_LOGGER: Final = logging.getLogger(__name__)


def company_missing_issue_id(entry_id: str) -> str:
    """Identify the repair raised when a company leaves the document."""
    return f"company_missing_{entry_id}"


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

        # Parsed twice from one download rather than fetched twice: the list of
        # companies is only needed to suggest a replacement, and it is the same
        # document the rates come from.
        content = await async_fetch_rates_document(self.websession, self.energy_sector)

        company_data = parse_energy_company_data(
            self.energy_sector, content, self.energy_company
        )

        if company_data is None:
            # The company has left the document. Ontario distributors are
            # regularly renamed or merged into rate zones, and no amount of
            # retrying brings the old name back, so this is reported as
            # something the user has to act on rather than retried forever.
            self._async_report_company_missing(
                parse_energy_companies(self.energy_sector, content)
            )

            raise ConfigEntryError(
                f"{self.energy_company} is no longer published by the Ontario "
                "Energy Board, and the entry needs to be pointed at its "
                "current name"
            )

        self._async_clear_company_missing()

        return company_data

    def _async_report_company_missing(self, available: list[str]) -> None:
        """Raise a repair explaining the entry needs re-pointing."""
        suggestion = closest_company(self.energy_company, available) or ""

        ir.async_create_issue(
            self.hass,
            DOMAIN,
            company_missing_issue_id(self.config_entry.entry_id),
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="company_suggestion" if suggestion else "company_missing",
            translation_placeholders={
                "energy_company": self.energy_company,
                "suggestion": suggestion,
            },
        )

    def _async_clear_company_missing(self) -> None:
        ir.async_delete_issue(
            self.hass, DOMAIN, company_missing_issue_id(self.config_entry.entry_id)
        )
