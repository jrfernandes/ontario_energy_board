"""Tests for setup, unload and config entry migration."""

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ontario_energy_board.const import (
    CONF_ENERGY_COMPANY,
    CONF_ULO_ENABLED,
    DOMAIN,
    ELECTRICITY_RATES_URL,
)

from .conftest import ELECTRICITY_COMPANY, build_config_entry


async def test_setup_and_unload(hass, init_integration):
    entry = await init_integration()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_setup_retries_when_oeb_is_unreachable(
    hass, aioclient_mock, ontario_timezone, enable_custom_integrations
):
    aioclient_mock.get(ELECTRICITY_RATES_URL, exc=aiohttp.ClientError)

    entry = build_config_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_two_entries_keep_independent_data(hass, init_integration):
    """Coordinator state must not be shared between entries."""
    electricity = await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)
    gas = await init_integration("Enbridge Gas (All) [Natural Gas]")

    electricity_coordinator = hass.data[DOMAIN][electricity.entry_id]
    gas_coordinator = hass.data[DOMAIN][gas.entry_id]

    assert electricity_coordinator.energy_sector == "electricity"
    assert gas_coordinator.energy_sector == "natural_gas"
    assert electricity_coordinator.company_data != gas_coordinator.company_data


async def test_migration_from_version_1(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """Version 1 entries predate the ULO option and must gain it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=ELECTRICITY_COMPANY,
        unique_id=ELECTRICITY_COMPANY,
        version=1,
        data={CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3
    assert entry.data[CONF_ULO_ENABLED] is False
    assert entry.state is ConfigEntryState.LOADED


async def test_a_vanished_company_is_a_permanent_error_not_a_retry(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """Retrying cannot bring a renamed distributor back.

    A network failure is worth retrying; a company that has left the document
    is not, and saying so is what surfaces it to the user instead of leaving
    the entry retrying quietly forever.
    """
    entry = build_config_entry("Utility That Left The Feed (RESIDENTIAL) [Electricity]")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_a_vanished_company_raises_a_repair(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    entry = build_config_entry("Utility That Left The Feed (RESIDENTIAL) [Electricity]")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"company_missing_{entry.entry_id}"
    )

    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR


async def test_the_repair_suggests_the_likely_new_name(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """A rename usually leaves most of the name intact."""
    entry = build_config_entry(
        "Alectra Utilities Corporation-For Brampton Main Rate Zone "
        "(RESIDENTIAL) [Electricity]"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"company_missing_{entry.entry_id}"
    )

    assert issue.translation_key == "company_suggestion"
    assert issue.translation_placeholders["suggestion"] == ELECTRICITY_COMPANY


async def test_the_repair_clears_once_the_company_resolves(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    entry = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"company_missing_{entry.entry_id}")
        is None
    )


async def test_migration_re_keys_entities_without_losing_them(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """A version 2 entry's entities keep their entity ids, and their history.

    Version 2 keyed everything on "<company> <plan>". Renaming a unique id in
    the registry keeps the row, so the entity id the user already has in
    dashboards and the recorder survives.
    """
    legacy_unique_id = f"{ELECTRICITY_COMPANY} False"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=ELECTRICITY_COMPANY,
        unique_id=legacy_unique_id,
        version=2,
        data={
            CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY,
            CONF_ULO_ENABLED: False,
        },
    )
    entry.add_to_hass(hass)

    registry = er.async_get(hass)
    # The single sensor that predates the device layout, plus one of the
    # entities added alongside it.
    rate = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        legacy_unique_id,
        suggested_object_id="my_rate",
        config_entry=entry,
    )
    peak = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{legacy_unique_id}_active_peak",
        suggested_object_id="my_peak",
        config_entry=entry,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3
    assert entry.unique_id is None

    # Same rows, same entity ids.
    assert registry.async_get(rate.entity_id).unique_id == (
        f"{entry.entry_id}_current_rate"
    )
    assert registry.async_get(peak.entity_id).unique_id == (
        f"{entry.entry_id}_active_peak"
    )

    # And they are live, not orphaned duplicates.
    assert hass.states.get("sensor.my_rate") is not None
    assert hass.states.get("sensor.my_peak") is not None
    assert not [
        e
        for e in registry.entities.values()
        if e.unique_id.startswith(legacy_unique_id)
    ]


async def test_migration_from_version_1_runs_both_steps(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """A version 1 entry gains the rate plan and then the new identity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=ELECTRICITY_COMPANY,
        unique_id=ELECTRICITY_COMPANY,
        version=1,
        data={CONF_ENERGY_COMPANY: ELECTRICITY_COMPANY},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3
    assert entry.unique_id is None
    assert entry.data[CONF_ULO_ENABLED] is False
    assert entry.state is ConfigEntryState.LOADED


async def test_removing_an_entry_clears_its_repair(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """Repairs are not tied to a config entry, so they must be cleared by hand.

    Otherwise deleting an entry leaves a notice about a company the user no
    longer has configured.
    """
    entry = build_config_entry("Utility That Left The Feed (RESIDENTIAL) [Electricity]")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    issue_id = f"company_missing_{entry.entry_id}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_the_document_is_downloaded_once_when_a_company_is_missing(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """The suggestion is parsed from the document already fetched."""
    entry = build_config_entry("Utility That Left The Feed (RESIDENTIAL) [Electricity]")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_oeb.mock_calls) == 1
