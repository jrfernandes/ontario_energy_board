"""The Ontario Energy Board component."""

from functools import partial
import logging
from typing import Final

from holidays import country_holidays
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import SetupPhases, async_pause_setup

from .const import CONF_ULO_ENABLED, DOMAIN
from .coordinator import OntarioEnergyBoardDataUpdateCoordinator

_LOGGER: Final = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Ontario Energy Board component."""
    hass.data.setdefault(DOMAIN, {})

    # Importing `holidays` builds its data tables and is slow enough to block
    # the event loop, so it is pushed to the import executor. Doing it here
    # rather than in each platform keeps it to once per config entry.
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

    coordinator = OntarioEnergyBoardDataUpdateCoordinator(
        hass, config_entry, ontario_holidays
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

        _LOGGER.debug("Unloading of %s successful", config_entry.title)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry to add ULO enabled to false."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_ULO_ENABLED: False},
            version=2,
        )

    _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True
