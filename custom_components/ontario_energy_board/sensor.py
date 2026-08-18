"""Sensor platform for the Ontario Energy Board integration.

Entities are declared as `SensorEntityDescription`s carrying a `value_fn` that
reads from the coordinator, so a new OEB field becomes one table row rather
than a new class.
"""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import as_local, now

from . import peaks
from .const import (
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
    suggested_display_precision=5,
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
        return [CURRENT_RATE_NATURAL_GAS]

    peak_options = ULO_PEAK_OPTIONS if coordinator.ulo_enabled else TOU_PEAK_OPTIONS

    descriptions = [
        CURRENT_RATE_ELECTRICITY,
        _active_peak_description(peak_options),
    ]

    # Only Time-of-Use swaps its schedule between summer and winter.
    if not coordinator.ulo_enabled:
        descriptions.append(SEASON)

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
