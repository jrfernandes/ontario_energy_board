"""End-to-end tests for the sensor entities, driven through Home Assistant."""

from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.helpers.entity_platform import async_get_platforms
import pytest

from custom_components.ontario_energy_board.const import (
    CONF_ULO_ENABLED,
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

    entities = er.async_entries_for_device(
        er.async_get(hass), device.id, include_disabled_entities=True
    )
    assert len(entities) > 3


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

    sensor_platforms = [
        platform
        for platform in async_get_platforms(hass, DOMAIN)
        if platform.domain == "sensor"
    ]

    assert sensor_platforms
    assert all(p.scan_interval == SCAN_INTERVAL for p in sensor_platforms)

    entities = [e for p in sensor_platforms for e in p.entities.values()]
    polling = {e.entity_description.key for e in entities if e.should_poll}

    assert polling == {
        "current_rate",
        "current_all_in_rate",
        "active_peak",
        "season",
        "next_peak",
        "next_peak_starts_at",
        "next_peak_rate",
        "next_peak_all_in_rate",
    }

    # The binary sensor tracks a flag that changes at most daily, so it has no
    # reason to poll; it updates when the coordinator refreshes.
    other = [
        e
        for platform in async_get_platforms(hass, DOMAIN)
        if platform.domain != "sensor"
        for e in platform.entities.values()
    ]
    assert not any(e.should_poll for e in other)


def _keys(registry, *, disabled: bool) -> set[str]:
    """Description keys of this device's entities, taken from their entity ids."""
    return {
        entry.entity_id.removeprefix(f"{ELECTRICITY}_")
        for entry in registry.entities.values()
        if bool(entry.disabled) is disabled
        and entry.entity_id.startswith(f"{ELECTRICITY}_")
    }


async def test_period_rates_are_enabled_diagnostics(hass, init_integration):
    """Both plans' rates are published, grouped as diagnostics.

    entity_registry_enabled_default only applies the first time an entity is
    registered, so promoting whichever plan is configured could not survive a
    plan changed later from the options: the newly relevant rates would stay
    disabled. Publishing both, always enabled, sidesteps that and lets the two
    plans be compared.
    """
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    registry = er.async_get(hass)
    enabled = {e.entity_id for e in registry.entities.values() if not e.disabled}

    assert enabled == {
        f"{ELECTRICITY}_current_rate",
        f"{ELECTRICITY}_current_all_in_rate",
        f"{ELECTRICITY}_active_peak",
        f"{ELECTRICITY}_season",
        f"{ELECTRICITY}_next_peak",
        f"{ELECTRICITY}_next_peak_starts",
        f"{ELECTRICITY}_next_peak_rate",
        f"{ELECTRICITY}_next_peak_all_in_rate",
        f"{ELECTRICITY}_off_peak_rate",
        f"{ELECTRICITY}_mid_peak_rate",
        f"{ELECTRICITY}_on_peak_rate",
        f"{ELECTRICITY}_ulo_overnight_rate",
        f"{ELECTRICITY}_ulo_weekend_off_peak_rate",
        f"{ELECTRICITY}_ulo_mid_peak_rate",
        f"{ELECTRICITY}_ulo_on_peak_rate",
    }

    for key in ("on_peak_rate", "ulo_overnight_rate"):
        entry = registry.async_get(f"{ELECTRICITY}_{key}")
        assert entry.entity_category is er.EntityCategory.DIAGNOSTIC, key

    # Only the live values stay out of the diagnostics section.
    assert registry.async_get(f"{ELECTRICITY}_current_rate").entity_category is None
    assert (
        registry.async_get(f"{ELECTRICITY}_current_all_in_rate").entity_category is None
    )
    assert registry.async_get(f"{ELECTRICITY}_active_peak").entity_category is None


async def test_changing_the_rate_plan_takes_effect(hass, init_integration):
    """Correcting the plan from the options changes which rates apply."""
    with freeze_time(ontario_moment(2024, 1, 15, 2)):
        entry = await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

        # 02:00 on a winter weekday: off-peak under Time-of-Use.
        assert hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_OFF_PEAK
        assert float(
            hass.states.get(f"{ELECTRICITY}_current_rate").state
        ) == pytest.approx(0.098)

        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_ULO_ENABLED: True}
        )
        await hass.async_block_till_done()

        # The same moment is overnight under Ultra-Low Overnight.
        assert (
            hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_ULO_OVERNIGHT
        )
        assert float(
            hass.states.get(f"{ELECTRICITY}_current_rate").state
        ) == pytest.approx(0.039)


async def test_changing_the_rate_plan_keeps_the_entities(hass, init_integration):
    """The reload must not orphan anything, least of all the pre-1.0 sensor."""
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        entry = await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

        before = {e.entity_id for e in er.async_get(hass).entities.values()}

        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_ULO_ENABLED: True}
        )
        await hass.async_block_till_done()

    after = {e.entity_id for e in er.async_get(hass).entities.values()}

    assert after == before


async def test_bill_components_ship_as_disabled_diagnostics(hass, init_integration):
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    registry = er.async_get(hass)

    for key in ("loss_factor", "wholesale_market_service_charge", "tier_threshold"):
        entry = next(
            e for e in registry.entities.values() if e.unique_id.endswith(f"_{key}")
        )
        assert entry.disabled, key
        assert entry.entity_category is er.EntityCategory.DIAGNOSTIC, key


async def test_percentages_are_scaled_from_the_oeb_fractions(
    hass, init_integration, enable_all_entities
):
    """HST arrives as 0.13; reporting it as "0.13 %" would be wrong."""
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    state = hass.states.get(f"{ELECTRICITY}_harmonized_sales_tax")

    assert float(state.state) == pytest.approx(13.0)
    assert state.attributes["unit_of_measurement"] == "%"


async def test_empty_oeb_values_report_as_unknown(
    hass, init_integration, enable_all_entities
):
    """The feed ships empty elements for charges a distributor does not levy.

    Those parse to "", which is not a valid state for a measurement sensor.
    """
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    # <VC></VC> is empty in the fixture, as it is for most distributors.
    state = hass.states.get(f"{ELECTRICITY}_distribution_volumetric_charge")

    assert state.state == "unknown"


def test_every_sensor_has_a_translated_name():
    """A missing name leaves entity ids to collide into _2, _3 suffixes.

    has_entity_name builds the entity id from the translated name, so an
    untranslated key is not a cosmetic problem: several entities end up
    competing for the same object id.
    """
    import json
    from pathlib import Path

    from custom_components.ontario_energy_board import sensor as sensor_module

    strings = json.loads(
        (Path(sensor_module.__file__).parent / "strings.json").read_text()
    )
    translated = set(strings["entity"]["sensor"])

    class _Coordinator:
        def __init__(self, energy_sector, ulo_enabled):
            self.energy_sector = energy_sector
            self.ulo_enabled = ulo_enabled

    described = {
        description.translation_key
        for energy_sector, ulo_enabled in (
            ("electricity", False),
            ("electricity", True),
            ("natural_gas", False),
        )
        for description in sensor_module.descriptions_for(
            _Coordinator(energy_sector, ulo_enabled)
        )
    }

    assert described, "no descriptions were collected"
    assert described <= translated, f"untranslated: {sorted(described - translated)}"


async def test_natural_gas_charge_sensors(hass, init_integration):
    """The bill lines a gas customer is most likely to want, enabled."""
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(NATURAL_GAS_COMPANY)

    registry = er.async_get(hass)
    enabled = {
        entry.entity_id.removeprefix(f"{GAS}_")
        for entry in registry.entities.values()
        if not entry.disabled and entry.entity_id.startswith(f"{GAS}_")
    }

    assert enabled == {
        "current_rate",
        "monthly_charge",
        "transportation_charge",
        "federal_carbon_charge",
        "facility_carbon_charge",
        "storage_charge",
        "effective_date",
    }

    assert float(hass.states.get(f"{GAS}_monthly_charge").state) == pytest.approx(27.69)
    assert float(
        hass.states.get(f"{GAS}_transportation_charge").state
    ) == pytest.approx(0.054267)


async def test_gas_effective_date_is_parsed_as_a_date(hass, init_integration):
    """The OEB ships it as an ISO string; a date sensor needs a date."""
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(NATURAL_GAS_COMPANY)

    state = hass.states.get(f"{GAS}_effective_date")

    assert state.state == "2026-07-01"
    assert state.attributes["device_class"] == "date"


async def test_gas_delivery_tiers_ship_disabled(hass, init_integration):
    """Delivery is banded by consumption, so it has no single value.

    Both the per-tier prices and their boundaries are published, and the
    arithmetic is left to the reader.
    """
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(NATURAL_GAS_COMPANY)

    registry = er.async_get(hass)
    disabled = {
        entry.entity_id.removeprefix(f"{GAS}_")
        for entry in registry.entities.values()
        if entry.disabled and entry.entity_id.startswith(f"{GAS}_")
    }

    for tier in range(1, 6):
        assert f"delivery_charge_tier_{tier}" in disabled
        assert f"delivery_tier_{tier}_start" in disabled
        assert f"delivery_tier_{tier}_end" in disabled

    assert "gas_supply_charge_price_adjustment" in disabled
    assert "harmonized_sales_tax" in disabled


async def test_gas_delivery_values_when_enabled(
    hass, init_integration, enable_all_entities
):
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(NATURAL_GAS_COMPANY)

    assert float(
        hass.states.get(f"{GAS}_delivery_charge_tier_1").state
    ) == pytest.approx(0.143745)
    assert float(hass.states.get(f"{GAS}_delivery_tier_1_end").state) == pytest.approx(
        30
    )
    # Adjustments can be negative.
    assert float(
        hass.states.get(f"{GAS}_gas_supply_charge_price_adjustment").state
    ) == pytest.approx(-0.012527)


async def test_monthly_usage_averages_are_not_entities(hass, init_integration):
    """January-December are the OEB's typical-consumption assumptions.

    They describe a notional customer, not this one's rates, so they stay in
    XML_KEY_MAPPINGS for the schema check without becoming twelve sensors.
    """
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(NATURAL_GAS_COMPANY)

    registry = er.async_get(hass)
    entity_ids = {entry.entity_id for entry in registry.entities.values()}

    for month in ("january", "june", "december"):
        assert f"{GAS}_{month}" not in entity_ids


async def test_all_in_rate_is_published_alongside_the_commodity_rate(
    hass, init_integration
):
    """What the next kWh costs once delivery, regulatory charges and tax land."""
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    commodity = float(hass.states.get(f"{ELECTRICITY}_current_rate").state)
    all_in = float(hass.states.get(f"{ELECTRICITY}_current_all_in_rate").state)

    assert commodity == pytest.approx(0.203)
    assert all_in == pytest.approx(0.212135, abs=1e-6)
    assert (
        hass.states.get(f"{ELECTRICITY}_current_all_in_rate").attributes[
            "unit_of_measurement"
        ]
        == ELECTRICITY_RATE_UNIT_OF_MEASURE
    )


async def test_all_in_rate_follows_the_active_peak(hass, init_integration):
    """Delivery is flat per kWh, so the uplift is largest on a cheap kWh."""
    with freeze_time(ontario_moment(2024, 1, 15, 8)) as frozen:
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

        on_peak = float(hass.states.get(f"{ELECTRICITY}_current_all_in_rate").state)

        frozen.move_to(ontario_moment(2024, 1, 15, 22))
        await async_update_entity(hass, f"{ELECTRICITY}_current_all_in_rate")
        await async_update_entity(hass, f"{ELECTRICITY}_current_rate")
        await hass.async_block_till_done()

        off_peak = float(hass.states.get(f"{ELECTRICITY}_current_all_in_rate").state)
        off_peak_commodity = float(hass.states.get(f"{ELECTRICITY}_current_rate").state)

    assert off_peak == pytest.approx(0.114956, abs=1e-6)
    assert off_peak < on_peak
    # 0.098 headline becomes 0.1150 all-in: a 17% uplift, against 4.5% on-peak.
    assert off_peak / off_peak_commodity > on_peak / 0.203


async def test_natural_gas_has_no_all_in_rate(hass, init_integration):
    """Gas delivery is banded by monthly volume, so it has no marginal rate."""
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(NATURAL_GAS_COMPANY)

    assert hass.states.get(f"{GAS}_current_all_in_rate") is None


async def test_next_peak_sensors_report_the_coming_change(hass, init_integration):
    """A winter weekday morning is on-peak until eleven, then mid-peak."""
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    assert hass.states.get(f"{ELECTRICITY}_active_peak").state == STATE_ON_PEAK
    assert hass.states.get(f"{ELECTRICITY}_next_peak").state == STATE_MID_PEAK
    assert float(
        hass.states.get(f"{ELECTRICITY}_next_peak_rate").state
    ) == pytest.approx(0.157)


async def test_next_peak_starts_is_an_instant_not_a_countdown(hass, init_integration):
    """Home Assistant renders a timestamp as relative time by itself."""
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    state = hass.states.get(f"{ELECTRICITY}_next_peak_starts")

    assert state.attributes["device_class"] == "timestamp"
    assert datetime.fromisoformat(state.state) == ontario_moment(2024, 1, 15, 11)


async def test_next_peak_looks_across_a_whole_weekend(hass, init_integration):
    """Friday evening off-peak runs until Monday morning."""
    with freeze_time(ontario_moment(2024, 1, 12, 19)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    state = hass.states.get(f"{ELECTRICITY}_next_peak_starts")

    assert datetime.fromisoformat(state.state) == ontario_moment(2024, 1, 15, 7)
    assert hass.states.get(f"{ELECTRICITY}_next_peak").state == STATE_ON_PEAK


async def test_next_peak_all_in_rate_matches_the_billing_arithmetic(
    hass, init_integration
):
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=False)

    # Mid-peak comes next; 0.157 all-in for this distributor.
    assert float(
        hass.states.get(f"{ELECTRICITY}_next_peak_all_in_rate").state
    ) == pytest.approx(0.169561, abs=1e-6)


async def test_next_peak_advertises_only_its_plans_peaks(hass, init_integration):
    with freeze_time(ontario_moment(2024, 1, 15, 8)):
        await init_integration(ELECTRICITY_COMPANY, ulo_enabled=True)

    state = hass.states.get(f"{ELECTRICITY}_next_peak")

    assert state.attributes["options"] == ULO_PEAK_OPTIONS
    assert state.state in ULO_PEAK_OPTIONS


async def test_natural_gas_has_no_next_peak_sensors(hass, init_integration):
    with freeze_time(ontario_moment(2024, 1, 15, 12)):
        await init_integration(NATURAL_GAS_COMPANY)

    for key in ("next_peak", "next_peak_starts", "next_peak_rate"):
        assert hass.states.get(f"{GAS}_{key}") is None
