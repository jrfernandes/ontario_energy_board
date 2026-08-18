"""Tests for fetching and parsing the OEB rates documents."""

from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest

from custom_components.ontario_energy_board.common import (
    energy_sector_from_company_name,
    format_company_name,
    get_energy_companies,
    get_energy_company_data,
    get_energy_sector_metadata,
    parse_energy_companies,
    parse_energy_company_data,
)
from custom_components.ontario_energy_board.const import (
    ELECTRICITY_RATE_UNIT_OF_MEASURE,
    NATURAL_GAS_RATE_UNIT_OF_MEASURE,
    SECTOR_ELECTRICITY,
    SECTOR_NATURAL_GAS,
)

from .conftest import ELECTRICITY_COMPANY, NATURAL_GAS_COMPANY


def test_format_company_name():
    assert (
        format_company_name("Alectra", "RESIDENTIAL", "Electricity")
        == "Alectra (RESIDENTIAL) [Electricity]"
    )


@pytest.mark.parametrize(
    "company_name, expected",
    [
        (ELECTRICITY_COMPANY, SECTOR_ELECTRICITY),
        (NATURAL_GAS_COMPANY, SECTOR_NATURAL_GAS),
        # Distributors whose own name contains a sector word must still resolve
        # by the bracketed suffix, not by the first word found.
        (
            "EPCOR Natural Gas Limited Partnership (Aylmer) [Natural Gas]",
            SECTOR_NATURAL_GAS,
        ),
        (
            "EPCOR Electricity Distribution Ontario Inc. (RESIDENTIAL) [Electricity]",
            SECTOR_ELECTRICITY,
        ),
        (
            "Oakville Hydro Electricity Distribution Inc. (All) [Natural Gas]",
            SECTOR_NATURAL_GAS,
        ),
    ],
)
def test_energy_sector_from_company_name(company_name, expected):
    assert energy_sector_from_company_name(company_name) == expected


def test_energy_sector_from_company_name_rejects_unknown():
    with pytest.raises(ValueError):
        energy_sector_from_company_name("Some Utility (RESIDENTIAL)")


@pytest.mark.parametrize(
    "sector, expected_unit",
    [
        (SECTOR_ELECTRICITY, ELECTRICITY_RATE_UNIT_OF_MEASURE),
        (SECTOR_NATURAL_GAS, NATURAL_GAS_RATE_UNIT_OF_MEASURE),
    ],
)
def test_get_energy_sector_metadata(sector, expected_unit):
    assert get_energy_sector_metadata(sector)["unit_of_measure"] == expected_unit


def test_parse_energy_companies_electricity(electricity_document):
    companies = parse_energy_companies(SECTOR_ELECTRICITY, electricity_document)

    assert ELECTRICITY_COMPANY in companies
    assert all(name.endswith("[Electricity]") for name in companies)


def test_parse_energy_companies_natural_gas(natural_gas_document):
    companies = parse_energy_companies(SECTOR_NATURAL_GAS, natural_gas_document)

    assert NATURAL_GAS_COMPANY in companies
    assert all(name.endswith("[Natural Gas]") for name in companies)


def test_parse_electricity_company_data(electricity_document):
    data = parse_energy_company_data(
        SECTOR_ELECTRICITY, electricity_document, ELECTRICITY_COMPANY
    )

    assert data is not None

    # Short aliases used for the documented attributes.
    assert data["on_peak_rate"] == pytest.approx(0.203)
    assert data["ulo_overnight_rate"] == pytest.approx(0.039)

    # Long names from XML_KEY_MAPPINGS, which is what the sensor state reads.
    assert data["time_of_use_on_peak_price"] == pytest.approx(0.203)
    assert data["ultra_low_overnight_overnight_rate"] == pytest.approx(0.039)

    # Text values stay as strings, numbers are coerced to float.
    assert (
        data["distributor_name"] == "Alectra Utilities Corporation-Brampton Rate Zone"
    )
    assert data["rate_class"] == "RESIDENTIAL"
    assert isinstance(data["tier_threshold"], float)


def test_parse_natural_gas_company_data(natural_gas_document):
    data = parse_energy_company_data(
        SECTOR_NATURAL_GAS, natural_gas_document, NATURAL_GAS_COMPANY
    )

    assert data is not None
    assert data["gas_supply_charge"] == pytest.approx(0.103025)
    assert data["distributor_name"] == "Enbridge Gas"
    assert data["service_area"] == "All"

    # Electricity-only aliases must not leak into gas data.
    assert "on_peak_rate" not in data


def test_parse_company_data_ignores_meaningless_tags(natural_gas_document):
    """Lic and ExtID carry no billing meaning and are never exposed."""
    data = parse_energy_company_data(
        SECTOR_NATURAL_GAS, natural_gas_document, NATURAL_GAS_COMPANY
    )

    assert "Lic" not in data
    assert "ExtID" not in data


def test_parse_company_data_returns_none_for_unknown_company(electricity_document):
    assert (
        parse_energy_company_data(
            SECTOR_ELECTRICITY,
            electricity_document,
            "Not A Real Utility (X) [Electricity]",
        )
        is None
    )


@pytest.mark.parametrize(
    "sector, expected, unexpected",
    [
        (SECTOR_ELECTRICITY, ELECTRICITY_COMPANY, NATURAL_GAS_COMPANY),
        (SECTOR_NATURAL_GAS, NATURAL_GAS_COMPANY, ELECTRICITY_COMPANY),
    ],
)
async def test_get_energy_companies_is_scoped_to_one_sector(
    hass, mock_oeb, sector, expected, unexpected
):
    companies = await get_energy_companies(async_get_clientsession(hass), sector)

    assert expected in companies
    assert unexpected not in companies
    assert companies == sorted(companies)


async def test_get_energy_company_data_fetches_selected_sector(hass, mock_oeb):
    data = await get_energy_company_data(
        async_get_clientsession(hass), SECTOR_ELECTRICITY, ELECTRICITY_COMPANY
    )

    assert data is not None
    assert (
        data["distributor_name"] == "Alectra Utilities Corporation-Brampton Rate Zone"
    )
