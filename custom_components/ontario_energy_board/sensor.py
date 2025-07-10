"""Sensor integration for Ontario Energy Board."""

from datetime import date
from functools import partial

from holidays import country_holidays

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.setup import SetupPhases, async_pause_setup
from homeassistant.util.dt import as_local, now

from .common import get_energy_sector_metadata
from .const import (
    DOMAIN,
    PEAK_KEY_MAPPINGS,
    STATE_MID_PEAK,
    STATE_NO_PEAK,
    STATE_OFF_PEAK,
    STATE_ON_PEAK,
    STATE_ULO_MID_PEAK,
    STATE_ULO_OFF_PEAK,
    STATE_ULO_ON_PEAK,
    STATE_ULO_OVERNIGHT,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ontario Energy Board sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    with async_pause_setup(hass, SetupPhases.WAIT_IMPORT_PACKAGES):
        ontario_holidays = await hass.async_add_import_executor_job(
            partial(
                country_holidays,
                "CA",
                subdiv="ON",
                observed=True,
                categories={"public", "optional"},
            )
        )

    async_add_entities([OntarioEnergyBoardSensor(coordinator, entry.unique_id)])


class OntarioEnergyBoardSensor(CoordinatorEntity, SensorEntity):
    """Sensor object for Ontario Energy Board."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator, entity_unique_id, ontario_holidays) -> None:
        super().__init__(coordinator)

        energy_company_metadata = get_energy_sector_metadata(
            self.coordinator.energy_sector
        )

        self.ontario_holidays = ontario_holidays

        self._attr_unique_id = entity_unique_id
        self._attr_name = f"{coordinator.energy_company} Rate"
        self._attr_native_unit_of_measurement = energy_company_metadata[
            "unit_of_measure"
        ]

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
        if self.coordinator.energy_sector == "natural_gas":
            return STATE_NO_PEAK

        if self.coordinator.ulo_enabled:
            return self.ulo_active_peak
        return self.tou_active_peak

    @property
    def ulo_active_peak(self) -> str:
        """Find the active peak based on the current day and hour.

        According to OEB, ULO nighttime rates apply every day. On weekends and
        holidays, daytime is off-peak. On weekdays, late afternoon and early
        evening is on-peak. The rest is mid-peak.

        ULO prices and periods are the same all year round.
        """

        if self.coordinator.energy_sector == "natural_gas":
            return STATE_NO_PEAK

        current_time = as_local(now())
        current_hour = int(current_time.strftime("%H"))

        is_overnight = current_hour < 7 or current_hour >= 23
        if is_overnight:
            return STATE_ULO_OVERNIGHT

        is_holiday = current_time.date() in self.ontario_holidays
        is_weekend = current_time.weekday() >= 5

        if is_holiday or is_weekend:
            return STATE_ULO_OFF_PEAK

        is_on_peak = 16 <= current_hour < 21
        if is_on_peak:
            return STATE_ULO_ON_PEAK

        return STATE_ULO_MID_PEAK

    @property
    def tou_active_peak(self) -> str:
        """Find the active peak based on the current day and hour.

        According to OEB, weekends and holidays are 24-hour off-peak periods.
        During summer (observed from May 1st to Oct 31st), the morning and evening
        periods are mid-peak, and the afternoon is on-peak. This flips during winter
        time, where morning and evening are on-peak and afternoons are mid-peak.
        """

        if self.coordinator.energy_sector == "natural_gas":
            return STATE_NO_PEAK

        current_time = as_local(now())

        is_holiday = current_time.date() in self.ontario_holidays
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
        """Returns the current peak's rate for electricity companies or the gas supply charge for natural gas companies."""

        company_data = self.coordinator.company_data

        if self.coordinator.energy_sector == "electricity":
            active_peak_mapping = PEAK_KEY_MAPPINGS.get(self.active_peak)

            if active_peak_mapping is not None and active_peak_mapping in company_data:
                return company_data[active_peak_mapping]

        return company_data["gas_supply_charge"]

    @property
    def extra_state_attributes(self) -> dict:
        attributes = {
            "energy_company": self.coordinator.energy_company,
            "energy_sector": self.coordinator.energy_sector,
            "active_peak": self.active_peak,
            "season": "summer" if self.is_summer else "winter",
        }

        attributes.update(self.coordinator.company_data)

        return attributes
