"""Config flow for Ontario Energy Board integration."""

import logging
from typing import Any, Final

import aiohttp
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .common import energy_sector_from_company_name, get_energy_companies
from .const import CONF_ENERGY_COMPANY, CONF_ULO_ENABLED, DOMAIN, SECTOR_ELECTRICITY

_LOGGER: Final = logging.getLogger(__name__)


class OntarioEnergyBoardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ontario Energy Board."""

    VERSION = 2

    def __init__(self) -> None:
        self._energy_company: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick the energy company.

        Electricity companies continue to the rate plan step. Natural gas has no
        peak periods, so there is nothing further to ask.
        """
        if user_input is not None:
            energy_company = user_input[CONF_ENERGY_COMPANY]

            if energy_sector_from_company_name(energy_company) != SECTOR_ELECTRICITY:
                return await self._async_create_entry(energy_company, ulo_enabled=False)

            self._energy_company = energy_company

            return await self.async_step_rate_plan()

        # Only needed to build the form. Home Assistant validates the submitted
        # value against the schema shown here, so the documents are downloaded
        # once per attempt rather than twice.
        try:
            companies_list = await get_energy_companies(
                async_get_clientsession(self.hass)
            )
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.exception("Failed to download the energy rates documents")
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ENERGY_COMPANY): vol.In(companies_list)}
            ),
        )

    async def async_step_rate_plan(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Ask which electricity rate plan the account is on."""
        assert self._energy_company is not None

        if user_input is not None:
            return await self._async_create_entry(
                self._energy_company, user_input[CONF_ULO_ENABLED]
            )

        return self.async_show_form(
            step_id="rate_plan",
            data_schema=vol.Schema(
                {vol.Required(CONF_ULO_ENABLED, default=False): bool}
            ),
            description_placeholders={"energy_company": self._energy_company},
        )

    async def _async_create_entry(
        self, energy_company: str, ulo_enabled: bool
    ) -> config_entries.ConfigFlowResult:
        """Create the entry, keeping the unique id format unchanged.

        Gas entries still record ulo_enabled as False, so their unique id is the
        same as one created before the rate plan moved to its own step.
        """
        await self.async_set_unique_id(f"{energy_company} {ulo_enabled}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=energy_company,
            data={
                CONF_ENERGY_COMPANY: energy_company,
                CONF_ULO_ENABLED: ulo_enabled,
            },
        )
