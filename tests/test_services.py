"""Service tests for Nest thermostat extensions."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from custom_components.nest_protect import HomeAssistantNestProtectData
from custom_components.nest_protect.const import (
    ATTR_DURATION_MINUTES,
    ATTR_SELECT_ENTITY,
    DOMAIN,
    SERVICE_SET_FAN_TIMER,
)
from custom_components.nest_protect.pynest.models import ThermostatData
from custom_components.nest_protect.services import (
    FAN_TRAIT_NAME,
    async_register_services,
)


async def test_set_fan_timer_service_uses_official_nest_device(hass) -> None:
    """The fan timer service should call the paired official Nest fan trait."""
    thermostat = ThermostatData(
        device_id="DEVICE_CCA7C1000022A6CF",
        name="Living Room",
        where_name="Living Room",
        where_id=None,
        structure_id=None,
        official_device_identifier=("nest", "enterprises/test/devices/thermostat-1"),
    )
    hass.data.setdefault(DOMAIN, {})["entry-id"] = HomeAssistantNestProtectData(
        devices={},
        areas={},
        client=object(),
        thermostats={thermostat.device_id: thermostat},
    )
    hass.states.async_set(
        "select.living_room_active_temperature_sensor",
        "Thermostat",
        {"thermostat_id": thermostat.device_id},
    )

    fan_trait = SimpleNamespace(set_timer=AsyncMock())
    nest_device = SimpleNamespace(
        name="enterprises/test/devices/thermostat-1",
        traits={FAN_TRAIT_NAME: fan_trait},
    )
    nest_entry = SimpleNamespace(
        runtime_data=SimpleNamespace(
            device_manager=SimpleNamespace(
                devices={"enterprises/test/devices/thermostat-1": nest_device}
            )
        )
    )

    async_register_services(hass)

    with patch.object(hass.config_entries, "async_loaded_entries", return_value=[nest_entry]):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_FAN_TIMER,
            {
                ATTR_SELECT_ENTITY: "select.living_room_active_temperature_sensor",
                ATTR_DURATION_MINUTES: 15,
            },
            blocking=True,
        )

    fan_trait.set_timer.assert_awaited_once_with("ON", duration=900)


async def test_set_fan_timer_service_turns_fan_off(hass) -> None:
    """A zero minute fan timer request should disable the timer."""
    thermostat = ThermostatData(
        device_id="DEVICE_CCA7C1000022A6CF",
        name="Living Room",
        where_name="Living Room",
        where_id=None,
        structure_id=None,
        official_device_identifier=("nest", "enterprises/test/devices/thermostat-1"),
    )
    hass.data.setdefault(DOMAIN, {})["entry-id"] = HomeAssistantNestProtectData(
        devices={},
        areas={},
        client=object(),
        thermostats={thermostat.device_id: thermostat},
    )

    fan_trait = SimpleNamespace(set_timer=AsyncMock())
    nest_device = SimpleNamespace(
        name="enterprises/test/devices/thermostat-1",
        traits={FAN_TRAIT_NAME: fan_trait},
    )
    nest_entry = SimpleNamespace(
        runtime_data=SimpleNamespace(
            device_manager=SimpleNamespace(
                devices={"enterprises/test/devices/thermostat-1": nest_device}
            )
        )
    )

    async_register_services(hass)

    with patch.object(hass.config_entries, "async_loaded_entries", return_value=[nest_entry]):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_FAN_TIMER,
            {
                "thermostat_id": thermostat.device_id,
                ATTR_DURATION_MINUTES: 0,
            },
            blocking=True,
        )

    fan_trait.set_timer.assert_awaited_once_with("OFF")
