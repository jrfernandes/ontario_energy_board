"""Config flow for Ontario Energy Board integration."""

import voluptuous as vol
from homeassistant import config_entries

from .common import get_energy_companies

from .const import (
    CONF_ENERGY_COMPANY,
    CONF_ULO_ENABLED,
    DOMAIN,
)


class OntarioEnergyBoardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ontario Energy Board."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        companies_list = await get_energy_companies()

        """Run a check to make sure the same device isn't being setup multiple times"""
        if user_input is not None:
            energy_company = user_input[CONF_ENERGY_COMPANY]
            ulo_enabled = user_input[CONF_ULO_ENABLED]

            await self.async_set_unique_id(energy_company)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=energy_company,
                data={
                    CONF_ENERGY_COMPANY: energy_company,
                    CONF_ULO_ENABLED: ulo_enabled,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENERGY_COMPANY): vol.In(companies_list),
                    vol.Required(CONF_ULO_ENABLED): bool,
                }
            ),
        )
