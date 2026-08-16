"""Tests for the Ontario Energy Board config flow."""

import aiohttp
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ontario_energy_board.const import (
    CONF_ENERGY_COMPANY,
    CONF_ULO_ENABLED,
    DOMAIN,
    ELECTRICITY_RATES_URL,
)

from .conftest import ELECTRICITY_COMPANY, NATURAL_GAS_COMPANY, build_config_entry


async def test_form_lists_companies_from_both_sectors(
    hass, mock_oeb, enable_custom_integrations
):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    options = result["data_schema"].schema[CONF_ENERGY_COMPANY].container
    assert ELECTRICITY_COMPANY in options
    assert NATURAL_GAS_COMPANY in options


async def test_creates_entry(hass, mock_oeb, enable_custom_integrations):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY, CONF_ULO_ENABLED: False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ELECTRICITY_COMPANY
    assert result["data"] == {
        CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY,
        CONF_ULO_ENABLED: False,
    }
    assert result["result"].unique_id == f"{ELECTRICITY_COMPANY} False"


async def test_same_company_with_different_rate_plans_is_allowed(
    hass, mock_oeb, enable_custom_integrations
):
    """A user may run TOU and ULO entries side by side for one company."""
    existing = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY, CONF_ULO_ENABLED: True},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{ELECTRICITY_COMPANY} True"


async def test_duplicate_entry_is_rejected(hass, mock_oeb, enable_custom_integrations):
    existing = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY, CONF_ULO_ENABLED: False},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_aborts_when_oeb_is_unreachable(
    hass, aioclient_mock, enable_custom_integrations
):
    aioclient_mock.get(ELECTRICITY_RATES_URL, exc=aiohttp.ClientError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
