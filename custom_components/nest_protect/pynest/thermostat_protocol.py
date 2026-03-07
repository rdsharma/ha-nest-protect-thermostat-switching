"""Helpers for Nest thermostat remote comfort sensing protocol."""

from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from typing import Final

from google.protobuf.any_pb2 import Any as ProtobufAny

from . import _nest_gateway_pb2 as gateway_pb2
from . import _nest_thermostat_pb2 as thermostat_pb2


REMOTE_COMFORT_SENSING_TYPE_URL: Final = (
    "type.nestlabs.com/nest.trait.hvac.RemoteComfortSensingSettingsTrait"
)
REMOTE_COMFORT_SENSING_OBSERVE_TYPE: Final = (
    "nest.trait.hvac.RemoteComfortSensingSettingsTrait"
)
REMOTE_COMFORT_SENSING_TRAIT_LABEL: Final = "remote_comfort_sensing_settings"
RCS_SOURCE_TYPE_THERMOSTAT: Final = 1
RCS_SOURCE_TYPE_SENSOR: Final = 2
OBSERVE_STATE_TYPES: Final = (2, 1)
THERMOSTAT_OPTION: Final = "Thermostat"


@dataclass(slots=True, frozen=True)
class RcsSensorMetadata:
    """A remote comfort sensing sensor entry."""

    resource_id: str
    vendor_id: int
    product_id: int


@dataclass(slots=True, frozen=True)
class RemoteComfortSensingSettings:
    """Remote comfort sensing settings trait."""

    rcs_control_mode: int
    source_type: int
    active_sensor_id: str | None
    associated_sensors: tuple[RcsSensorMetadata, ...]
    remembered_sensor_id: str | None
    raw_payload: bytes


@dataclass(slots=True, frozen=True)
class RemoteComfortSensingObserveUpdate:
    """An observe update for a thermostat remote comfort trait."""

    thermostat_id: str
    trait_label: str
    settings: RemoteComfortSensingSettings


def encode_observe_request(trait_types: tuple[str, ...] | list[str]) -> bytes:
    """Encode a minimal Observe request."""
    request = gateway_pb2.ObserveRequest()
    request.state_types_list.extend(OBSERVE_STATE_TYPES)
    for trait_type in trait_types:
        request.trait_type_params.add(trait_type=trait_type)
    return request.SerializeToString()


def decode_observe_stream_body(
    payload: bytes,
) -> list[RemoteComfortSensingObserveUpdate]:
    """Decode a grpc-web Observe stream body."""
    stream_body = gateway_pb2.StreamBody()
    stream_body.ParseFromString(payload)
    updates: list[RemoteComfortSensingObserveUpdate] = []
    for message in stream_body.message:
        response = gateway_pb2.ObserveResponse()
        response.ParseFromString(message)
        for trait_state in response.trait_states:
            if (
                trait_state.trait_id.trait_label != REMOTE_COMFORT_SENSING_TRAIT_LABEL
                or trait_state.patch.values.type_url != REMOTE_COMFORT_SENSING_TYPE_URL
            ):
                continue

            settings = decode_remote_comfort_sensing_settings(
                trait_state.patch.values.value
            )
            updates.append(
                RemoteComfortSensingObserveUpdate(
                    thermostat_id=trait_state.trait_id.resource_id,
                    trait_label=trait_state.trait_id.trait_label,
                    settings=settings,
                )
            )

    return updates


def decode_observe_buffer(
    buffer: bytes,
) -> tuple[list[RemoteComfortSensingObserveUpdate], bytes]:
    """Decode one or more buffered base64 grpc-web messages."""
    updates: list[RemoteComfortSensingObserveUpdate] = []

    while buffer:
        try:
            decoded = b64decode(buffer, validate=True)
        except ValueError:
            break

        try:
            updates.extend(decode_observe_stream_body(decoded))
        except Exception:  # pylint: disable=broad-except
            break

        buffer = b""

    return updates, buffer


def decode_remote_comfort_sensing_settings(
    payload: bytes,
) -> RemoteComfortSensingSettings:
    """Decode RemoteComfortSensingSettingsTrait bytes."""
    message = thermostat_pb2.RemoteComfortSensingSettingsTrait()
    message.ParseFromString(payload)

    return RemoteComfortSensingSettings(
        rcs_control_mode=message.rcs_control_mode,
        source_type=message.active_rcs_selection.rcs_source_type,
        active_sensor_id=_resource_id(message.active_rcs_selection.active_rcs_sensor),
        associated_sensors=tuple(
            RcsSensorMetadata(
                resource_id=_resource_id(sensor.device_id) or "",
                vendor_id=sensor.vendor_id,
                product_id=sensor.product_id,
            )
            for sensor in message.associated_rcs_sensors
            if _resource_id(sensor.device_id)
        ),
        remembered_sensor_id=_resource_id(
            message.remembered_remote_sensor_selection.sensor
        ),
        raw_payload=payload,
    )


def encode_remote_comfort_sensing_settings(
    settings: RemoteComfortSensingSettings,
) -> bytes:
    """Encode RemoteComfortSensingSettingsTrait bytes."""
    message = thermostat_pb2.RemoteComfortSensingSettingsTrait()
    message.rcs_control_mode = settings.rcs_control_mode
    message.active_rcs_selection.rcs_source_type = settings.source_type
    message.rcs_control_schedule.CopyFrom(thermostat_pb2.EmptyMessage())

    if settings.active_sensor_id:
        message.active_rcs_selection.active_rcs_sensor.resource_id = (
            settings.active_sensor_id
        )
    elif settings.source_type == RCS_SOURCE_TYPE_THERMOSTAT:
        message.active_rcs_selection.active_rcs_sensor.CopyFrom(
            thermostat_pb2.ResourceId()
        )

    for sensor in settings.associated_sensors:
        message.associated_rcs_sensors.add(
            device_id=thermostat_pb2.ResourceId(resource_id=sensor.resource_id),
            vendor_id=sensor.vendor_id,
            product_id=sensor.product_id,
        )

    if settings.remembered_sensor_id:
        message.remembered_remote_sensor_selection.sensor.resource_id = (
            settings.remembered_sensor_id
        )

    return message.SerializeToString()


def encode_batch_update_state_request(
    thermostat_id: str, request_id: str, trait_payload: bytes
) -> bytes:
    """Encode a BatchUpdateState request for remote comfort sensing."""
    request = gateway_pb2.BatchUpdateStateRequest()
    request.trait_set_properties.add(
        trait_id=gateway_pb2.TraitInstanceId(
            resource_id=thermostat_id,
            trait_label=REMOTE_COMFORT_SENSING_TRAIT_LABEL,
            request_id=request_id,
        ),
        property=ProtobufAny(
            type_url=REMOTE_COMFORT_SENSING_TYPE_URL,
            value=trait_payload,
        ),
    )
    return request.SerializeToString()


def update_remote_comfort_sensing_settings(
    settings: RemoteComfortSensingSettings, target_sensor_id: str | None
) -> RemoteComfortSensingSettings:
    """Return updated settings for the requested target sensor."""
    return decode_remote_comfort_sensing_settings(
        update_remote_comfort_sensing_payload(settings.raw_payload, target_sensor_id)
    )


def update_remote_comfort_sensing_payload(
    payload: bytes, target_sensor_id: str | None
) -> bytes:
    """Mutate a live trait payload while preserving unknown fields."""
    message = thermostat_pb2.RemoteComfortSensingSettingsTrait()
    message.ParseFromString(payload)

    if target_sensor_id is None:
        message.active_rcs_selection.rcs_source_type = RCS_SOURCE_TYPE_THERMOSTAT
        message.active_rcs_selection.active_rcs_sensor.CopyFrom(
            thermostat_pb2.ResourceId()
        )
    else:
        message.active_rcs_selection.rcs_source_type = RCS_SOURCE_TYPE_SENSOR
        message.active_rcs_selection.active_rcs_sensor.resource_id = target_sensor_id
        message.remembered_remote_sensor_selection.sensor.resource_id = target_sensor_id

    return message.SerializeToString()


def _resource_id(resource_id: thermostat_pb2.ResourceId) -> str | None:
    value = resource_id.resource_id
    return value or None
