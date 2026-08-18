"""Tests for the Ontario Energy Board config flow."""

import aiohttp
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

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
    # Neither the company nor the plan identifies an entry, since both can
    # change; the entry id does that instead.
    assert result["result"].unique_id is None


async def test_natural_gas_still_records_the_plan(
    hass, mock_oeb, enable_custom_integrations
):
    """Gas is never asked, but the value is still stored for the coordinator."""
    result = await _choose_sector(hass, "natural_gas")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: NATURAL_GAS_COMPANY}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
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


async def test_options_flow_changes_the_rate_plan(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    entry = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({})[CONF_ULO_ENABLED] is False

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_ULO_ENABLED: True}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_ULO_ENABLED] is True
    # The value chosen at setup is left alone; the option overrides it.
    assert entry.data[CONF_ULO_ENABLED] is False


async def test_options_flow_is_not_offered_for_natural_gas(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    entry = build_config_entry(NATURAL_GAS_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_rate_plan"


async def test_a_plan_changed_from_the_options_still_blocks_a_duplicate(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """The unique id records the plan chosen at setup, not the current one.

    An entry set up on Time-of-Use and later corrected to ULO keeps the unique
    id "<company> False". Adding a ULO entry for the same company would take
    the still-free "<company> True", so the check has to compare current plans.
    """
    entry = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    options = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        options["flow_id"], {CONF_ULO_ENABLED: True}
    )
    await hass.async_block_till_done()

    result = await _choose_sector(hass, "electricity")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY, CONF_ULO_ENABLED: True},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_the_original_plan_can_be_added_again_after_a_change(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """An entry moved to ULO leaves Time-of-Use genuinely free again.

    While the unique id encoded the plan chosen at setup, it kept occupying
    "<company> False" after the plan changed, and blocked this. Entries carry
    no unique id now, so the check reflects what is actually configured.
    """
    entry = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    options = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        options["flow_id"], {CONF_ULO_ENABLED: True}
    )
    await hass.async_block_till_done()

    result = await _choose_sector(hass, "electricity")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY, CONF_ULO_ENABLED: False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_repoints_a_renamed_company(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """The recovery path for a distributor that has been renamed or merged."""
    entry = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    other = "Algoma Power Inc. (RESIDENTIAL R1) [Electricity]"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: other}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_ENERGY_COMPANY] == other
    assert entry.title == other


async def test_reconfigure_preserves_the_entities(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """Re-pointing keeps the history; deleting and re-adding would not."""
    entry = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    before = {e.entity_id: e.unique_id for e in registry.entities.values()}

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ENERGY_COMPANY: "Algoma Power Inc. (RESIDENTIAL R1) [Electricity]"},
    )
    await hass.async_block_till_done()

    after = {e.entity_id: e.unique_id for e in registry.entities.values()}

    assert after == before


async def test_reconfigure_offers_the_closest_surviving_name(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """The likely new name is pre-selected, but the user confirms it.

    Rate zones carry near-identical names and different delivery charges, so
    choosing automatically could quietly bill against another city's rates.
    """
    entry = build_config_entry(
        "Alectra Utilities Corporation-For Brampton Main Rate Zone "
        "(RESIDENTIAL) [Electricity]"
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["data_schema"]({})[CONF_ENERGY_COMPANY] == ELECTRICITY_COMPANY


async def test_reconfigure_stays_within_the_current_sector(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """A gas entry cannot be re-pointed at an electricity company."""
    entry = build_config_entry(NATURAL_GAS_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    values = [option["value"] for option in _company_options(result)]

    assert NATURAL_GAS_COMPANY in values
    assert ELECTRICITY_COMPANY not in values


async def test_reconfigure_refuses_a_company_another_entry_already_has(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """Re-pointing must not create the duplicate that adding would refuse."""
    other = "Algoma Power Inc. (RESIDENTIAL R1) [Electricity]"

    existing = build_config_entry(other, ulo_enabled=False)
    existing.add_to_hass(hass)
    entry = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: other}
    )

    # Reported on the form, so the user keeps their place.
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "already_configured"}
    assert entry.data[CONF_ENERGY_COMPANY] == ELECTRICITY_COMPANY


async def test_reconfigure_allows_keeping_the_same_company(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """An entry is not a duplicate of itself."""
    entry = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
