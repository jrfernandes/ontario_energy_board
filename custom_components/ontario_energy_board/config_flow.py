"""Config flow for Ontario Energy Board integration."""

import logging
from typing import Any, Final

import aiohttp
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .common import (
    closest_company,
    company_display_name,
    effective_ulo_enabled,
    energy_sector_from_company_name,
    get_energy_companies,
)
from .const import (
    CONF_ENERGY_COMPANY,
    CONF_ULO_ENABLED,
    DOMAIN,
    SECTOR_ELECTRICITY,
    SECTOR_NATURAL_GAS,
)

_LOGGER: Final = logging.getLogger(__name__)


def _company_selector(companies: list[str]) -> SelectSelector:
    """A searchable list of companies.

    The stored value keeps the sector suffix, since it identifies the sector;
    the label drops it, because the sector is already known by this point.
    """
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=company, label=company_display_name(company))
                for company in companies
            ],
            mode=SelectSelectorMode.DROPDOWN,
            sort=False,
        )
    )


class OntarioEnergyBoardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ontario Energy Board."""

    VERSION = 3

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

            # Entries carry no unique id: the company and the rate plan can
            # both change, so neither can identify an entry for its lifetime.
            # Duplicates are judged on what an entry currently holds instead.
            if any(
                entry.data[CONF_ENERGY_COMPANY] == energy_company
                and effective_ulo_enabled(entry) == ulo_enabled
                for entry in self._async_current_entries()
            ):
                return self.async_abort(reason="already_configured")

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
            vol.Required(CONF_ENERGY_COMPANY): _company_selector(companies)
        }

        if sector == SECTOR_ELECTRICITY:
            schema[vol.Required(CONF_ULO_ENABLED, default=False)] = bool

        return self.async_show_form(step_id=sector, data_schema=vol.Schema(schema))

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Point an existing entry at a different company.

        Distributors are renamed and merged, which leaves an entry naming a
        company the Ontario Energy Board no longer publishes. Re-pointing it
        keeps the entry, and with it every entity id and its history; deleting
        and re-adding would not.
        """
        entry = self._get_reconfigure_entry()
        current = entry.data[CONF_ENERGY_COMPANY]
        sector = energy_sector_from_company_name(current)

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                title=user_input[CONF_ENERGY_COMPANY],
                data_updates={CONF_ENERGY_COMPANY: user_input[CONF_ENERGY_COMPANY]},
            )

        try:
            companies = await get_energy_companies(
                async_get_clientsession(self.hass), sector
            )
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.exception("Failed to download the %s rates document", sector)
            return self.async_abort(reason="cannot_connect")

        # Offered as a default, never applied on the user's behalf: rate zones
        # carry near-identical names and genuinely different delivery charges.
        suggested = (
            current if current in companies else closest_company(current, companies)
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENERGY_COMPANY, default=suggested
                    ): _company_selector(companies)
                }
            ),
            description_placeholders={"energy_company": current},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Allow the rate plan to be corrected after setup."""
        return OntarioEnergyBoardOptionsFlow()


class OntarioEnergyBoardOptionsFlow(config_entries.OptionsFlow):
    """Change which rate plan an existing entry is billed on.

    This is configuration rather than control: it records the plan the utility
    bills the account on, which Home Assistant cannot change.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        energy_company = self.config_entry.data[CONF_ENERGY_COMPANY]

        if energy_sector_from_company_name(energy_company) != SECTOR_ELECTRICITY:
            # Gas has no peak periods, so there is no plan to choose.
            return self.async_abort(reason="no_rate_plan")

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ULO_ENABLED,
                        default=effective_ulo_enabled(self.config_entry),
                    ): bool
                }
            ),
            description_placeholders={"energy_company": energy_company},
        )
