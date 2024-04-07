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
    ELECTRICITY_RATE_UNIT_OF_MEASURE,
    NATURAL_GAS_RATE_UNIT_OF_MEASURE,
    STATE_MID_PEAK,
    STATE_NO_PEAK,
    STATE_OFF_PEAK,
    STATE_ON_PEAK,
    STATE_ULO_MID_PEAK,
    STATE_ULO_ON_PEAK,
    STATE_ULO_OFF_PEAK,
    STATE_ULO_OVERNIGHT,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Ontario Energy Board sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OntarioEnergyBoardSensor(coordinator, entry.unique_id)])


class OntarioEnergyBoardSensor(CoordinatorEntity, SensorEntity):
    """Sensor object for Ontario Energy Board."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator, entity_unique_id):
        super().__init__(coordinator)
        self._attr_unique_id = entity_unique_id
        self._attr_name = f"{coordinator.energy_company} Rate"
        self._attr_native_unit_of_measurement = (
            ELECTRICITY_RATE_UNIT_OF_MEASURE
            if self.coordinator.energy_sector == "electricity"
            else NATURAL_GAS_RATE_UNIT_OF_MEASURE
        )

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
        if self.coordinator.ulo_enabled:
            return self.ulo_active_peak
        else:
            return self.tou_active_peak

    @property
    def ulo_active_peak(self) -> str:
        """
        Find the active peak based on the current day and hour.

        According to OEB, ULO nighttime rates apply every day. On weekends and
        holidays, daytime is off-peak. On weekdays, late afternoon and early
        evening is on-peak. The rest is mid-peak.

        ULO prices and periods are the same all year round.
        """
        current_time = as_local(now())
        current_hour = int(current_time.strftime("%H"))

        is_overnight = current_hour < 7 or current_hour >= 23
        if is_overnight:
            return STATE_ULO_OVERNIGHT

        is_holiday = current_time.date() in self.coordinator.ontario_holidays
        is_weekend = current_time.weekday() >= 5

        if is_holiday or is_weekend:
            return STATE_ULO_OFF_PEAK

        is_on_peak = 16 <= current_hour < 21
        if is_on_peak:
            return STATE_ULO_ON_PEAK

        return STATE_ULO_MID_PEAK

    @property
    def tou_active_peak(self) -> str:
        """
        Find the active peak based on the current day and hour.

        According to OEB, weekends and holidays are 24-hour off-peak periods.
        During summer (observed from May 1st to Oct 31st), the morning and evening
        periods are mid-peak, and the afternoon is on-peak. This flips during winter
        time, where morning and evening are on-peak and afternoons mid-peak.
        """

        if self.coordinator.energy_sector == "natural_gas":
            return STATE_NO_PEAK

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
    def native_value(self) -> float | str:
        rates_mapper = {
            "on_peak": "time_of_use_on_peak_price",
            "mid_peak": "time_of_use_mid_peak_price",
            "off_peak": "time_of_use_off_peak_price",
            "no_peak": "no_peak_rate",
        }

        """Returns the current peak's rate."""
        return (
            self.coordinator.company_data[rates_mapper[self.active_peak]]
            if rates_mapper[self.active_peak] in self.coordinator.company_data
            else STATE_NO_PEAK
        )

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "energy_company": self.coordinator.energy_company,
            "energy_sector": self.coordinator.energy_sector,
            "active_peak": self.active_peak,
            "season": "summer" if self.is_summer else "winter",
        } | self.coordinator.company_data
