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


def test_single_official_candidate_is_not_reused_for_multiple_thermostats(
    pynest_import, integration_import
) -> None:
    """A single official thermostat should not auto-link to multiple unofficial ones."""
    enums = pynest_import("enums")
    models = pynest_import("models")
    thermostat = integration_import("thermostat")

    buckets = [
        models.Bucket(
            object_key="device.CCA7C1000022A6CF",
            object_revision=1,
            object_timestamp=1,
            value={"resource_id": "DEVICE_CCA7C1000022A6CF", "name": "Upstairs"},
            type=enums.BucketType.DEVICE,
        ),
        models.Bucket(
            object_key="device.CCA7C1000022A6D0",
            object_revision=1,
            object_timestamp=1,
            value={"resource_id": "DEVICE_CCA7C1000022A6D0", "name": "Downstairs"},
            type=enums.BucketType.DEVICE,
        ),
    ]
    official = {
        "only-id": thermostat.OfficialThermostatCandidate(
            device_entry_id="device-entry-id",
            device_identifier=("nest", "only-id"),
            device_identifier_key="only-id",
            name="Living Room",
            area_name="Living Room",
        )
    }

    thermostats = thermostat.build_thermostats(buckets, {}, official)

    assert thermostats["DEVICE_CCA7C1000022A6CF"].official_device_identifier is None
    assert thermostats["DEVICE_CCA7C1000022A6D0"].official_device_identifier is None


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


def test_build_thermostats_from_observe_uses_stable_fallback_name(
    pynest_import, integration_import
) -> None:
    """Observe-only thermostats should have a readable fallback name."""
    protocol = pynest_import("thermostat_protocol")
    thermostat = integration_import("thermostat")

    updates = [
        protocol.RemoteComfortSensingObserveUpdate(
            thermostat_id="DEVICE_CCA7C1000022A6CF",
            trait_label="remote_comfort_sensing_settings",
            settings=protocol.RemoteComfortSensingSettings(
                rcs_control_mode=1,
                source_type=protocol.RCS_SOURCE_TYPE_THERMOSTAT,
                active_sensor_id=None,
                associated_sensors=(),
                remembered_sensor_id=None,
                raw_payload=b"payload",
            ),
        )
    ]

    thermostats = thermostat.build_thermostats_from_observe(updates, {}, {}, {})

    assert thermostats["DEVICE_CCA7C1000022A6CF"].name == "Nest Thermostat 22A6CF"


def test_build_thermostat_from_single_observe_update_uses_area_name(
    pynest_import, integration_import
) -> None:
    """Observe-only thermostats should pick up the associated sensor area name."""
    enums = pynest_import("enums")
    models = pynest_import("models")
    protocol = pynest_import("thermostat_protocol")
    thermostat = integration_import("thermostat")

    devices = {
        "kryptonite.18B430CE7E5A5C06": models.Bucket(
            object_key="kryptonite.18B430CE7E5A5C06",
            object_revision=1,
            object_timestamp=1,
            value={
                "resource_id": "DEVICE_18B430CE7E5A5C06",
                "where_id": "where1",
                "current_temperature": 7300,
            },
            type=enums.BucketType.KRYPTONITE,
        )
    }
    update = protocol.RemoteComfortSensingObserveUpdate(
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

    discovered = thermostat.build_thermostat_from_observe_update(
        update, devices, {"where1": "Master Bedroom"}
    )

    assert discovered.name == "Master Bedroom"
    assert discovered.where_name == "Master Bedroom"


def test_thermostat_pairing_label_includes_readable_name_and_suffix(
    pynest_import, integration_import
) -> None:
    """Pairing labels should be readable and stable."""
    models = pynest_import("models")
    thermostat = integration_import("thermostat")

    label = thermostat.thermostat_pairing_label(
        models.ThermostatData(
            device_id="DEVICE_CCA7C1000022A6CF",
            name="Living Room",
            where_name="Living Room",
            where_id=None,
            structure_id=None,
        )
    )

    assert label == "Living Room (22A6CF)"


def test_official_thermostat_label_includes_area_when_needed(
    pynest_import, integration_import
) -> None:
    """Official thermostat labels should include the area when it adds context."""
    thermostat = integration_import("thermostat")

    candidate = thermostat.OfficialThermostatCandidate(
        device_entry_id="device-entry-id",
        device_identifier=("nest", "only-id"),
        device_identifier_key="only-id",
        name="Thermostat",
        area_name="Hallway",
    )

    assert thermostat.official_thermostat_label(candidate) == "Thermostat (Hallway)"


def test_runtime_official_match_ignores_already_assigned_thermostats(
    pynest_import, integration_import
) -> None:
    """Runtime discovery should not reuse an official thermostat already assigned."""
    models = pynest_import("models")
    thermostat = integration_import("thermostat")

    official = thermostat.OfficialThermostatCandidate(
        device_entry_id="device-entry-id",
        device_identifier=("nest", "only-id"),
        device_identifier_key="nest\x1fonly-id",
        name="Living Room",
        area_name="Living Room",
    )
    existing = models.ThermostatData(
        device_id="DEVICE_EXISTING",
        name="Living Room",
        where_name="Living Room",
        where_id=None,
        structure_id=None,
        official_device_identifier=("nest", "only-id"),
        official_device_entry_id="device-entry-id",
    )
    discovered = models.ThermostatData(
        device_id="DEVICE_NEW",
        name="Living Room",
        where_name="Living Room",
        where_id=None,
        structure_id=None,
    )

    thermostat.assign_runtime_official_thermostat_match(
        discovered,
        {"DEVICE_EXISTING": existing},
        {"nest\x1fonly-id": official},
    )

    assert discovered.official_device_identifier is None


def test_runtime_official_match_honors_manual_link(
    pynest_import, integration_import
) -> None:
    """Runtime discovery should honor a configured manual pairing override."""
    models = pynest_import("models")
    thermostat = integration_import("thermostat")

    official = thermostat.OfficialThermostatCandidate(
        device_entry_id="device-entry-id",
        device_identifier=("nest", "only-id"),
        device_identifier_key="nest\x1fonly-id",
        name="Upstairs",
        area_name="Upstairs",
    )
    discovered = models.ThermostatData(
        device_id="DEVICE_NEW",
        name="Nest Thermostat 22A6CF",
        where_name=None,
        where_id=None,
        structure_id=None,
    )

    thermostat.assign_runtime_official_thermostat_match(
        discovered,
        {},
        {"nest\x1fonly-id": official},
        {"DEVICE_NEW": "nest\x1fonly-id"},
    )

    assert discovered.official_device_identifier == ("nest", "only-id")


def test_apply_remote_comfort_sensing_backfills_placeholder_sensor_metadata(
    pynest_import, integration_import
) -> None:
    """Placeholder sensor names should be replaced when bucket metadata arrives."""
    enums = pynest_import("enums")
    models = pynest_import("models")
    protocol = pynest_import("thermostat_protocol")
    thermostat = integration_import("thermostat")

    discovered = models.ThermostatData(
        device_id="DEVICE_CCA7C1000022A6CF",
        name="Nest Thermostat 22A6CF",
        where_name=None,
        where_id=None,
        structure_id=None,
    )
    settings = protocol.RemoteComfortSensingSettings(
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
    )

    thermostat.apply_remote_comfort_sensing(discovered, settings, {}, {})
    assert (
        discovered.sensors["DEVICE_18B430CE7E5A5C06"].name
        == "DEVICE_18B430CE7E5A5C06"
    )

    devices = {
        "kryptonite.18B430CE7E5A5C06": models.Bucket(
            object_key="kryptonite.18B430CE7E5A5C06",
            object_revision=1,
            object_timestamp=1,
            value={
                "resource_id": "DEVICE_18B430CE7E5A5C06",
                "name": "Master Bedroom",
                "where_id": "where1",
                "current_temperature": 7300,
            },
            type=enums.BucketType.KRYPTONITE,
        )
    }
    thermostat.apply_remote_comfort_sensing(
        discovered,
        settings,
        devices,
        {"where1": "Master Bedroom"},
    )

    sensor = discovered.sensors["DEVICE_18B430CE7E5A5C06"]
    assert sensor.name == "Master Bedroom"
    assert sensor.bucket_key == "kryptonite.18B430CE7E5A5C06"
