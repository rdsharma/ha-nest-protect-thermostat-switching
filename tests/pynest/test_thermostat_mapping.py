"""Tests for thermostat discovery and pairing helpers."""

from __future__ import annotations


def test_build_thermostats_discovers_sensors_and_matches_official_device(
    pynest_import, integration_import
) -> None:
    """Build a thermostat model from legacy buckets."""
    enums = pynest_import("enums")
    models = pynest_import("models")
    thermostat = integration_import("thermostat")

    areas = {
        "where_hall": "Hallway",
        "where_bed": "Bedroom",
        "where_office": "Office",
    }
    buckets = [
        models.Bucket(
            object_key="device.CCA7C1000022A6CF",
            object_revision=1,
            object_timestamp=1,
            value={
                "resource_id": "DEVICE_CCA7C1000022A6CF",
                "name": "Hallway Thermostat",
                "where_id": "where_hall",
                "serial_number": "THERMO123",
            },
            type=enums.BucketType.DEVICE,
        ),
        models.Bucket(
            object_key="track.CCA7C1000022A6CF",
            object_revision=1,
            object_timestamp=1,
            value={"online": True},
            type=enums.BucketType.TRACK,
        ),
        models.Bucket(
            object_key="rcs_settings.CCA7C1000022A6CF",
            object_revision=1,
            object_timestamp=1,
            value={
                "associated_rcs_sensors": [
                    "kryptonite.18B430CE7E5A5C06",
                    "kryptonite.18B430C0E759221E",
                ]
            },
            type=enums.BucketType.RCS_SETTINGS,
        ),
        models.Bucket(
            object_key="kryptonite.18B430CE7E5A5C06",
            object_revision=1,
            object_timestamp=1,
            value={
                "resource_id": "DEVICE_18B430CE7E5A5C06",
                "where_id": "where_bed",
                "serial_number": "SENSOR1",
                "current_temperature": 70.0,
            },
            type=enums.BucketType.KRYPTONITE,
        ),
        models.Bucket(
            object_key="kryptonite.18B430C0E759221E",
            object_revision=1,
            object_timestamp=1,
            value={
                "resource_id": "DEVICE_18B430C0E759221E",
                "where_id": "where_office",
                "serial_number": "SENSOR2",
                "current_temperature": 68.0,
            },
            type=enums.BucketType.KRYPTONITE,
        ),
    ]
    official = {
        "enterprise-device-id": thermostat.OfficialThermostatCandidate(
            device_entry_id="device-entry-id",
            device_identifier=("nest", "enterprise-device-id"),
            device_identifier_key="enterprise-device-id",
            name="Hallway Thermostat",
            area_name="Hallway",
        )
    }

    thermostats = thermostat.build_thermostats(buckets, areas, official)

    discovered = thermostats["DEVICE_CCA7C1000022A6CF"]
    assert discovered.official_device_identifier == ("nest", "enterprise-device-id")
    assert discovered.official_device_entry_id == "device-entry-id"
    assert list(discovered.sensors) == [
        "DEVICE_18B430CE7E5A5C06",
        "DEVICE_18B430C0E759221E",
    ]


def test_manual_links_override_auto_match(pynest_import, integration_import) -> None:
    """Manual links should win when multiple official thermostats exist."""
    enums = pynest_import("enums")
    models = pynest_import("models")
    thermostat = integration_import("thermostat")

    buckets = [
        models.Bucket(
            object_key="device.CCA7C1000022A6CF",
            object_revision=1,
            object_timestamp=1,
            value={
                "resource_id": "DEVICE_CCA7C1000022A6CF",
                "name": "Upstairs",
                "where_id": "where_upstairs",
            },
            type=enums.BucketType.DEVICE,
        )
    ]
    official = {
        "first-id": thermostat.OfficialThermostatCandidate(
            device_entry_id="first-entry",
            device_identifier=("nest", "first-id"),
            device_identifier_key="first-id",
            name="Upstairs",
            area_name="Hallway",
        ),
        "second-id": thermostat.OfficialThermostatCandidate(
            device_entry_id="second-entry",
            device_identifier=("nest", "second-id"),
            device_identifier_key="second-id",
            name="Upstairs",
            area_name="Bedroom",
        ),
    }

    thermostats = thermostat.build_thermostats(
        buckets,
        {"where_upstairs": "Upstairs"},
        official,
        {"DEVICE_CCA7C1000022A6CF": "second-id"},
    )

    assert (
        thermostats["DEVICE_CCA7C1000022A6CF"].official_device_identifier
        == ("nest", "second-id")
    )


def test_build_thermostats_from_observe_uses_remote_comfort_updates(
    pynest_import, integration_import
) -> None:
    """Build thermostat models from observe updates when legacy buckets are absent."""
    models = pynest_import("models")
    protocol = pynest_import("thermostat_protocol")
    thermostat = integration_import("thermostat")

    official = {
        "only-id": thermostat.OfficialThermostatCandidate(
            device_entry_id="device-entry-id",
            device_identifier=("nest", "only-id"),
            device_identifier_key="only-id",
            name="Hallway Thermostat",
            area_name="Hallway",
        )
    }
    devices = {
        "kryptonite.18B430CE7E5A5C06": models.Bucket(
            object_key="kryptonite.18B430CE7E5A5C06",
            object_revision=1,
            object_timestamp=1,
            value={
                "resource_id": "DEVICE_18B430CE7E5A5C06",
                "where_id": "where_bed",
                "serial_number": "SENSOR1",
                "current_temperature": 70.0,
            },
            type="kryptonite",
        )
    }
    updates = [
        protocol.RemoteComfortSensingObserveUpdate(
            thermostat_id="DEVICE_CCA7C1000022A6CF",
            trait_label="remote_comfort_sensing_settings",
            settings=protocol.RemoteComfortSensingSettings(
                rcs_control_mode=1,
                source_type=protocol.RCS_SOURCE_TYPE_SENSOR,
                active_sensor_id="DEVICE_18B430CE7E5A5C06",
                associated_sensors=(
                    protocol.RcsSensorMetadata(
                        resource_id="DEVICE_18B430CE7E5A5C06",
                        vendor_id=9050,
                        product_id=26,
                    ),
                ),
                remembered_sensor_id="DEVICE_18B430CE7E5A5C06",
                raw_payload=b"payload",
            ),
        )
    ]

    thermostats = thermostat.build_thermostats_from_observe(
        updates,
        devices,
        {"where_bed": "Bedroom"},
        official,
    )

    discovered = thermostats["DEVICE_CCA7C1000022A6CF"]
    assert discovered.name == "Hallway Thermostat"
    assert discovered.official_device_identifier == ("nest", "only-id")
    assert list(discovered.sensors) == ["DEVICE_18B430CE7E5A5C06"]
    assert discovered.active_sensor_id == "DEVICE_18B430CE7E5A5C06"
