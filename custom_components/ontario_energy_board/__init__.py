"""The Ontario Energy Board component."""

from functools import partial
import logging
from typing import Final

from holidays import country_holidays
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import SetupPhases, async_pause_setup

from .const import CONF_ULO_ENABLED, DOMAIN
from .coordinator import OntarioEnergyBoardDataUpdateCoordinator

_LOGGER: Final = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


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

    # Changing the rate plan from the options changes which rates apply, so the
    # entry is rebuilt rather than left reporting the previous plan.
    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the entry after its options change."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

        _LOGGER.debug("Unloading of %s successful", config_entry.title)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Bring an older config entry up to the current layout."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # Version 1 predates the rate plan option.
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_ULO_ENABLED: False},
            version=2,
        )

    if config_entry.version == 2:
        await _async_migrate_to_stable_identity(hass, config_entry)

    _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True


async def _async_migrate_to_stable_identity(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Re-key entities on the entry id rather than the company and rate plan.

    Version 2 built the entry's unique id from the company name and whether
    Ultra-Low Overnight was enabled, and every entity id from that. Both can
    legitimately change: a distributor is renamed or merged, or the account
    moves between rate plans. A unique id cannot change without orphaning its
    entity, so that identity had to go.

    The entry id is assigned once and never changes. Renaming a unique id in
    the registry keeps the row, and with it the entity id and its history.
    """
    previous = config_entry.unique_id

    if previous:

        def migrate(entity: er.RegistryEntry) -> dict[str, str] | None:
            if entity.unique_id == previous:
                # The single sensor that predates the device layout.
                key = "current_rate"
            elif entity.unique_id.startswith(f"{previous}_"):
                key = entity.unique_id[len(previous) + 1 :]
            else:
                return None

            return {"new_unique_id": f"{config_entry.entry_id}_{key}"}

        await er.async_migrate_entries(hass, config_entry.entry_id, migrate)

    # Duplicates are now detected from the company and rate plan an entry
    # currently holds, which its unique id can no longer speak for.
    hass.config_entries.async_update_entry(config_entry, unique_id=None, version=3)
