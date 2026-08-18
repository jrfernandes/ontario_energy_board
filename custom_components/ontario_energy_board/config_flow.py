"""Config flow for Ontario Energy Board integration."""

import logging
from typing import Any, Final

import aiohttp
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .common import company_display_name, get_energy_companies
from .const import (
    CONF_ENERGY_COMPANY,
    CONF_ULO_ENABLED,
    DOMAIN,
    SECTOR_ELECTRICITY,
    SECTOR_NATURAL_GAS,
)

_LOGGER: Final = logging.getLogger(__name__)


class OntarioEnergyBoardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ontario Energy Board."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Choose which kind of company to add.

        Asking first means the company list can be filtered to one sector, and
        that only the rate plan question that applies is shown.
        """
        return self.async_show_menu(
            step_id="user",
            menu_options=[SECTOR_ELECTRICITY, SECTOR_NATURAL_GAS],
        )

    async def async_step_electricity(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick an electricity company and its rate plan."""
        return await self._async_step_company(SECTOR_ELECTRICITY, user_input)

    async def async_step_natural_gas(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Pick a natural gas company.

        Gas has no peak periods, so there is no rate plan to choose.
        """
        return await self._async_step_company(SECTOR_NATURAL_GAS, user_input)

    async def _async_step_company(
        self, sector: str, user_input: dict[str, Any] | None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            energy_company = user_input[CONF_ENERGY_COMPANY]
            # Gas is never asked, but the value is still recorded so its unique
            # id matches entries created before the sector was chosen first.
            ulo_enabled = user_input.get(CONF_ULO_ENABLED, False)

            await self.async_set_unique_id(f"{energy_company} {ulo_enabled}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=energy_company,
                data={
                    CONF_ENERGY_COMPANY: energy_company,
                    CONF_ULO_ENABLED: ulo_enabled,
                },
            )

        try:
            companies = await get_energy_companies(
                async_get_clientsession(self.hass), sector
            )
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.exception("Failed to download the %s rates document", sector)
            return self.async_abort(reason="cannot_connect")

        schema: dict[Any, Any] = {
            vol.Required(CONF_ENERGY_COMPANY): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        # The stored value keeps the sector suffix, since it
                        # identifies the entry; the label drops it, because the
                        # sector was chosen a step ago.
                        SelectOptionDict(
                            value=company, label=company_display_name(company)
                        )
                        for company in companies
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    sort=False,
                )
            )
        }

        if sector == SECTOR_ELECTRICITY:
            schema[vol.Required(CONF_ULO_ENABLED, default=False)] = bool

        return self.async_show_form(step_id=sector, data_schema=vol.Schema(schema))
