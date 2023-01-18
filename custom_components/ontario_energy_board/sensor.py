"""Sensor integration for Ontario Energy Board."""
from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import as_local, now

from .const import (
    DOMAIN,
    RATE_UNIT_OF_MEASURE,
    STATE_MID_PEAK,
    STATE_OFF_PEAK,
    STATE_ON_PEAK,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Ontario Energy Board sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OntarioEnergyBoardSensor(coordinator)])


class OntarioEnergyBoardSensor(CoordinatorEntity, SensorEntity):
    """Sensor object for Ontario Energy Board."""

    _attr_native_unit_of_measurement = RATE_UNIT_OF_MEASURE
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.energy_company}"
        self._attr_name = f"{coordinator.energy_company} Rate"

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def is_summer(self) -> bool:
        current_time = as_local(now())
        return (
            date(current_time.year, 5, 1)
            <= current_time.date()
            <= date(current_time.year, 10, 31)
        )

    @property
    def active_peak(self) -> str:
        """
        Find the active peak based on the current day and hour.

        According to OEB, weekends and holidays are 24-hour off peak periods.
        During summer (observed from May 1st to Oct 31st), the morning and evening
        periods are mid-peak, and the afternoon is on-peak. This flips during winter
        time, where morning and evening are on-peak and afternoons mid-peak.
        """
        current_time = as_local(now())

        is_holiday = current_time.date() in self.coordinator.ontario_holidays
        is_weekend = current_time.weekday() >= 5

        if is_holiday or is_weekend:
            return STATE_OFF_PEAK

        current_hour = int(current_time.strftime("%H"))
        if (7 <= current_hour < 11) or (17 <= current_hour < 19):
            return STATE_MID_PEAK if self.is_summer else STATE_ON_PEAK
        if 11 <= current_hour < 17:
            return STATE_ON_PEAK if self.is_summer else STATE_MID_PEAK

        return STATE_OFF_PEAK

    @property
    def native_value(self) -> float:
        """Returns the current peak's rate."""
        return getattr(self.coordinator, f"{self.active_peak}_rate")

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "energy_company": self.coordinator.energy_company,
            "off_peak_rate": self.coordinator.off_peak_rate,
            "mid_peak_rate": self.coordinator.mid_peak_rate,
            "on_peak_rate": self.coordinator.on_peak_rate,
            "active_peak": self.active_peak,
            "season": "summer" if self.is_summer else "winter",
            "tier_threshold": self.coordinator.tier_threshold,
            "tier_1": self.coordinator.tier_1_rate,
            "tier_2": self.coordinator.tier_2_rate,
            "service_charge": self.coordinator.service_charge,
            "loss_adjustment_factor": self.coordinator.loss_adjustment_factor,
            "network_service_rate": self.coordinator.network_service_rate,
            "connection_service_rate": self.coordinator.connection_service_rate,
            "wholesale_market_service_rate": self.coordinator.wholesale_market_service_rate,
            "rural_remote_rate_protection_charge": self.coordinator.rural_remote_rate_protection_charge,
            "standard_supply_service": self.coordinator.standard_supply_service,
            "gst": self.coordinator.gst,
            "rebate": self.coordinator.rebate,
            "one_time_fixed_charge": self.coordinator.one_time_fixed_charge,
        }
