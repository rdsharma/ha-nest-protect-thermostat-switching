"""Select platform for Nest Protect."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import EntityCategory

from . import HomeAssistantNestProtectData
from .const import ATTRIBUTION, DOMAIN, LOGGER, NEST_DOMAIN
from .entity import NestDescriptiveEntity
from .pynest.models import ThermostatData
from .pynest.thermostat_protocol import (
    RCS_SOURCE_TYPE_SENSOR,
    THERMOSTAT_OPTION,
)
from .thermostat import thermostat_update_signal


@dataclass
class NestProtectSelectDescription(SelectEntityDescription):
    """Class to describe an Nest Protect sensor."""


BRIGHTNESS_TO_PRESET: dict[str, str] = {1: "low", 2: "medium", 3: "high"}

PRESET_TO_BRIGHTNESS = {v: k for k, v in BRIGHTNESS_TO_PRESET.items()}


SENSOR_DESCRIPTIONS: list[SelectEntityDescription] = [
    NestProtectSelectDescription(
        key="night_light_brightness",
        translation_key="night_light_brightness",
        name="Brightness",
        icon="mdi:lightbulb-on",
        options=[*PRESET_TO_BRIGHTNESS],
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up the Nest Protect sensors from a config entry."""

    data: HomeAssistantNestProtectData = hass.data[DOMAIN][entry.entry_id]
    entities: list[SelectEntity] = []

    SUPPORTED_KEYS: dict[str, NestProtectSelectDescription] = {
        description.key: description for description in SENSOR_DESCRIPTIONS
    }

    for device in data.devices.values():
        for key in device.value:
            if description := SUPPORTED_KEYS.get(key):
                entities.append(
                    NestProtectSelect(device, description, data.areas, data.client)
                )

    for thermostat in data.thermostats.values():
        entities.append(NestThermostatSensorSelect(data, thermostat.device_id))

    async_add_devices(entities)


class NestProtectSelect(NestDescriptiveEntity, SelectEntity):
    """Representation of a Nest Protect Select."""

    entity_description: NestProtectSelectDescription

    @property
    def current_option(self) -> str:
        """Return the selected entity option to represent the entity state."""
        state = self.bucket.value.get(self.entity_description.key)
        return BRIGHTNESS_TO_PRESET.get(state)

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return self.entity_description.options

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        select = PRESET_TO_BRIGHTNESS.get(option)

        objects = [
            {
                "object_key": self.bucket.object_key,
                "op": "MERGE",
                "value": {
                    self.entity_description.key: select,
                },
            }
        ]

        if not self.client.nest_session or self.client.nest_session.is_expired():
            if not self.client.auth or self.client.auth.is_expired():
                await self.client.get_access_token()

            await self.client.authenticate(self.client.auth.access_token)

        result = await self.client.update_objects(
            self.client.nest_session.access_token,
            self.client.nest_session.userid,
            self.client.transport_url,
            objects,
        )

        LOGGER.debug(result)


class NestThermostatSensorSelect(SelectEntity):
    """Representation of a thermostat active sensor selector."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_name = "Active temperature sensor"
    _attr_icon = "mdi:thermometer-auto"

    def __init__(self, data: HomeAssistantNestProtectData, thermostat_id: str) -> None:
        """Initialize the thermostat select."""
        self._data = data
        self._thermostat_id = thermostat_id
        thermostat = self.thermostat
        self._attr_unique_id = f"{thermostat.device_id}-active_temperature_sensor"
        self._attr_attribution = ATTRIBUTION
        self._attr_device_info = self._build_device_info(thermostat)

    @property
    def thermostat(self) -> ThermostatData:
        """Return the current thermostat model."""
        return self._data.thermostats[self._thermostat_id]

    @property
    def available(self) -> bool:
        """Return availability."""
        return (
            self.thermostat.available
            and self.thermostat.remote_comfort_sensing is not None
        )

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        settings = self.thermostat.remote_comfort_sensing
        if settings is None:
            return None
        if (
            settings.source_type != RCS_SOURCE_TYPE_SENSOR
            or settings.active_sensor_id is None
        ):
            return THERMOSTAT_OPTION
        return self._option_by_sensor_id().get(
            settings.active_sensor_id, THERMOSTAT_OPTION
        )

    @property
    def options(self) -> list[str]:
        """Return the selectable options."""
        return [THERMOSTAT_OPTION, *self._sensor_options()]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        settings = self.thermostat.remote_comfort_sensing
        if settings is None:
            raise ValueError("Thermostat observe state is not loaded yet")

        target_sensor_id = None
        if option != THERMOSTAT_OPTION:
            target_sensor_id = self._sensor_id_by_option()[option]

        self.thermostat.remote_comfort_sensing = (
            await self._data.client.async_set_active_temperature_sensor(
                self.thermostat.device_id,
                settings,
                target_sensor_id,
            )
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register dispatcher update callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                thermostat_update_signal(self._thermostat_id),
                self._async_handle_update,
            )
        )

    def _async_handle_update(self, thermostat: ThermostatData) -> None:
        """Handle thermostat updates."""
        self._data.thermostats[self._thermostat_id] = thermostat
        self.async_write_ha_state()

    def _sensor_options(self) -> list[str]:
        return list(self._sensor_id_by_option())

    def _sensor_id_by_option(self) -> dict[str, str]:
        counts = Counter(
            sensor.name or sensor.sensor_id
            for sensor in self.thermostat.sensors.values()
        )
        options: dict[str, str] = {}
        for sensor in self.thermostat.sensors.values():
            label = sensor.name or sensor.sensor_id
            if counts[label] > 1:
                label = f"{label} ({sensor.sensor_id[-4:]})"
            options[label] = sensor.sensor_id
        return options

    def _option_by_sensor_id(self) -> dict[str, str]:
        return {
            sensor_id: option
            for option, sensor_id in self._sensor_id_by_option().items()
        }

    def _build_device_info(self, thermostat: ThermostatData) -> DeviceInfo:
        if thermostat.official_device_identifier:
            return DeviceInfo(
                identifiers={thermostat.official_device_identifier}
            )

        return DeviceInfo(
            identifiers={(DOMAIN, thermostat.device_id)},
            manufacturer="Google",
            model="Thermostat",
            name=thermostat.name,
            suggested_area=thermostat.where_name,
        )
