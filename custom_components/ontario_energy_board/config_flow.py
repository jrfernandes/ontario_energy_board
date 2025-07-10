"""Config flow for Ontario Energy Board integration."""

import voluptuous as vol

from homeassistant import config_entries

from .common import get_energy_companies
from .const import CONF_ENERGY_COMPANY, CONF_ULO_ENABLED, DOMAIN


class OntarioEnergyBoardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ontario Energy Board."""

    VERSION = 2

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Handle the initial step of the config flow for Ontario Energy Board.

        Show a form to select the energy company and ULO option, or create the entry if user input is provided.

        Args:
            user_input (dict | None): The user input from the form, or None if showing the form.

        Returns:
            ConfigFlowResult: The result of the config flow step.
        """
        companies_list = await get_energy_companies()

        if user_input is not None:
            energy_company = user_input[CONF_ENERGY_COMPANY]
            ulo_enabled = user_input[CONF_ULO_ENABLED]

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
