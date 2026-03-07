"""Select platform tests."""

from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nest_protect import HomeAssistantNestProtectData
from custom_components.nest_protect.const import DOMAIN
from custom_components.nest_protect.pynest.models import ThermostatData, ThermostatSensor
from custom_components.nest_protect.pynest.thermostat_protocol import (
    RCS_SOURCE_TYPE_SENSOR,
    RemoteComfortSensingSettings,
)
from custom_components.nest_protect.select import (
    NestThermostatSensorSelect,
    async_setup_entry,
)
from custom_components.nest_protect.thermostat import thermostat_discovery_signal


async def test_async_setup_entry_adds_late_discovered_thermostat_select(hass) -> None:
    """Late thermostat discovery should add a select entity."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"refresh_token": "token"})
    config_entry.add_to_hass(hass)

    thermostat = ThermostatData(
        device_id="DEVICE_CCA7C1000022A6CF",
        name="Living Room",
        where_name="Living Room",
        where_id=None,
        structure_id=None,
    )
    data = HomeAssistantNestProtectData(
        devices={},
        areas={},
        client=object(),
        thermostats={},
    )
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = data

    added_entities = []

    def async_add_devices(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, config_entry, async_add_devices)
    assert added_entities == []

    data.thermostats[thermostat.device_id] = thermostat
    async_dispatcher_send(
        hass,
        thermostat_discovery_signal(config_entry.entry_id),
        thermostat.device_id,
    )
    await hass.async_block_till_done()

    assert len(added_entities) == 1
    assert isinstance(added_entities[0], NestThermostatSensorSelect)
    assert added_entities[0].unique_id == "DEVICE_CCA7C1000022A6CF-active_temperature_sensor"


async def test_thermostat_select_exposes_sensor_metadata_attributes(hass) -> None:
    """The thermostat select should expose remote sensor temperatures for the frontend."""
    thermostat = ThermostatData(
        device_id="DEVICE_CCA7C1000022A6CF",
        name="Living Room",
        where_name="Living Room",
        where_id=None,
        structure_id=None,
        sensors={
            "DEVICE_18B430CE7E5A5C06": ThermostatSensor(
                sensor_id="DEVICE_18B430CE7E5A5C06",
                name="Master Bedroom",
                current_temperature=21.4,
            )
        },
        remote_comfort_sensing=RemoteComfortSensingSettings(
            rcs_control_mode=1,
            source_type=RCS_SOURCE_TYPE_SENSOR,
            active_sensor_id="DEVICE_18B430CE7E5A5C06",
            associated_sensors=(),
            remembered_sensor_id="DEVICE_18B430CE7E5A5C06",
            raw_payload=b"payload",
        ),
    )
    data = HomeAssistantNestProtectData(
        devices={},
        areas={},
        client=object(),
        thermostats={thermostat.device_id: thermostat},
    )

    entity = NestThermostatSensorSelect(data, thermostat.device_id)
    entity.hass = hass

    assert entity.extra_state_attributes == {
        "thermostat_id": "DEVICE_CCA7C1000022A6CF",
        "active_sensor_id": "DEVICE_18B430CE7E5A5C06",
        "remembered_sensor_id": "DEVICE_18B430CE7E5A5C06",
        "sensor_options": [
            {
                "option": "Master Bedroom",
                "sensor_id": "DEVICE_18B430CE7E5A5C06",
                "name": "Master Bedroom",
                "temperature": 21.4,
            }
        ],
    }
