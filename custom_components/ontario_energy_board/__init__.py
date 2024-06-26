"""The Ontario Energy Board component."""

from typing import Final
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_ULO_ENABLED
from .coordinator import OntarioEnergyBoardDataUpdateCoordinator

_LOGGER: Final = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up the Ontario Energy Board component."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = OntarioEnergyBoardDataUpdateCoordinator(hass)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        config_entry, Platform.SENSOR
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

        _LOGGER.debug("Unloading of %s successful", config_entry.title)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old entry to add ULO enabled to false."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new = {**config_entry.data}
        new[CONF_ULO_ENABLED] = False

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, data=new)

    _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True
