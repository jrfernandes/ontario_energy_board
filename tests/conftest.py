"""Shared fixtures for the Ontario Energy Board tests.

The fixtures here deliberately avoid touching the network: every OEB request is
served from the documents in ``tests/fixtures/``, which are trimmed snapshots of
the live feeds. ``pytest-socket`` (bundled with pytest-homeassistant-custom-
component) blocks real sockets, so a missed mock fails loudly.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ontario_energy_board.const import (
    CONF_ENERGY_COMPANY,
    CONF_ULO_ENABLED,
    DOMAIN,
    ELECTRICITY_RATES_URL,
    NATURAL_GAS_RATES_URL,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"

TIME_ZONE = "America/Toronto"

ELECTRICITY_COMPANY = (
    "Alectra Utilities Corporation-Brampton Rate Zone (RESIDENTIAL) [Electricity]"
)
NATURAL_GAS_COMPANY = "Enbridge Gas (All) [Natural Gas]"


def load_rates_document(name: str) -> str:
    """Read one of the captured OEB rates documents."""
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def electricity_document() -> str:
    return load_rates_document("BillData.xml")


@pytest.fixture
def natural_gas_document() -> str:
    return load_rates_document("GasBillData.xml")


@pytest.fixture
def mock_oeb(aioclient_mock):
    """Serve both OEB rates documents from the local fixtures."""
    aioclient_mock.get(ELECTRICITY_RATES_URL, text=load_rates_document("BillData.xml"))
    aioclient_mock.get(
        NATURAL_GAS_RATES_URL, text=load_rates_document("GasBillData.xml")
    )
    return aioclient_mock


@pytest.fixture
def enable_all_entities():
    """Register the diagnostic entities that ship disabled by default.

    Home Assistant core has an equivalent fixture; pytest-homeassistant-custom-
    component does not re-export it.
    """
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        property(lambda self: True),
    ):
        yield


@pytest.fixture
async def ontario_timezone(hass):
    """Run the test in the timezone the integration actually cares about."""
    await hass.config.async_set_time_zone(TIME_ZONE)
    return TIME_ZONE


def build_config_entry(
    energy_company: str = ELECTRICITY_COMPANY,
    ulo_enabled: bool = False,
) -> MockConfigEntry:
    """Create a config entry matching what the config flow produces."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=energy_company,
        unique_id=f"{energy_company} {ulo_enabled}",
        version=2,
        data={
            CONF_ENERGY_COMPANY: energy_company,
            CONF_ULO_ENABLED: ulo_enabled,
        },
    )


@pytest.fixture
async def init_integration(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """Set up the integration and return a factory for further entries."""

    async def _setup(
        energy_company: str = ELECTRICITY_COMPANY,
        ulo_enabled: bool = False,
    ) -> MockConfigEntry:
        entry = build_config_entry(energy_company, ulo_enabled)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry

    return _setup
