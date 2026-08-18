"""Common functions used throughout various sections of the repo.

Fetching and parsing are kept separate on purpose: the ``parse_*`` functions
take a document as a string and can be tested against the fixtures in
``tests/fixtures/`` without any network or Home Assistant involvement.
"""

import re

import aiohttp
import defusedxml.ElementTree as ET

from .const import (
    CONF_ULO_ENABLED,
    ELECTRICITY_CLASS_KEY,
    ELECTRICITY_NAME_KEY,
    ELECTRICITY_RATE_UNIT_OF_MEASURE,
    ELECTRICITY_RATES_URL,
    ELECTRICITY_XML_ROOT_ELEMENT,
    NATURAL_GAS_CLASS_KEY,
    NATURAL_GAS_NAME_KEY,
    NATURAL_GAS_RATE_UNIT_OF_MEASURE,
    NATURAL_GAS_RATES_URL,
    NATURAL_GAS_XML_ROOT_ELEMENT,
    SECTOR_ELECTRICITY,
    XML_KEY_MAPPINGS,
    XML_KEY_MID_PEAK_RATE,
    XML_KEY_OFF_PEAK_RATE,
    XML_KEY_ON_PEAK_RATE,
    XML_KEY_ULO_MID_PEAK_RATE,
    XML_KEY_ULO_OFF_PEAK_RATE,
    XML_KEY_ULO_ON_PEAK_RATE,
    XML_KEY_ULO_OVERNIGHT_RATE,
)

# XML tags that carry no billing meaning and are never exposed as attributes.
IGNORED_XML_TAGS = frozenset(
    {ELECTRICITY_XML_ROOT_ELEMENT, NATURAL_GAS_XML_ROOT_ELEMENT, "Lic", "ExtID"}
)

# The sector is stored as a bracketed suffix on the company name. Anchoring the
# match matters: some distributors carry a sector word in their own name, such
# as "EPCOR Natural Gas Limited Partnership".
SECTOR_SUFFIX_PATTERN = re.compile(r"\[(Natural Gas|Electricity)\]$")


def format_company_name(company_name, rate_class, energy_sector) -> str:
    """Format the company name with rate class and energy sector.

    The result is the stored identity of a config entry, so this format cannot
    change without migrating existing entries.

    Args:
        company_name: The name of the company.
        rate_class: The rate class for the company.
        energy_sector: The energy sector (e.g., 'Electricity' or 'Natural Gas').

    Returns:
        The formatted company name string.
    """
    return f"{company_name} ({rate_class}) [{energy_sector}]"


def company_display_name(company_name: str) -> str:
    """Strip the sector suffix, which the device carries as its model instead.

    "Alectra (RESIDENTIAL) [Electricity]" becomes "Alectra (RESIDENTIAL)".
    """
    return SECTOR_SUFFIX_PATTERN.sub("", company_name).strip()


def effective_ulo_enabled(config_entry) -> bool:
    """Whether the entry is on the Ultra-Low Overnight plan.

    The plan is chosen during setup and can be corrected afterwards from the
    options, so the option wins where one has been set. Entries created before
    the options existed only carry the setup value.
    """
    return config_entry.options.get(
        CONF_ULO_ENABLED, config_entry.data[CONF_ULO_ENABLED]
    )


def energy_sector_from_company_name(company_name: str) -> str:
    """Extract the energy sector key from a formatted company name.

    Raises:
        ValueError: If the name does not carry a recognised sector suffix.
    """
    match = SECTOR_SUFFIX_PATTERN.search(company_name)

    if match is None:
        raise ValueError(f"Could not determine energy sector from '{company_name}'")

    return match.group(1).lower().replace(" ", "_")


def get_energy_sector_metadata(sector) -> dict:
    """Returns the respective energy sector metadata."""
    is_electricity = sector == SECTOR_ELECTRICITY

    return {
        "name": "Electricity" if is_electricity else "Natural Gas",
        "xml_url": ELECTRICITY_RATES_URL if is_electricity else NATURAL_GAS_RATES_URL,
        "xml_root_element": (
            ELECTRICITY_XML_ROOT_ELEMENT
            if is_electricity
            else NATURAL_GAS_XML_ROOT_ELEMENT
        ),
        "class_key": ELECTRICITY_CLASS_KEY if is_electricity else NATURAL_GAS_CLASS_KEY,
        "name_key": ELECTRICITY_NAME_KEY if is_electricity else NATURAL_GAS_NAME_KEY,
        "unit_of_measure": (
            ELECTRICITY_RATE_UNIT_OF_MEASURE
            if is_electricity
            else NATURAL_GAS_RATE_UNIT_OF_MEASURE
        ),
    }


async def async_fetch_rates_document(
    session: aiohttp.ClientSession, sector: str
) -> str:
    """Download the raw OEB rates document for an energy sector.

    SSL verification is disabled deliberately: the OEB host serves an incomplete
    certificate chain.
    """
    energy_sector_metadata = get_energy_sector_metadata(sector)

    async with session.get(energy_sector_metadata["xml_url"], ssl=False) as response:
        response.raise_for_status()
        return await response.text()


def parse_energy_companies(sector: str, content: str) -> list[str]:
    """Extract every company and rate class combination from a rates document."""
    energy_sector_metadata = get_energy_sector_metadata(sector)
    tree = ET.fromstring(content)

    return [
        format_company_name(
            company.find(energy_sector_metadata["name_key"]).text,
            company.find(energy_sector_metadata["class_key"]).text,
            energy_sector_metadata["name"],
        )
        for company in tree.findall(energy_sector_metadata["xml_root_element"])
    ]


def parse_energy_company_data(
    sector: str, content: str, desired_company: str
) -> dict | None:
    """Extract a single company's rates from a rates document.

    Returns None when the company is not present in the document.
    """
    energy_sector_metadata = get_energy_sector_metadata(sector)
    tree = ET.fromstring(content)

    for company in tree.findall(energy_sector_metadata["xml_root_element"]):
        current_company = format_company_name(
            company.find(energy_sector_metadata["name_key"]).text,
            company.find(energy_sector_metadata["class_key"]).text,
            energy_sector_metadata["name"],
        )

        if current_company != desired_company:
            continue

        company_data = {}

        if sector == SECTOR_ELECTRICITY:
            # Short aliases for the rates the sensor state is chosen from.
            for alias, xml_key in (
                ("on_peak_rate", XML_KEY_ON_PEAK_RATE),
                ("mid_peak_rate", XML_KEY_MID_PEAK_RATE),
                ("off_peak_rate", XML_KEY_OFF_PEAK_RATE),
                ("ulo_on_peak_rate", XML_KEY_ULO_ON_PEAK_RATE),
                ("ulo_mid_peak_rate", XML_KEY_ULO_MID_PEAK_RATE),
                ("ulo_off_peak_rate", XML_KEY_ULO_OFF_PEAK_RATE),
                ("ulo_overnight_rate", XML_KEY_ULO_OVERNIGHT_RATE),
            ):
                company_data[alias] = float(company.find(xml_key).text)

        for element in company.iter():
            if element.tag in IGNORED_XML_TAGS:
                continue

            if element.tag not in XML_KEY_MAPPINGS[sector]:
                continue

            if element.text is None:
                value = ""
            else:
                try:
                    value = float(element.text)
                except ValueError:
                    value = element.text

            company_data[XML_KEY_MAPPINGS[sector][element.tag]] = value

        return company_data

    return None


async def get_energy_companies(
    session: aiohttp.ClientSession, sector: str
) -> list[str]:
    """Sorted list of every company and rate class in one sector's document."""

    content = await async_fetch_rates_document(session, sector)

    return sorted(parse_energy_companies(sector, content))


async def get_energy_company_data(
    session: aiohttp.ClientSession, sector: str, desired_company: str
) -> dict | None:
    """Returns the respective data for an energy company."""

    content = await async_fetch_rates_document(session, sector)

    return parse_energy_company_data(sector, content, desired_company)
