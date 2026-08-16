"""End-to-end tests for the sensor entity, driven through Home Assistant."""

from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from homeassistant.helpers.entity_component import async_update_entity
import pytest

from custom_components.ontario_energy_board.const import (
    ELECTRICITY_RATE_UNIT_OF_MEASURE,
    NATURAL_GAS_RATE_UNIT_OF_MEASURE,
    STATE_MID_PEAK,
    STATE_NO_PEAK,
    STATE_OFF_PEAK,
    STATE_ON_PEAK,
    STATE_ULO_ON_PEAK,
    STATE_ULO_OVERNIGHT,
)

from .conftest import ELECTRICITY_COMPANY, NATURAL_GAS_COMPANY

ONTARIO = ZoneInfo("America/Toronto")

ELECTRICITY_ENTITY = (
    "sensor.alectra_utilities_corporation_brampton_rate_zone_residential_"
    "electricity_rate"
)
NATURAL_GAS_ENTITY = "sensor.enbridge_gas_all_natural_gas_rate"


def ontario_moment(year, month, day, hour):
    return datetime(year, month, day, hour, tzinfo=ONTARIO)


async def find_entity(hass, unique_id_fragment):
    """Locate the created sensor without hard-coding slug rules."""
    states = [
        state
        for state in hass.states.async_all("sensor")
        if unique_id_fragment in state.attributes.get("energy_company", "")
    ]
    assert len(states) == 1, [s.entity_id for s in hass.states.async_all("sensor")]
    return states[0]


async def test_electricity_sensor_reports_active_peak_rate(hass, init_integration):
    # A Monday in winter at 08:00 local: on-peak under TOU.
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

        state = await find_entity(hass, "Alectra")

        assert state.attributes["active_peak"] == STATE_ON_PEAK
        assert state.attributes["season"] == "winter"
        assert (
            state.attributes["unit_of_measurement"] == ELECTRICITY_RATE_UNIT_OF_MEASURE
        )
        assert float(state.state) == pytest.approx(0.203)


async def test_electricity_sensor_follows_the_clock(hass, init_integration):
    """The state must change as peaks change, without new coordinator data."""
    with freeze_time(ontario_moment(2024, 1, 15, 8)) as frozen:
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

        state = await find_entity(hass, "Alectra")
        assert state.attributes["active_peak"] == STATE_ON_PEAK
        on_peak_rate = float(state.state)

        # Move to 12:00 the same day: mid-peak in winter.
        frozen.move_to(ontario_moment(2024, 1, 15, 12))
        await async_update_entity(hass, state.entity_id)
        await hass.async_block_till_done()

        state = hass.states.get(state.entity_id)
        assert state.attributes["active_peak"] == STATE_MID_PEAK
        assert float(state.state) != on_peak_rate

        # Move to 22:00: off-peak.
        frozen.move_to(ontario_moment(2024, 1, 15, 22))
        await async_update_entity(hass, state.entity_id)
        await hass.async_block_till_done()

        assert (
            hass.states.get(state.entity_id).attributes["active_peak"] == STATE_OFF_PEAK
        )


async def test_summer_flips_the_midday_peak(hass, init_integration):
    with freeze_time(ontario_moment(2024, 7, 15, 12)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

        state = await find_entity(hass, "Alectra")

        assert state.attributes["season"] == "summer"
        assert state.attributes["active_peak"] == STATE_ON_PEAK


async def test_ulo_entry_uses_ulo_rates(hass, init_integration):
    # 02:00 local, any day: ULO overnight.
    with freeze_time(ontario_moment(2024, 1, 15, 2)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=True)

        state = await find_entity(hass, "Alectra")

        assert state.attributes["active_peak"] == STATE_ULO_OVERNIGHT
        assert float(state.state) == pytest.approx(0.039)


async def test_ulo_on_peak_window(hass, init_integration):
    with freeze_time(ontario_moment(2024, 1, 15, 17)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=True)

        state = await find_entity(hass, "Alectra")

        assert state.attributes["active_peak"] == STATE_ULO_ON_PEAK
        assert float(state.state) == pytest.approx(0.391)


async def test_natural_gas_sensor_reports_supply_charge(hass, init_integration):
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(NATURAL_GAS_COMPANY)

        state = await find_entity(hass, "Enbridge")

        assert state.attributes["active_peak"] == STATE_NO_PEAK
        assert (
            state.attributes["unit_of_measurement"] == NATURAL_GAS_RATE_UNIT_OF_MEASURE
        )
        assert float(state.state) == pytest.approx(0.103025)


async def test_attributes_include_full_billing_data(hass, init_integration):
    """The documented attribute table depends on every mapped key being present."""
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(ELECTRICITY_COMPANY)

        state = await find_entity(hass, "Alectra")

        for attribute in (
            "distributor_name",
            "rate_class",
            "rate_year",
            "tier_threshold",
            "monthly_fixed_charge",
            "harmonized_sales_tax",
            "time_of_use_on_peak_price",
            "ultra_low_overnight_overnight_rate",
            "ontario_electricity_rebate",
        ):
            assert attribute in state.attributes, attribute


async def test_utc_instant_is_interpreted_in_ontario_time(hass, init_integration):
    """17:00 UTC is midday in Ontario, not evening.

    This is the failure mode the old Mock-based tests could not see: patching
    the localisation helper hid whether the conversion happened at all.
    """
    with freeze_time(datetime(2024, 1, 15, 17, tzinfo=ZoneInfo("UTC"))):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

        state = await find_entity(hass, "Alectra")

        # 12:00 EST on a winter weekday is mid-peak. If UTC leaked through, the
        # hour would read as 17 and the state would be on-peak.
        assert state.attributes["active_peak"] == STATE_MID_PEAK


async def test_platform_uses_the_declared_scan_interval(hass, init_integration):
    """SCAN_INTERVAL only takes effect if it is a name on the platform module.

    Home Assistant reads it with getattr(platform, "SCAN_INTERVAL", None), so
    declaring it in const alone leaves the platform on the sensor default.
    """
    from homeassistant.helpers.entity_platform import async_get_platforms

    from custom_components.ontario_energy_board.const import DOMAIN, SCAN_INTERVAL

    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(ELECTRICITY_COMPANY)

    platforms = async_get_platforms(hass, DOMAIN)

    assert platforms
    assert all(platform.scan_interval == SCAN_INTERVAL for platform in platforms)
