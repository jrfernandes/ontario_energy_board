"""Config flow for Ontario Energy Board integration."""

import aiohttp
import xml.etree.ElementTree as ET
import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_ENERGY_COMPANY,
    CONF_ULO_ENABLED,
    DOMAIN,
    ELECTRICITY_RATES_URL,
    ENERGY_SECTORS,
    NATURAL_GAS_RATES_URL,
)


async def get_energy_companies() -> list[str]:
    """Generates a list of all energy companies available
    in the XML document including the available classes.
    """

    all_companies = []

    for sector in ENERGY_SECTORS:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                ELECTRICITY_RATES_URL
                if sector == "electricity"
                else NATURAL_GAS_RATES_URL
            ) as response:
                content = await response.text()

        tree = ET.fromstring(content)

        session._base_url

        for company in tree.findall(
            "BillDataRow" if sector == "electricity" else "GasBillData"
        ):
            all_companies.append(
                "{company_name} ({company_class}) [{company_sector}]".format(
                    company_name=company.find("Dist").text,
                    company_class=company.find(
                        "Class" if sector == "electricity" else "SA"
                    ).text,
                    company_sector=sector.replace("_", " ").title(),
                )
            )

    all_companies.sort()

    return all_companies


class OntarioEnergyBoardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ontario Energy Board."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        companies_list = await get_energy_companies()

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
