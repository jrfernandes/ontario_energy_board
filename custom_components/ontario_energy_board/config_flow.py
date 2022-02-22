"""Config flow for Ontario Energy Board integration."""

import aiohttp
import xml.etree.ElementTree as ET
import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_ENERGY_COMPANY, DOMAIN, RATES_URL


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


class OntarioEnergyBoardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ontario Energy Board."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        companies_list = await get_energy_companies()

        if user_input is not None:
            energy_company = user_input[CONF_ENERGY_COMPANY]
            await self.async_set_unique_id(energy_company)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=energy_company,
                data={CONF_ENERGY_COMPANY: energy_company},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ENERGY_COMPANY): vol.In(companies_list)}
            ),
        )
