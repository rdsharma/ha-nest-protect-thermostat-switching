"""Helpers for unofficial Nest thermostat state."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import NEST_DOMAIN, THERMOSTAT_UPDATE_SIGNAL_PREFIX
from .pynest.enums import BucketType
from .pynest.models import Bucket, ThermostatData, ThermostatSensor
from .pynest.thermostat_protocol import RemoteComfortSensingSettings

_NORMALIZE_PATTERN = re.compile(r"[^a-z0-9]+")

if TYPE_CHECKING:
    from homeassistant.helpers.area_registry import AreaRegistry


@dataclass(slots=True, frozen=True)
class OfficialThermostatCandidate:
    """An official Home Assistant Nest thermostat device."""

    device_entry_id: str
    device_identifier: tuple[str, ...]
    device_identifier_key: str
    name: str | None
    area_name: str | None


def thermostat_update_signal(device_id: str) -> str:
    """Return the dispatcher signal used for thermostat updates."""
    return f"{THERMOSTAT_UPDATE_SIGNAL_PREFIX}{device_id}"


@callback
def async_official_thermostats(
    hass: HomeAssistant,
) -> dict[str, OfficialThermostatCandidate]:
    """Return official Nest thermostat candidates keyed by Nest device identifier."""
    registry = dr.async_get(hass)
    area_registry = _async_area_registry(hass)
    candidates: dict[str, OfficialThermostatCandidate] = {}

    for device in registry.devices.values():
        identifier = next(
            (
                tuple(identifier)
                for identifier in device.identifiers
                if len(identifier) >= 2 and identifier[0] == NEST_DOMAIN
            ),
            None,
        )
        if identifier is None:
            continue

        model = (device.model or "").lower()
        if model and "thermostat" not in model:
            continue

        candidates[_identifier_key(identifier)] = OfficialThermostatCandidate(
            device_entry_id=device.id,
            device_identifier=identifier,
            device_identifier_key=_identifier_key(identifier),
            name=device.name_by_user or device.name,
            area_name=_device_area_name(area_registry, device.area_id),
        )

    return candidates


def build_thermostats(
    buckets: list[Bucket],
    areas: dict[str, str],
    official_thermostats: dict[str, OfficialThermostatCandidate],
    thermostat_links: dict[str, str] | None = None,
) -> dict[str, ThermostatData]:
    """Build thermostat runtime data from legacy buckets."""
    thermostat_links = thermostat_links or {}
    devices = _buckets_by_type(buckets, BucketType.DEVICE)
    shared = _buckets_by_type(buckets, BucketType.SHARED)
    tracks = _buckets_by_type(buckets, BucketType.TRACK)
    structures = _buckets_by_type(buckets, BucketType.STRUCTURE)
    rcs_settings = _buckets_by_type(buckets, BucketType.RCS_SETTINGS)
    kryptonite = _buckets_by_type(buckets, BucketType.KRYPTONITE)

    structure_by_device = _structure_by_device(structures)
    sensors_by_bucket_id = {
        bucket_id: _build_sensor(sensor_bucket, areas)
        for bucket_id, sensor_bucket in kryptonite.items()
    }

    thermostats: dict[str, ThermostatData] = {}
    for bucket_id, device_bucket in devices.items():
        value = dict(device_bucket.value)
        if shared_bucket := shared.get(bucket_id):
            value.update(shared_bucket.value)

        where_id = value.get("where_id")
        resource_id = value.get("resource_id") or f"DEVICE_{bucket_id}"
        thermostat = ThermostatData(
            device_id=resource_id,
            name=_thermostat_name(value, areas.get(where_id)),
            where_name=areas.get(where_id),
            where_id=where_id,
            structure_id=value.get("structure_id") or structure_by_device.get(bucket_id),
            serial_number=value.get("serial_number"),
            available=_track_online(tracks.get(bucket_id)),
        )

        if rcs_bucket := rcs_settings.get(bucket_id):
            for sensor_ref in rcs_bucket.value.get("associated_rcs_sensors", []):
                sensor = sensors_by_bucket_id.get(_sensor_bucket_id(sensor_ref))
                if sensor is not None:
                    thermostat.sensors[sensor.sensor_id] = sensor

        if official := _match_official_thermostat(
            thermostat, official_thermostats, thermostat_links
        ):
            thermostat.official_device_identifier = official.device_identifier
            thermostat.official_device_entry_id = official.device_entry_id

        thermostats[thermostat.device_id] = thermostat

    return thermostats


def apply_remote_comfort_sensing(
    thermostat: ThermostatData,
    settings: RemoteComfortSensingSettings,
    devices: dict[str, Bucket],
    areas: dict[str, str],
) -> None:
    """Merge live remote comfort sensing state into a thermostat model."""
    thermostat.remote_comfort_sensing = settings

    for sensor_metadata in settings.associated_sensors:
        if sensor_metadata.resource_id in thermostat.sensors:
            continue

        bucket_id = sensor_metadata.resource_id.removeprefix("DEVICE_")
        sensor_bucket = devices.get(f"kryptonite.{bucket_id}")
        if sensor_bucket is None:
            thermostat.sensors[sensor_metadata.resource_id] = ThermostatSensor(
                sensor_id=sensor_metadata.resource_id,
                name=sensor_metadata.resource_id,
            )
            continue

        sensor = _build_sensor(sensor_bucket, areas)
        thermostat.sensors[sensor.sensor_id] = sensor


def official_thermostat_options(
    official_thermostats: dict[str, OfficialThermostatCandidate],
) -> dict[str, str]:
    """Build option labels for thermostat pairing."""
    options: dict[str, str] = {}
    for identifier_key, thermostat in official_thermostats.items():
        label = (
            thermostat.name
            or thermostat.area_name
            or thermostat.device_identifier[-1]
        )
        if thermostat.area_name and thermostat.area_name not in label:
            label = f"{label} ({thermostat.area_name})"
        options[identifier_key] = label
    return options


def _buckets_by_type(
    buckets: list[Bucket], bucket_type: BucketType
) -> dict[str, Bucket]:
    return {
        _bucket_id(bucket.object_key): bucket
        for bucket in buckets
        if bucket.type == bucket_type
    }


def _bucket_id(object_key: str) -> str:
    return object_key.split(".", 1)[1]


def _structure_by_device(structures: dict[str, Bucket]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for structure_id, structure_bucket in structures.items():
        for swarm_member in structure_bucket.value.get("swarm", []):
            swarm_type, _, bucket_id = swarm_member.partition(".")
            if swarm_type == BucketType.DEVICE:
                mapping[bucket_id] = structure_id
    return mapping


def _build_sensor(sensor_bucket: Bucket, areas: dict[str, str]) -> ThermostatSensor:
    value = sensor_bucket.value
    where_id = value.get("where_id")
    sensor_id = value.get("resource_id") or f"DEVICE_{_bucket_id(sensor_bucket.object_key)}"
    name = (
        value.get("name")
        or value.get("description")
        or areas.get(where_id)
        or value.get("serial_number")
        or sensor_id
    )
    return ThermostatSensor(
        sensor_id=sensor_id,
        name=name,
        bucket_key=sensor_bucket.object_key,
        current_temperature=value.get("current_temperature"),
    )


def _match_official_thermostat(
    thermostat: ThermostatData,
    official_thermostats: dict[str, OfficialThermostatCandidate],
    thermostat_links: dict[str, str],
) -> OfficialThermostatCandidate | None:
    manual_identifier = thermostat_links.get(thermostat.device_id)
    if manual_identifier:
        return official_thermostats.get(manual_identifier)

    candidates = list(official_thermostats.values())
    if len(candidates) == 1:
        return candidates[0]

    thermostat_name = _normalize(thermostat.name)
    thermostat_area = _normalize(thermostat.where_name)

    if thermostat_name:
        matches = [
            candidate
            for candidate in candidates
            if _normalize(candidate.name) == thermostat_name
        ]
        if len(matches) == 1:
            return matches[0]

    if thermostat_area:
        matches = [
            candidate
            for candidate in candidates
            if _normalize(candidate.area_name) == thermostat_area
        ]
        if len(matches) == 1:
            return matches[0]

    return None


def _identifier_key(identifier: tuple[str, ...]) -> str:
    """Return a stable, serializable key for an official Nest identifier."""
    return "\x1f".join(identifier)


def _device_area_name(
    area_registry: AreaRegistry | Any | None, area_id: str | None
) -> str | None:
    """Resolve a device area id to a display name."""
    if area_registry is None or area_id is None:
        return None
    if area := area_registry.async_get_area(area_id):
        return area.name
    return None


def _async_area_registry(hass: HomeAssistant) -> AreaRegistry | Any | None:
    """Return the area registry when available."""
    try:
        from homeassistant.helpers import area_registry
    except ImportError:
        return None
    return area_registry.async_get(hass)


def _sensor_bucket_id(sensor_ref: str) -> str:
    if sensor_ref.startswith("kryptonite."):
        return sensor_ref.split(".", 1)[1]
    if sensor_ref.startswith("DEVICE_"):
        return sensor_ref.removeprefix("DEVICE_")
    return sensor_ref


def _thermostat_name(value: dict, where_name: str | None) -> str:
    return value.get("name") or value.get("description") or where_name or "Nest Thermostat"


def _track_online(track_bucket: Bucket | None) -> bool:
    if track_bucket is None:
        return True
    return bool(track_bucket.value.get("online", True))


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    return _NORMALIZE_PATTERN.sub("", value.lower())
