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


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_form_lists_companies_from_both_sectors(
    hass, mock_oeb, enable_custom_integrations
):
    result = await _start(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    options = result["data_schema"].schema[CONF_ENERGY_COMPANY].container
    assert ELECTRICITY_COMPANY in options
    assert NATURAL_GAS_COMPANY in options

    # The rate plan is asked separately, once the sector is known.
    assert CONF_ULO_ENABLED not in result["data_schema"].schema


async def test_electricity_is_asked_for_its_rate_plan(
    hass, mock_oeb, enable_custom_integrations
):
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "rate_plan"
    assert result["description_placeholders"] == {"energy_company": ELECTRICITY_COMPANY}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ULO_ENABLED: True}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ELECTRICITY_COMPANY
    assert result["data"] == {
        CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY,
        CONF_ULO_ENABLED: True,
    }
    assert result["result"].unique_id == f"{ELECTRICITY_COMPANY} True"


async def test_natural_gas_skips_the_rate_plan_step(
    hass, mock_oeb, enable_custom_integrations
):
    """Gas has no peak periods, so Ultra-Low Overnight is meaningless for it."""
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: NATURAL_GAS_COMPANY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NATURAL_GAS_COMPANY


async def test_natural_gas_keeps_the_established_unique_id(
    hass, mock_oeb, enable_custom_integrations
):
    """Gas entries still record the plan, so their unique id is unchanged.

    A gas entry created before the rate plan moved to its own step is keyed on
    "<company> False"; skipping the step must not change that, or existing
    entries would be orphaned.
    """
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: NATURAL_GAS_COMPANY}
    )

    assert result["result"].unique_id == f"{NATURAL_GAS_COMPANY} False"
    assert result["data"][CONF_ULO_ENABLED] is False


async def test_same_company_with_different_rate_plans_is_allowed(
    hass, mock_oeb, enable_custom_integrations
):
    """A user may run Time-of-Use and ULO entries side by side."""
    build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False).add_to_hass(hass)

    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ULO_ENABLED: True}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{ELECTRICITY_COMPANY} True"


async def test_duplicate_entry_is_rejected(hass, mock_oeb, enable_custom_integrations):
    build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False).add_to_hass(hass)

    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ULO_ENABLED: False}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_duplicate_gas_entry_is_rejected(
    hass, mock_oeb, enable_custom_integrations
):
    """The gas path creates the entry directly, so it checks for itself."""
    build_config_entry(NATURAL_GAS_COMPANY, ulo_enabled=False).add_to_hass(hass)

    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: NATURAL_GAS_COMPANY}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_aborts_when_oeb_is_unreachable(
    hass, aioclient_mock, enable_custom_integrations
):
    aioclient_mock.get(ELECTRICITY_RATES_URL, exc=aiohttp.ClientError)

    result = await _start(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_the_documents_are_downloaded_once_per_attempt(
    hass, mock_oeb, enable_custom_integrations
):
    """Submitting is validated against the schema already shown.

    There is no need to rebuild the company list, so the feeds are not fetched
    a second time.
    """
    result = await _start(hass)
    calls_after_form = len(mock_oeb.mock_calls)

    # Stop at the rate plan form, so nothing the coordinator does on setup is
    # counted here.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY}
    )

    assert result["step_id"] == "rate_plan"
    assert len(mock_oeb.mock_calls) == calls_after_form
