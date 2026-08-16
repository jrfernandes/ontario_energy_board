"""Sensor integration for Ontario Energy Board."""

from functools import partial

from holidays import country_holidays
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.setup import SetupPhases, async_pause_setup
from homeassistant.util.dt import as_local, now

from . import peaks
from .common import get_energy_sector_metadata
from .const import DOMAIN, PEAK_KEY_MAPPINGS, SECTOR_ELECTRICITY


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ontario Energy Board sensors."""

    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Importing `holidays` builds its data tables and is slow enough to block
    # the event loop, so it is pushed to the import executor.
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

    async_add_entities(
        [OntarioEnergyBoardSensor(coordinator, entry.unique_id, ontario_holidays)]
    )


class OntarioEnergyBoardSensor(CoordinatorEntity, SensorEntity):
    """Sensor object for Ontario Energy Board.

    The peak rules themselves live in `peaks`, which knows nothing about Home
    Assistant. This class only supplies the current moment and the coordinator's
    configuration to them.
    """

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator, entity_unique_id, ontario_holidays) -> None:
        super().__init__(coordinator)

        energy_company_metadata = get_energy_sector_metadata(coordinator.energy_sector)

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
        return peaks.is_summer(as_local(now()))

    @property
    def ulo_active_peak(self) -> str:
        """The active peak under the Ultra-Low Overnight plan."""
        return peaks.active_peak(
            as_local(now()),
            self.ontario_holidays,
            energy_sector=self.coordinator.energy_sector,
            ulo_enabled=True,
        )

    @property
    def tou_active_peak(self) -> str:
        """The active peak under the Time-of-Use plan."""
        return peaks.active_peak(
            as_local(now()),
            self.ontario_holidays,
            energy_sector=self.coordinator.energy_sector,
            ulo_enabled=False,
        )

    @property
    def active_peak(self) -> str:
        """The active peak under the plan this entry is configured for."""
        return peaks.active_peak(
            as_local(now()),
            self.ontario_holidays,
            energy_sector=self.coordinator.energy_sector,
            ulo_enabled=self.coordinator.ulo_enabled,
        )

    @property
    def native_value(self) -> float | str:
        """Returns the current peak's rate for electricity companies or the gas supply charge for natural gas companies."""

        company_data = self.coordinator.company_data

        if self.coordinator.energy_sector == SECTOR_ELECTRICITY:
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
