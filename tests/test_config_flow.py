"""Tests for the Ontario Energy Board config flow."""

import aiohttp
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ontario_energy_board.const import (
    CONF_ENERGY_COMPANY,
    CONF_ULO_ENABLED,
    DOMAIN,
    ELECTRICITY_RATES_URL,
    NATURAL_GAS_RATES_URL,
)

from .conftest import ELECTRICITY_COMPANY, NATURAL_GAS_COMPANY, build_config_entry


async def _choose_sector(hass, sector):
    """Open the flow and pick a sector from the menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU

    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": sector}
    )


def _company_options(result):
    selector = result["data_schema"].schema[CONF_ENERGY_COMPANY]

    return selector.config["options"]


async def test_first_step_is_a_sector_menu(hass, mock_oeb, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["electricity", "natural_gas"]


async def test_electricity_list_is_filtered_and_asks_for_the_rate_plan(
    hass, mock_oeb, enable_custom_integrations
):
    result = await _choose_sector(hass, "electricity")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "electricity"

    values = [option["value"] for option in _company_options(result)]
    assert ELECTRICITY_COMPANY in values
    assert NATURAL_GAS_COMPANY not in values
    assert all(value.endswith("[Electricity]") for value in values)

    # The rate plan is asked here, now that the sector is known.
    assert CONF_ULO_ENABLED in result["data_schema"].schema


async def test_natural_gas_list_is_filtered_and_asks_nothing_further(
    hass, mock_oeb, enable_custom_integrations
):
    result = await _choose_sector(hass, "natural_gas")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "natural_gas"

    values = [option["value"] for option in _company_options(result)]
    assert NATURAL_GAS_COMPANY in values
    assert ELECTRICITY_COMPANY not in values

    # Gas has no peak periods, so Ultra-Low Overnight is meaningless for it.
    assert CONF_ULO_ENABLED not in result["data_schema"].schema


async def test_labels_drop_the_now_redundant_sector_suffix(
    hass, mock_oeb, enable_custom_integrations
):
    """The stored value identifies the entry, so only the label is shortened."""
    result = await _choose_sector(hass, "electricity")

    option = next(
        option
        for option in _company_options(result)
        if option["value"] == ELECTRICITY_COMPANY
    )

    assert option["value"] == ELECTRICITY_COMPANY
    assert option["label"] == (
        "Alectra Utilities Corporation-Brampton Rate Zone (RESIDENTIAL)"
    )


async def test_creates_an_electricity_entry(hass, mock_oeb, enable_custom_integrations):
    result = await _choose_sector(hass, "electricity")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY, CONF_ULO_ENABLED: True},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ELECTRICITY_COMPANY
    assert result["data"] == {
        CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY,
        CONF_ULO_ENABLED: True,
    }
    assert result["result"].unique_id == f"{ELECTRICITY_COMPANY} True"


async def test_natural_gas_keeps_the_established_unique_id(
    hass, mock_oeb, enable_custom_integrations
):
    """Gas is never asked about the plan, but still records it as False.

    Its unique id is "<company> False", the same as an entry created before the
    sector was chosen first. Dropping the value would orphan existing entries.
    """
    result = await _choose_sector(hass, "natural_gas")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: NATURAL_GAS_COMPANY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{NATURAL_GAS_COMPANY} False"
    assert result["data"][CONF_ULO_ENABLED] is False


async def test_same_company_with_different_rate_plans_is_allowed(
    hass, mock_oeb, enable_custom_integrations
):
    """A user may run Time-of-Use and ULO entries side by side."""
    build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False).add_to_hass(hass)

    result = await _choose_sector(hass, "electricity")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY, CONF_ULO_ENABLED: True},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{ELECTRICITY_COMPANY} True"


async def test_duplicate_entry_is_rejected(hass, mock_oeb, enable_custom_integrations):
    build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False).add_to_hass(hass)

    result = await _choose_sector(hass, "electricity")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY, CONF_ULO_ENABLED: False},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_duplicate_gas_entry_is_rejected(
    hass, mock_oeb, enable_custom_integrations
):
    build_config_entry(NATURAL_GAS_COMPANY, ulo_enabled=False).add_to_hass(hass)

    result = await _choose_sector(hass, "natural_gas")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: NATURAL_GAS_COMPANY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_aborts_when_the_sectors_document_is_unreachable(
    hass, aioclient_mock, enable_custom_integrations
):
    aioclient_mock.get(ELECTRICITY_RATES_URL, exc=aiohttp.ClientError)

    result = await _choose_sector(hass, "electricity")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_only_the_chosen_sectors_document_is_downloaded(
    hass, mock_oeb, enable_custom_integrations
):
    """Choosing the sector first halves the setup traffic."""
    await _choose_sector(hass, "natural_gas")

    requested = {str(call[1]) for call in mock_oeb.mock_calls}

    assert requested == {NATURAL_GAS_RATES_URL}
    assert ELECTRICITY_RATES_URL not in requested
