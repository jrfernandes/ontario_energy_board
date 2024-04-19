"""Common functions used throught various sections of the repo."""

import aiohttp
import xml.etree.ElementTree as ET
from .const import (
    ELECTRICITY_CLASS_KEY,
    ELECTRICITY_NAME_KEY,
    ELECTRICITY_RATES_URL,
    ENERGY_SECTORS,
    NATURAL_GAS_CLASS_KEY,
    NATURAL_GAS_NAME_KEY,
    NATURAL_GAS_RATES_URL,
    ELECTRICITY_XML_ROOT_ELEMENT,
    NATURAL_GAS_XML_ROOT_ELEMENT,
    XML_KEY_MAPPINGS,
    XML_KEY_MID_PEAK_RATE,
    XML_KEY_OFF_PEAK_RATE,
    XML_KEY_ON_PEAK_RATE,
    XML_KEY_ULO_MID_PEAK_RATE,
    XML_KEY_ULO_OFF_PEAK_RATE,
    XML_KEY_ULO_ON_PEAK_RATE,
    XML_KEY_ULO_OVERNIGHT_RATE,
)


def format_company_name(company_name, rate_class, energy_sector) -> str:
    return "{company_name} ({company_class}) [{company_sector}]".format(
        company_name=company_name,
        company_class=rate_class,
        company_sector=energy_sector,
    )


def get_energy_sector_metadata(sector) -> str:
    """Returns the respective energy sector metadata."""
    return {
        "xml_url": (
            ELECTRICITY_RATES_URL if sector == "electricity" else NATURAL_GAS_RATES_URL
        ),
        "xml_root_element": (
            ELECTRICITY_XML_ROOT_ELEMENT
            if sector == "electricity"
            else NATURAL_GAS_XML_ROOT_ELEMENT
        ),
        "class_key": (
            ELECTRICITY_CLASS_KEY if sector == "electricity" else NATURAL_GAS_CLASS_KEY
        ),
        "name_key": (
            ELECTRICITY_NAME_KEY if sector == "electricity" else NATURAL_GAS_NAME_KEY
        ),
    }


async def get_energy_companies(sort=True) -> list[str]:
    """Generates a list of all energy companies available
    in the XML document including the available classes.
    """

    all_companies = []

    for sector in ENERGY_SECTORS:
        content = ""
        energy_sector_metadata = get_energy_sector_metadata(sector)
        energy_sector_companies = []

        async with aiohttp.ClientSession() as session:
            async with session.get(energy_sector_metadata["xml_url"]) as response:
                content = await response.text()

        tree = ET.fromstring(content)

        for company in tree.findall(energy_sector_metadata["xml_root_element"]):
            energy_sector_companies.append(
                format_company_name(
                    company.find(energy_sector_metadata["name_key"]).text,
                    company.find(energy_sector_metadata["class_key"]).text,
                    sector.replace("_", " ").title(),
                )
            )

        if sort:
            energy_sector_companies.sort()

        all_companies = list(set(all_companies + energy_sector_companies))

    return all_companies


async def get_energy_company_data(sector, company) -> dict[str, any] | None:
    """Returns the respective data for an energy company."""

    company_data = {}
    content = ""
    energy_sector_metadata = get_energy_sector_metadata(sector)

    async with aiohttp.ClientSession() as session:
        async with session.get(energy_sector_metadata["xml_url"]) as response:
            content = await response.text()

    tree = ET.fromstring(content)

    for company in tree.findall(energy_sector_metadata["xml_root_element"]):
        current_company = format_company_name(
            company.find(energy_sector_metadata["name_key"]).text,
            company.find(energy_sector_metadata["class_key"]).text,
            sector,
        )

        if current_company == company:
            if sector == "electricity":
                company_data["on_peak_rate"] = float(
                    company.find(XML_KEY_ON_PEAK_RATE).text
                )
                company_data["mid_peak_rate"] = float(
                    company.find(XML_KEY_MID_PEAK_RATE).text
                )
                company_data["off_peak_rate"] = float(
                    company.find(XML_KEY_OFF_PEAK_RATE).text
                )
                company_data["ulo_on_peak_rate"] = float(
                    company.find(XML_KEY_ULO_ON_PEAK_RATE).text
                )
                company_data["ulo_mid_peak_rate"] = float(
                    company.find(XML_KEY_ULO_MID_PEAK_RATE).text
                )
                company_data["ulo_off_peak_rate"] = float(
                    company.find(XML_KEY_ULO_OFF_PEAK_RATE).text
                )
                company_data["ulo_overnight_rate"] = float(
                    company.find(XML_KEY_ULO_OVERNIGHT_RATE).text
                )

            for element in company.iter():
                if element.tag in ["BillDataRow", "GasBillData", "Lic", "ExtID"]:
                    continue

                value = element.text

                if element.text is not None:
                    try:
                        value = float(value)
                    except ValueError:
                        value = element.text
                else:
                    value = ""

                if element.tag in XML_KEY_MAPPINGS[sector]:
                    company_data[XML_KEY_MAPPINGS[sector][element.tag]] = value

            return company_data

    return None
