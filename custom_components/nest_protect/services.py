"""Services for unofficial Nest thermostat extensions."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    ATTR_DURATION_MINUTES,
    ATTR_SELECT_ENTITY,
    ATTR_THERMOSTAT_ID,
    DOMAIN,
    NEST_DOMAIN,
    SERVICE_SET_FAN_TIMER,
)

if TYPE_CHECKING:
    from . import HomeAssistantNestProtectData
    from .pynest.models import ThermostatData

FAN_TRAIT_NAME = "sdm.devices.traits.Fan"
ALLOWED_FAN_TIMER_MINUTES = (0, 15, 30, 45, 60, 120, 240)
SET_FAN_TIMER_SCHEMA = vol.Schema(
    {
        vol.Exclusive(ATTR_SELECT_ENTITY, "thermostat"): cv.entity_id,
        vol.Exclusive(ATTR_THERMOSTAT_ID, "thermostat"): cv.string,
        vol.Required(ATTR_DURATION_MINUTES): vol.In(ALLOWED_FAN_TIMER_MINUTES),
    }
)


def async_register_services(hass: HomeAssistant) -> None:
    """Register domain services."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_FAN_TIMER):
        return

    async def _async_handle_set_fan_timer(call: ServiceCall) -> None:
        thermostat = _resolve_thermostat(hass, call)
        device = _resolve_official_nest_device(hass, thermostat)
        if FAN_TRAIT_NAME not in device.traits:
            raise HomeAssistantError(
                f"Official Nest thermostat {device.name} does not expose fan control"
            )

        duration_minutes = int(call.data[ATTR_DURATION_MINUTES])
        trait = device.traits[FAN_TRAIT_NAME]
        if duration_minutes <= 0:
            await trait.set_timer("OFF")
            return

        await trait.set_timer("ON", duration=duration_minutes * 60)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_FAN_TIMER,
        _async_handle_set_fan_timer,
        schema=SET_FAN_TIMER_SCHEMA,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister domain services."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_FAN_TIMER):
        hass.services.async_remove(DOMAIN, SERVICE_SET_FAN_TIMER)


def _resolve_thermostat(hass: HomeAssistant, call: ServiceCall) -> ThermostatData:
    thermostat_id = call.data.get(ATTR_THERMOSTAT_ID)
    if thermostat_id is None and (select_entity := call.data.get(ATTR_SELECT_ENTITY)):
        state = hass.states.get(select_entity)
        if state is None:
            raise ServiceValidationError(
                f"Unknown select entity for fan timer: {select_entity}"
            )
        thermostat_id = state.attributes.get(ATTR_THERMOSTAT_ID)

    if thermostat_id is None:
        raise ServiceValidationError(
            "Fan timer service requires thermostat_id or select_entity"
        )

    for entry_data in _entry_data_iter(hass):
        if thermostat := entry_data.thermostats.get(thermostat_id):
            return thermostat

    raise ServiceValidationError(f"Unknown Nest Protect thermostat: {thermostat_id}")


def _resolve_official_nest_device(
    hass: HomeAssistant, thermostat: ThermostatData
) -> Any:
    if thermostat.official_device_identifier is None:
        raise HomeAssistantError(
            f"Thermostat {thermostat.device_id} is not paired with an official Nest thermostat"
        )

    nest_device_name = thermostat.official_device_identifier[-1]
    for entry in hass.config_entries.async_loaded_entries(NEST_DOMAIN):
        runtime_data = getattr(entry, "runtime_data", None)
        device_manager = getattr(runtime_data, "device_manager", None)
        if device_manager is None:
            continue
        if device := device_manager.devices.get(nest_device_name):
            return device

    raise HomeAssistantError(
        f"Unable to find official Nest thermostat device {nest_device_name}"
    )


def _entry_data_iter(hass: HomeAssistant) -> Iterable[HomeAssistantNestProtectData]:
    for value in hass.data.get(DOMAIN, {}).values():
        if hasattr(value, "thermostats") and hasattr(value, "client"):
            yield value
