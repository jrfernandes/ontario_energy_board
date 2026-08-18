"""Sensor platform for the Ontario Energy Board integration.

Entities are declared as `SensorEntityDescription`s carrying a `value_fn` that
reads from the coordinator, so a new OEB field becomes one table row rather
than a new class.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import as_local, now

from . import peaks
from .const import (
    CURRENCY_UNIT,
    DOMAIN,
    ELECTRICITY_RATE_UNIT_OF_MEASURE,
    NATURAL_GAS_RATE_UNIT_OF_MEASURE,
    PEAK_KEY_MAPPINGS,
    SCAN_INTERVAL,
    SEASON_OPTIONS,
    SECTOR_ELECTRICITY,
    STATE_SUMMER,
    STATE_WINTER,
    TOU_PEAK_OPTIONS,
    ULO_PEAK_OPTIONS,
)
from .coordinator import OntarioEnergyBoardDataUpdateCoordinator
from .entity import OntarioEnergyBoardEntity

# Home Assistant reads the poll interval off the platform module itself.
__all__ = ["SCAN_INTERVAL", "async_setup_entry"]


@dataclass(frozen=True, kw_only=True)
class OntarioEnergyBoardSensorEntityDescription(SensorEntityDescription):
    """Describes an Ontario Energy Board sensor."""

    value_fn: Callable[[OntarioEnergyBoardDataUpdateCoordinator], StateType]
    # Most values only change when the coordinator refreshes, once a day. Only
    # the few derived from the wall clock need the platform to poll them.
    clock_dependent: bool = False
    # Reuses the config entry's own unique id, preserving an entity that
    # predates the device layout.
    use_entry_unique_id: bool = False


def _active_peak(coordinator: OntarioEnergyBoardDataUpdateCoordinator) -> str:
    return peaks.active_peak(
        as_local(now()),
        coordinator.ontario_holidays,
        energy_sector=coordinator.energy_sector,
        ulo_enabled=coordinator.ulo_enabled,
    )


def _current_rate(
    coordinator: OntarioEnergyBoardDataUpdateCoordinator,
) -> StateType:
    """The rate in effect right now, per the entry's sector and rate plan."""
    company_data = coordinator.company_data

    if coordinator.energy_sector != SECTOR_ELECTRICITY:
        return company_data.get("gas_supply_charge")

    mapping = PEAK_KEY_MAPPINGS.get(_active_peak(coordinator))

    return None if mapping is None else company_data.get(mapping)


def _season(coordinator: OntarioEnergyBoardDataUpdateCoordinator) -> str:
    return STATE_SUMMER if peaks.is_summer(as_local(now())) else STATE_WINTER


def _numeric(
    key: str,
) -> Callable[[OntarioEnergyBoardDataUpdateCoordinator], StateType]:
    """Read a numeric field.

    The OEB feed ships empty elements for charges that do not apply to a
    distributor, which parse to "". Report those as unknown rather than letting
    a non-numeric state reach a measurement sensor.
    """

    def value_fn(coordinator: OntarioEnergyBoardDataUpdateCoordinator) -> StateType:
        value = coordinator.company_data.get(key)
        return value if isinstance(value, (int, float)) else None

    return value_fn


def _percentage(
    key: str,
) -> Callable[[OntarioEnergyBoardDataUpdateCoordinator], StateType]:
    """Read a rate the OEB stores as a fraction, and report it as a percentage.

    HST arrives as 0.13, not 13.
    """

    def value_fn(coordinator: OntarioEnergyBoardDataUpdateCoordinator) -> StateType:
        value = coordinator.company_data.get(key)
        return value * 100 if isinstance(value, (int, float)) else None

    return value_fn


def _rate(
    key: str, translation_key: str, **kwargs
) -> OntarioEnergyBoardSensorEntityDescription:
    """A price per kWh."""
    return OntarioEnergyBoardSensorEntityDescription(
        key=translation_key,
        translation_key=translation_key,
        native_unit_of_measurement=ELECTRICITY_RATE_UNIT_OF_MEASURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_numeric(key),
        **kwargs,
    )


def _gas_rate(
    key: str, translation_key: str, **kwargs
) -> OntarioEnergyBoardSensorEntityDescription:
    """A price per cubic metre."""
    return OntarioEnergyBoardSensorEntityDescription(
        key=translation_key,
        translation_key=translation_key,
        native_unit_of_measurement=NATURAL_GAS_RATE_UNIT_OF_MEASURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=6,
        value_fn=_numeric(key),
        **kwargs,
    )


def _volume(
    key: str, translation_key: str
) -> OntarioEnergyBoardSensorEntityDescription:
    """A tier boundary, expressed as a consumption threshold."""
    return OntarioEnergyBoardSensorEntityDescription(
        key=translation_key,
        translation_key=translation_key,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=0,
        value_fn=_numeric(key),
    )


def _effective_date(
    coordinator: OntarioEnergyBoardDataUpdateCoordinator,
) -> date | None:
    """Parse the date these rates took effect, which arrives as an ISO string."""
    value = coordinator.company_data.get("effective_date")

    if not isinstance(value, str):
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _as_diagnostic(
    description: OntarioEnergyBoardSensorEntityDescription,
) -> OntarioEnergyBoardSensorEntityDescription:
    """Demote a sensor to a diagnostic that is off until someone asks for it."""
    return replace(
        description,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    )


def _as_shown_diagnostic(
    description: OntarioEnergyBoardSensorEntityDescription,
) -> OntarioEnergyBoardSensorEntityDescription:
    """Group a sensor under the device's diagnostics, but leave it enabled."""
    return replace(description, entity_category=EntityCategory.DIAGNOSTIC)


CURRENT_RATE_ELECTRICITY = OntarioEnergyBoardSensorEntityDescription(
    key="current_rate",
    translation_key="current_rate",
    native_unit_of_measurement=ELECTRICITY_RATE_UNIT_OF_MEASURE,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=4,
    value_fn=_current_rate,
    clock_dependent=True,
    use_entry_unique_id=True,
)

CURRENT_RATE_NATURAL_GAS = OntarioEnergyBoardSensorEntityDescription(
    key="current_rate",
    translation_key="current_rate",
    native_unit_of_measurement=NATURAL_GAS_RATE_UNIT_OF_MEASURE,
    state_class=SensorStateClass.MEASUREMENT,
    suggested_display_precision=6,
    value_fn=_current_rate,
    use_entry_unique_id=True,
)

SEASON = OntarioEnergyBoardSensorEntityDescription(
    key="season",
    translation_key="season",
    device_class=SensorDeviceClass.ENUM,
    options=SEASON_OPTIONS,
    entity_category=EntityCategory.DIAGNOSTIC,
    value_fn=_season,
    clock_dependent=True,
)


TOU_RATE_SENSORS = (
    _rate("time_of_use_off_peak_price", "off_peak_rate"),
    _rate("time_of_use_mid_peak_price", "mid_peak_rate"),
    _rate("time_of_use_on_peak_price", "on_peak_rate"),
)

ULO_RATE_SENSORS = (
    _rate("ultra_low_overnight_overnight_rate", "ulo_overnight_rate"),
    _rate("ultra_low_overnight_weekend_off_peak_rate", "ulo_off_peak_rate"),
    _rate("ultra_low_overnight_mid_peak_rate", "ulo_mid_peak_rate"),
    _rate("ultra_low_overnight_on_peak_rate", "ulo_on_peak_rate"),
)

# Everything needed to reconstruct a bill, off by default. The README documents
# this use case; enable what you need in the entity registry.
ELECTRICITY_DIAGNOSTIC_SENSORS = (
    # Volumetric, priced per kWh.
    _rate("distribution_variable_charge", "distribution_variable_charge"),
    _rate("distribution_volumetric_charge", "distribution_volumetric_charge"),
    _rate("other_volumetric_charges", "other_volumetric_charges"),
    _rate("global_adjustment", "global_adjustment"),
    _rate("global_adjustment_rate_rider", "global_adjustment_rate_rider"),
    _rate("retail_transmission_network_rate", "transmission_network_rate"),
    _rate("retail_transmission_connection_rate", "transmission_connection_rate"),
    _rate("wholesale_market_service_charge", "wholesale_market_service_charge"),
    _rate("rural_remote_rate_protection", "rural_remote_rate_protection"),
    _rate("debt_retirement_charge", "debt_retirement_charge"),
    _rate("lower_tier_price", "lower_tier_price"),
    _rate("higher_tier_price", "higher_tier_price"),
    # Fixed amounts.
    OntarioEnergyBoardSensorEntityDescription(
        key="monthly_fixed_charge",
        translation_key="monthly_fixed_charge",
        native_unit_of_measurement=CURRENCY_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_numeric("monthly_fixed_charge"),
    ),
    OntarioEnergyBoardSensorEntityDescription(
        key="standard_supply_service_charge",
        translation_key="standard_supply_service_charge",
        native_unit_of_measurement=CURRENCY_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_numeric("standard_supply_service_charge"),
    ),
    OntarioEnergyBoardSensorEntityDescription(
        key="other_fixed_charges",
        translation_key="other_fixed_charges",
        native_unit_of_measurement=CURRENCY_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_numeric("other_fixed_charges"),
    ),
    OntarioEnergyBoardSensorEntityDescription(
        key="distribution_rate_protection_rate",
        translation_key="distribution_rate_protection_rate",
        native_unit_of_measurement=CURRENCY_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_numeric("distribution_rate_protection_rate"),
    ),
    # Percentages, stored by the OEB as fractions.
    OntarioEnergyBoardSensorEntityDescription(
        key="harmonized_sales_tax",
        translation_key="harmonized_sales_tax",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_percentage("harmonized_sales_tax"),
    ),
    OntarioEnergyBoardSensorEntityDescription(
        key="ontario_electricity_rebate",
        translation_key="ontario_electricity_rebate",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_percentage("ontario_electricity_rebate"),
    ),
    # Everything else.
    OntarioEnergyBoardSensorEntityDescription(
        key="tier_threshold",
        translation_key="tier_threshold",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_numeric("tier_threshold"),
    ),
    OntarioEnergyBoardSensorEntityDescription(
        key="loss_factor",
        translation_key="loss_factor",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=4,
        value_fn=_numeric("loss_factor"),
    ),
    OntarioEnergyBoardSensorEntityDescription(
        key="rate_year",
        translation_key="rate_year",
        suggested_display_precision=0,
        value_fn=_numeric("rate_year"),
    ),
)


# The bill lines a gas customer is most likely to want, grouped under the
# device's diagnostics but left enabled.
NATURAL_GAS_CHARGE_SENSORS = (
    OntarioEnergyBoardSensorEntityDescription(
        key="monthly_charge",
        translation_key="monthly_charge",
        native_unit_of_measurement=CURRENCY_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=_numeric("monthly_charge"),
    ),
    _gas_rate("transportation_charge", "transportation_charge"),
    _gas_rate("federal_carbon_charge", "federal_carbon_charge"),
    _gas_rate("facility_carbon_charge", "facility_carbon_charge"),
    _gas_rate("storage_charge", "storage_charge"),
    OntarioEnergyBoardSensorEntityDescription(
        key="effective_date",
        translation_key="effective_date",
        device_class=SensorDeviceClass.DATE,
        value_fn=_effective_date,
    ),
)

# Delivery is banded by consumption, so there is no single delivery charge
# without knowing usage. Both the per-tier prices and their boundaries are
# published, and the arithmetic is left to the reader.
NATURAL_GAS_DELIVERY_SENSORS = tuple(
    description
    for tier in range(1, 6)
    for description in (
        _gas_rate(f"delivery_charge_tier_{tier}", f"delivery_charge_tier_{tier}"),
        _volume(f"delivery_tier_{tier}_start", f"delivery_tier_{tier}_start"),
        _volume(f"delivery_tier_{tier}_end", f"delivery_tier_{tier}_end"),
    )
)

NATURAL_GAS_DIAGNOSTIC_SENSORS = (
    *NATURAL_GAS_DELIVERY_SENSORS,
    _gas_rate("delivery_charge_price_adjustment", "delivery_charge_price_adjustment"),
    _gas_rate("storage_charge_price_adjustment", "storage_charge_price_adjustment"),
    _gas_rate(
        "gas_supply_charge_price_adjustment", "gas_supply_charge_price_adjustment"
    ),
    _gas_rate(
        "transportation_charge_price_adjustment",
        "transportation_charge_price_adjustment",
    ),
    OntarioEnergyBoardSensorEntityDescription(
        key="harmonized_sales_tax",
        translation_key="harmonized_sales_tax",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_percentage("harmonized_sales_tax"),
    ),
)


def _active_peak_description(
    options: list[str],
) -> OntarioEnergyBoardSensorEntityDescription:
    return OntarioEnergyBoardSensorEntityDescription(
        key="active_peak",
        translation_key="active_peak",
        device_class=SensorDeviceClass.ENUM,
        options=options,
        value_fn=_active_peak,
        clock_dependent=True,
    )


def descriptions_for(
    coordinator: OntarioEnergyBoardDataUpdateCoordinator,
) -> list[OntarioEnergyBoardSensorEntityDescription]:
    """Pick the sensors that make sense for this entry's sector and plan."""
    if coordinator.energy_sector != SECTOR_ELECTRICITY:
        # Gas has no peak periods and no seasonal schedule.
        return [
            CURRENT_RATE_NATURAL_GAS,
            *(
                _as_shown_diagnostic(description)
                for description in NATURAL_GAS_CHARGE_SENSORS
            ),
            *(
                _as_diagnostic(description)
                for description in NATURAL_GAS_DIAGNOSTIC_SENSORS
            ),
        ]

    peak_options = ULO_PEAK_OPTIONS if coordinator.ulo_enabled else TOU_PEAK_OPTIONS

    descriptions = [
        CURRENT_RATE_ELECTRICITY,
        _active_peak_description(peak_options),
    ]

    # Only Time-of-Use swaps its schedule between summer and winter.
    if not coordinator.ulo_enabled:
        descriptions.append(SEASON)

    # Both plans' rates are published as enabled diagnostics, rather than
    # promoting whichever plan is configured. entity_registry_enabled_default
    # only applies the first time an entity is registered, so a split could not
    # follow a plan changed later from the options: the newly relevant rates
    # would stay disabled. Publishing both also lets the two be compared.
    descriptions.extend(
        _as_shown_diagnostic(description)
        for description in (*TOU_RATE_SENSORS, *ULO_RATE_SENSORS)
    )
    descriptions.extend(
        _as_diagnostic(description) for description in ELECTRICITY_DIAGNOSTIC_SENSORS
    )

    return descriptions


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ontario Energy Board sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        OntarioEnergyBoardSensor(coordinator, description)
        for description in descriptions_for(coordinator)
    )


class OntarioEnergyBoardSensor(OntarioEnergyBoardEntity, SensorEntity):
    """A single value published by the Ontario Energy Board."""

    entity_description: OntarioEnergyBoardSensorEntityDescription

    @property
    def should_poll(self) -> bool:
        """Poll only the values that change with the clock rather than the data."""
        return self.entity_description.clock_dependent

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator)
