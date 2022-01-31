"""Sensor integration for Ontario Energy Board."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, RATE_UNIT_OF_MEASURE


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Ontario Energy Board sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OntarioEnergyBoardSensor(coordinator, entry.unique_id)])


class OntarioEnergyBoardSensor(CoordinatorEntity, SensorEntity):
    """Sensor object for Ontario Energy Board."""

    _attr_unit_of_measurement = RATE_UNIT_OF_MEASURE
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator, energy_company):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{energy_company}"
        self._attr_name = f"{energy_company} Rate"

    @property
    def native_value(self) -> float:
        return self.coordinator.ontario_energy_board.active_peak_rate

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "off_peak_rate": self.coordinator.ontario_energy_board.off_peak_rate,
            "mid_peak_rate": self.coordinator.ontario_energy_board.mid_peak_rate,
            "on_peak_rate": self.coordinator.ontario_energy_board.on_peak_rate,
            "active_peak": self.coordinator.ontario_energy_board.active_peak,
        }
