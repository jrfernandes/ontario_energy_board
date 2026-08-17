"""Binary sensor platform for the Ontario Energy Board integration."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, SECTOR_ELECTRICITY
from .coordinator import OntarioEnergyBoardDataUpdateCoordinator
from .entity import OntarioEnergyBoardEntity


@dataclass(frozen=True, kw_only=True)
class OntarioEnergyBoardBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Ontario Energy Board binary sensor."""

    value_fn: Callable[[OntarioEnergyBoardDataUpdateCoordinator], bool | None]


def _distribution_rate_protection(
    coordinator: OntarioEnergyBoardDataUpdateCoordinator,
) -> bool | None:
    """Whether this distributor's customers get distribution rate protection.

    The OEB publishes it as 0 or 1 rather than as a charge, which is why it is
    a binary sensor and not one more rate.
    """
    value = coordinator.company_data.get("distribution_rate_protection")

    return bool(value) if isinstance(value, (int, float)) else None


ELECTRICITY_BINARY_SENSORS = (
    OntarioEnergyBoardBinarySensorEntityDescription(
        key="distribution_rate_protection",
        translation_key="distribution_rate_protection",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_distribution_rate_protection,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ontario Energy Board binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Distribution rate protection is an electricity concept.
    if coordinator.energy_sector != SECTOR_ELECTRICITY:
        return

    async_add_entities(
        OntarioEnergyBoardBinarySensor(coordinator, description)
        for description in ELECTRICITY_BINARY_SENSORS
    )


class OntarioEnergyBoardBinarySensor(OntarioEnergyBoardEntity, BinarySensorEntity):
    """A boolean flag published by the Ontario Energy Board."""

    entity_description: OntarioEnergyBoardBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator)
