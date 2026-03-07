"""Minimal protobuf message definitions for Nest thermostat traits."""

from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x15nest_thermostat.proto\x12\x12nest_protect.proto"!\n\nResourceId\x12\x13\n\x0bresource_id\x18\x01 \x01(\t"Q\n\x1fRememberedRemoteSensorSelection\x12.\n\x06sensor\x18\x02 \x01(\x0b\x32\x1e.nest_protect.proto.ResourceId"\x0e\n\x0cEmptyMessage"\xb6\x08\n!RemoteComfortSensingSettingsTrait\x12^\n\x10rcs_control_mode\x18\x01 \x01(\x0e\x32D.nest_protect.proto.RemoteComfortSensingSettingsTrait.RcsControlMode\x12\x66\n\x14active_rcs_selection\x18\x02 \x01(\x0b\x32H.nest_protect.proto.RemoteComfortSensingSettingsTrait.RcsSourceSelection\x12>\n\x14rcs_control_schedule\x18\x03 \x01(\x0b\x32 .nest_protect.proto.EmptyMessage\x12\x61\n\x16associated_rcs_sensors\x18\x04 \x03(\x0b\x32A.nest_protect.proto.RemoteComfortSensingSettingsTrait.RcsSensorId\x12_\n"remembered_remote_sensor_selection\x18\x06 \x01(\x0b\x32\x33.nest_protect.proto.RememberedRemoteSensorSelection\x1ag\n\x0bRcsSensorId\x12\x31\n\tdevice_id\x18\x01 \x01(\x0b\x32\x1e.nest_protect.proto.ResourceId\x12\x11\n\tvendor_id\x18\x02 \x01(\r\x12\x12\n\nproduct_id\x18\x03 \x01(\r\x1a\xad\x01\n\x12RcsSourceSelection\x12\\\n\x0frcs_source_type\x18\x01 \x01(\x0e\x32\x43.nest_protect.proto.RemoteComfortSensingSettingsTrait.RcsSourceType\x12\x39\n\x11active_rcs_sensor\x18\x02 \x01(\x0b\x32\x1e.nest_protect.proto.ResourceId"\x94\x01\n\x0eRcsControlMode\x12 \n\x1cRCS_CONTROL_MODE_UNSPECIFIED\x10\x00\x12\x19\n\x15RCS_CONTROL_MODE_HOLD\x10\x01\x12\x1d\n\x19RCS_CONTROL_MODE_SCHEDULE\x10\x02\x12&\n"RCS_CONTROL_MODE_SCHEDULE_OVERRIDE\x10\x03"\x94\x01\n\rRcsSourceType\x12\x1f\n\x1bRCS_SOURCE_TYPE_UNSPECIFIED\x10\x00\x12\x1d\n\x19RCS_SOURCE_TYPE_BACKPLATE\x10\x01\x12!\n\x1dRCS_SOURCE_TYPE_SINGLE_SENSOR\x10\x02\x12 \n\x1cRCS_SOURCE_TYPE_MULTI_SENSOR\x10\x03b\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(
    DESCRIPTOR, "custom_components.nest_protect.pynest._nest_thermostat_pb2", _globals
)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals["_RESOURCEID"]._serialized_start = 45
    _globals["_RESOURCEID"]._serialized_end = 78
    _globals["_REMEMBEREDREMOTESENSORSELECTION"]._serialized_start = 80
    _globals["_REMEMBEREDREMOTESENSORSELECTION"]._serialized_end = 161
    _globals["_EMPTYMESSAGE"]._serialized_start = 163
    _globals["_EMPTYMESSAGE"]._serialized_end = 177
    _globals["_REMOTECOMFORTSENSINGSETTINGSTRAIT"]._serialized_start = 180
    _globals["_REMOTECOMFORTSENSINGSETTINGSTRAIT"]._serialized_end = 1258
    _globals["_REMOTECOMFORTSENSINGSETTINGSTRAIT_RCSSENSORID"]._serialized_start = 677
    _globals["_REMOTECOMFORTSENSINGSETTINGSTRAIT_RCSSENSORID"]._serialized_end = 780
    _globals["_REMOTECOMFORTSENSINGSETTINGSTRAIT_RCSSOURCESELECTION"]._serialized_start = 783
    _globals["_REMOTECOMFORTSENSINGSETTINGSTRAIT_RCSSOURCESELECTION"]._serialized_end = 956
    _globals["_REMOTECOMFORTSENSINGSETTINGSTRAIT_RCSCONTROLMODE"]._serialized_start = 959
    _globals["_REMOTECOMFORTSENSINGSETTINGSTRAIT_RCSCONTROLMODE"]._serialized_end = 1107
    _globals["_REMOTECOMFORTSENSINGSETTINGSTRAIT_RCSSOURCETYPE"]._serialized_start = 1110
    _globals["_REMOTECOMFORTSENSINGSETTINGSTRAIT_RCSSOURCETYPE"]._serialized_end = 1258
