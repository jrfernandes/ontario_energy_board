"""Base entity for the Ontario Energy Board integration."""

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .common import company_display_name
from .const import DOMAIN, MANUFACTURER, OEB_URL, SECTOR_ELECTRICITY
from .coordinator import OntarioEnergyBoardDataUpdateCoordinator


def device_model(coordinator: OntarioEnergyBoardDataUpdateCoordinator) -> str:
    """Describe the sector and rate plan this entry is configured for."""
    if coordinator.energy_sector != SECTOR_ELECTRICITY:
        return "Natural Gas"

    plan = "Ultra-Low Overnight" if coordinator.ulo_enabled else "Time-of-Use"

    return f"Electricity · {plan}"


class OntarioEnergyBoardEntity(
    CoordinatorEntity[OntarioEnergyBoardDataUpdateCoordinator]
):
    """Shared device wiring for every Ontario Energy Board entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OntarioEnergyBoardDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)

        self.entity_description = description

        entry = coordinator.config_entry

        # Derived from the entry id, which is assigned once and never changes.
        # The company and the rate plan both can change, so neither can be part
        # of an entity's identity without orphaning it later.
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer=MANUFACTURER,
            name=company_display_name(coordinator.energy_company),
            model=device_model(coordinator),
            configuration_url=OEB_URL,
        )
