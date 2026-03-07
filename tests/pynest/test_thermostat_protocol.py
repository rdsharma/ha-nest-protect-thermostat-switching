"""Tests for thermostat protocol helpers."""

from __future__ import annotations


INTERNAL_TRAIT_HEX = (
    "08011204080112001a0022200a190a174445564943455f31384234333043453745354135433036"
    "10da46181a22200a190a174445564943455f3138423433304330453735393232314510da46181a"
    "321b12190a174445564943455f31384234333043453745354135433036"
)
THERMOSTAT_ID = "DEVICE_CCA7C1000022A6CF"
SENSOR_A = "DEVICE_18B430CE7E5A5C06"
SENSOR_B = "DEVICE_18B430C0E759221E"


def test_remote_comfort_sensing_round_trip_is_lossless(pynest_import) -> None:
    """A parsed live payload should serialize back to the same bytes."""
    thermostat_pb2 = pynest_import("_nest_thermostat_pb2")

    raw = bytes.fromhex(INTERNAL_TRAIT_HEX)
    message = thermostat_pb2.RemoteComfortSensingSettingsTrait()
    message.ParseFromString(raw)

    assert message.SerializeToString() == raw


def test_decode_internal_sensor_payload(pynest_import) -> None:
    """Decode the captured internal sensor payload."""
    protocol = pynest_import("thermostat_protocol")

    settings = protocol.decode_remote_comfort_sensing_settings(
        bytes.fromhex(INTERNAL_TRAIT_HEX)
    )

    assert settings.rcs_control_mode == 1
    assert settings.source_type == protocol.RCS_SOURCE_TYPE_THERMOSTAT
    assert settings.active_sensor_id is None
    assert settings.remembered_sensor_id == SENSOR_A
    assert [sensor.resource_id for sensor in settings.associated_sensors] == [
        SENSOR_A,
        SENSOR_B,
    ]


def test_switch_to_remote_sensor_updates_active_and_remembered(pynest_import) -> None:
    """Switching to a remote sensor should update both remote fields."""
    protocol = pynest_import("thermostat_protocol")

    raw = protocol.update_remote_comfort_sensing_payload(
        bytes.fromhex(INTERNAL_TRAIT_HEX), SENSOR_B
    )
    settings = protocol.decode_remote_comfort_sensing_settings(raw)

    assert settings.source_type == protocol.RCS_SOURCE_TYPE_SENSOR
    assert settings.active_sensor_id == SENSOR_B
    assert settings.remembered_sensor_id == SENSOR_B
    assert [sensor.resource_id for sensor in settings.associated_sensors] == [
        SENSOR_A,
        SENSOR_B,
    ]


def test_switch_to_thermostat_preserves_captured_payload(pynest_import) -> None:
    """Switching to thermostat from an internal-state payload should be a no-op."""
    protocol = pynest_import("thermostat_protocol")

    raw = bytes.fromhex(INTERNAL_TRAIT_HEX)
    assert protocol.update_remote_comfort_sensing_payload(raw, None) == raw


def test_encode_batch_update_state_request(pynest_import) -> None:
    """Encode a BatchUpdateState request with the expected identifiers."""
    gateway_pb2 = pynest_import("_nest_gateway_pb2")
    protocol = pynest_import("thermostat_protocol")

    request = gateway_pb2.BatchUpdateStateRequest()
    request.ParseFromString(
        protocol.encode_batch_update_state_request(
            THERMOSTAT_ID,
            "test-request-id",
            bytes.fromhex(INTERNAL_TRAIT_HEX),
        )
    )

    update = request.trait_set_properties[0]
    assert update.trait_id.resource_id == THERMOSTAT_ID
    assert update.trait_id.trait_label == protocol.REMOTE_COMFORT_SENSING_TRAIT_LABEL
    assert update.trait_id.request_id == "test-request-id"
    assert update.property.type_url == protocol.REMOTE_COMFORT_SENSING_TYPE_URL
    assert update.property.value == bytes.fromhex(INTERNAL_TRAIT_HEX)
