"""Tests for setup, unload and config entry migration."""

import aiohttp
from homeassistant.config_entries import ConfigEntryState
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

    assert entry.version == 2
    assert entry.data[CONF_ULO_ENABLED] is False
    assert entry.state is ConfigEntryState.LOADED
