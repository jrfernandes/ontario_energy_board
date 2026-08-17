"""Tests for the distribution rate protection flag."""

from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from homeassistant.helpers import entity_registry as er

from .conftest import ELECTRICITY_COMPANY, NATURAL_GAS_COMPANY

ONTARIO = ZoneInfo("America/Toronto")

RATE_PROTECTION = (
    "binary_sensor.alectra_utilities_corporation_brampton_rate_zone_residential_"
    "distribution_rate_protection"
)


def ontario_moment(year, month, day, hour):
    return datetime(year, month, day, hour, tzinfo=ONTARIO)


async def test_rate_protection_ships_as_a_disabled_diagnostic(hass, init_integration):
    """The OEB publishes it as 0 or 1, so it is a flag rather than a rate."""
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    entry = er.async_get(hass).async_get(RATE_PROTECTION)

    assert entry is not None
    assert entry.disabled
    assert entry.entity_category is er.EntityCategory.DIAGNOSTIC
    assert hass.states.get(RATE_PROTECTION) is None


async def test_rate_protection_reports_the_flag(
    hass, init_integration, enable_all_entities
):
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    # DRP is 0 for the distributor in the fixture.
    assert hass.states.get(RATE_PROTECTION).state == "off"


async def test_natural_gas_has_no_rate_protection(hass, init_integration):
    """Distribution rate protection is an electricity concept."""
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(NATURAL_GAS_COMPANY)

    registry = er.async_get(hass)

    assert not [
        entry for entry in registry.entities.values() if entry.domain == "binary_sensor"
    ]
