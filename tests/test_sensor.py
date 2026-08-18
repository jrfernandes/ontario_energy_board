"""End-to-end tests for the sensor entities, driven through Home Assistant."""

from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_platform import async_get_platforms
import pytest

from custom_components.ontario_energy_board.const import (
    DOMAIN,
    ELECTRICITY_RATE_UNIT_OF_MEASURE,
    NATURAL_GAS_RATE_UNIT_OF_MEASURE,
    SCAN_INTERVAL,
    STATE_MID_PEAK,
    STATE_OFF_PEAK,
    STATE_ON_PEAK,
    STATE_ULO_ON_PEAK,
    STATE_ULO_OVERNIGHT,
    TOU_PEAK_OPTIONS,
    ULO_PEAK_OPTIONS,
)

from .conftest import ELECTRICITY_COMPANY, NATURAL_GAS_COMPANY, build_config_entry

ONTARIO = ZoneInfo("America/Toronto")

ELECTRICITY = "sensor.alectra_utilities_corporation_brampton_rate_zone_residential"
GAS = "sensor.enbridge_gas_all"


def ontario_moment(year, month, day, hour):
    return datetime(year, month, day, hour, tzinfo=ONTARIO)


async def test_time_of_use_entry_creates_its_entities(hass, init_integration):
    """A Time-of-Use entry gets the rate, the peak, and the season."""
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    assert hass.states.get(f"{ELECTRICITY}_current_rate").state == "0.203"
    assert hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_ON_PEAK
    assert hass.states.get(f"{ELECTRICITY}_season").state == "winter"


async def test_current_rate_is_shaped_for_the_energy_dashboard(hass, init_integration):
    """The unit's suffix after "/" is what Home Assistant converts costs with."""
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    state = hass.states.get(f"{ELECTRICITY}_current_rate")

    assert state.attributes["unit_of_measurement"] == ELECTRICITY_RATE_UNIT_OF_MEASURE
    assert ELECTRICITY_RATE_UNIT_OF_MEASURE.partition("/")[2] == "kWh"
    assert state.attributes["state_class"] == "measurement"
    # device_class monetary would mean "an amount of money" and expects a total
    # state class; a price per kWh is a measurement.
    assert "device_class" not in state.attributes


async def test_rate_and_peak_follow_the_clock(hass, init_integration):
    """Both change as peaks change, without new coordinator data."""
    with freeze_time(ontario_moment(2024, 1, 15, 8)) as frozen:
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

        assert hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_ON_PEAK
        on_peak = float(hass.states.get(f"{ELECTRICITY}_current_rate").state)

        frozen.move_to(ontario_moment(2024, 1, 15, 12))
        for entity_id in (f"{ELECTRICITY}_current_rate", f"{ELECTRICITY}_active_peak"):
            await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

        assert hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_MID_PEAK
        assert float(hass.states.get(f"{ELECTRICITY}_current_rate").state) != on_peak

        frozen.move_to(ontario_moment(2024, 1, 15, 22))
        await async_update_entity(hass, f"{ELECTRICITY}_active_peak")
        await hass.async_block_till_done()

        assert hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_OFF_PEAK


async def test_summer_flips_the_midday_peak(hass, init_integration):
    with freeze_time(ontario_moment(2024, 7, 15, 12)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    assert hass.states.get(f"{ELECTRICITY}_season").state == "summer"
    assert hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_ON_PEAK


async def test_ulo_entry_reports_ulo_peaks_and_no_season(hass, init_integration):
    """ULO prices are the same year round, so a season sensor would mislead."""
    with freeze_time(ontario_moment(2024, 1, 15, 2)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=True)

    assert hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_ULO_OVERNIGHT
    assert float(hass.states.get(f"{ELECTRICITY}_current_rate").state) == pytest.approx(
        0.039
    )
    assert hass.states.get(f"{ELECTRICITY}_season") is None


async def test_ulo_on_peak_window(hass, init_integration):
    with freeze_time(ontario_moment(2024, 1, 15, 17)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=True)

    assert hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_ULO_ON_PEAK
    assert float(hass.states.get(f"{ELECTRICITY}_current_rate").state) == pytest.approx(
        0.391
    )


@pytest.mark.parametrize(
    "ulo_enabled, expected_options",
    [(False, TOU_PEAK_OPTIONS), (True, ULO_PEAK_OPTIONS)],
)
async def test_active_peak_advertises_only_its_plans_peaks(
    hass, init_integration, ulo_enabled, expected_options
):
    """Home Assistant validates an enum's state against its options."""
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=ulo_enabled)

    state = hass.states.get(f"{ELECTRICITY}_active_peak")

    assert state.attributes["options"] == expected_options
    assert state.state in expected_options


async def test_natural_gas_entry_has_only_a_rate(hass, init_integration):
    """Gas has no peak periods, so peak and season sensors would be constants."""
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(NATURAL_GAS_COMPANY)

    state = hass.states.get(f"{GAS}_current_rate")

    assert float(state.state) == pytest.approx(0.103025)
    assert state.attributes["unit_of_measurement"] == NATURAL_GAS_RATE_UNIT_OF_MEASURE
    assert NATURAL_GAS_RATE_UNIT_OF_MEASURE.partition("/")[2] == "m³"

    assert hass.states.get(f"{GAS}_active_peak") is None
    assert hass.states.get(f"{GAS}_season") is None


async def test_entities_are_grouped_under_a_service_device(hass, init_integration):
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        entry = await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})

    assert device is not None
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.manufacturer == "Ontario Energy Board"
    # The sector lives in the model, so the name does not repeat it.
    assert (
        device.name == "Alectra Utilities Corporation-Brampton Rate Zone (RESIDENTIAL)"
    )
    assert device.model == "Electricity · Time-of-Use"

    entities = er.async_entries_for_device(er.async_get(hass), device.id)
    assert len(entities) == 3


async def test_pre_1_0_rate_entity_keeps_its_entity_id(
    hass, mock_oeb, ontario_timezone, enable_custom_integrations
):
    """Upgrading must not orphan the existing sensor or lose its history.

    Before 1.0 the single rate entity was registered under the config entry's
    own unique id. current_rate reuses it, so the registry keeps that row and
    the entity id already present in dashboards survives.
    """
    entry = build_config_entry(ELECTRICITY_COMPANY, ulo_enabled=False)
    entry.add_to_hass(hass)

    registry = er.async_get(hass)
    existing = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        entry.unique_id,
        suggested_object_id="an_established_entity_id",
        config_entry=entry,
    )
    assert existing.entity_id == "sensor.an_established_entity_id"

    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.an_established_entity_id")

    assert state is not None, "the pre-1.0 entity id was orphaned"
    assert float(state.state) == pytest.approx(0.203)
    assert hass.states.get(f"{ELECTRICITY}_current_rate") is None


async def test_utc_instant_is_interpreted_in_ontario_time(hass, init_integration):
    """17:00 UTC is midday in Ontario, not evening."""
    with freeze_time(datetime(2024, 1, 15, 17, tzinfo=ZoneInfo("UTC"))):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    # If UTC leaked through, the hour would read as 17 and this would be on-peak.
    assert hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_MID_PEAK


async def test_only_clock_dependent_entities_poll(hass, init_integration):
    """Rate components change once a day, so polling them every minute is waste."""
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    platforms = async_get_platforms(hass, DOMAIN)

    assert platforms
    assert all(platform.scan_interval == SCAN_INTERVAL for platform in platforms)

    entities = [e for platform in platforms for e in platform.entities.values()]
    polling = {e.entity_description.key for e in entities if e.should_poll}

    assert polling == {"current_rate", "active_peak", "season"}
