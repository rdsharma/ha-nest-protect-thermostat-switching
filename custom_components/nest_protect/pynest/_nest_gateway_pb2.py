"""Minimal protobuf message definitions for Nest gateway requests."""

from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

from google.protobuf import any_pb2 as google_dot_protobuf_dot_any__pb2

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\x12nest_gateway.proto\x12\x12nest_protect.proto\x1a\x19google/protobuf/any.proto"q\n\x0eObserveRequest\x12\x18\n\x10state_types_list\x18\x01 \x03(\x05\x12\x45\n\x11trait_type_params\x18\x03 \x03(\x0b\x32*.nest_protect.proto.TraitTypeObserveParams",\n\x16TraitTypeObserveParams\x12\x12\n\ntrait_type\x18\x01 \x01(\t"3\n\x07TraitId\x12\x13\n\x0bresource_id\x18\x01 \x01(\t\x12\x13\n\x0btrait_label\x18\x02 \x01(\t"-\n\x05Patch\x12$\n\x06values\x18\x01 \x01(\x0b\x32\x14.google.protobuf.Any"e\n\nTraitState\x12-\n\x08trait_id\x18\x01 \x01(\x0b\x32\x1b.nest_protect.proto.TraitId\x12(\n\x05patch\x18\x03 \x01(\x0b\x32\x19.nest_protect.proto.Patch"G\n\x0fObserveResponse\x12\x34\n\x0ctrait_states\x18\x03 \x03(\x0b\x32\x1e.nest_protect.proto.TraitState"\x1d\n\nStreamBody\x12\x0f\n\x07message\x18\x01 \x03(\x0c"O\n\x0fTraitInstanceId\x12\x13\n\x0bresource_id\x18\x01 \x01(\t\x12\x13\n\x0btrait_label\x18\x02 \x01(\t\x12\x12\n\nrequest_id\x18\x03 \x01(\t"q\n\x10TraitSetProperty\x12\x35\n\x08trait_id\x18\x01 \x01(\x0b\x32#.nest_protect.proto.TraitInstanceId\x12&\n\x08property\x18\x02 \x01(\x0b\x32\x14.google.protobuf.Any"]\n\x17BatchUpdateStateRequest\x12\x42\n\x14trait_set_properties\x18\x01 \x03(\x0b\x32$.nest_protect.proto.TraitSetPropertyb\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(
    DESCRIPTOR, "custom_components.nest_protect.pynest._nest_gateway_pb2", _globals
)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals["_OBSERVEREQUEST"]._serialized_start = 69
    _globals["_OBSERVEREQUEST"]._serialized_end = 182
    _globals["_TRAITTYPEOBSERVEPARAMS"]._serialized_start = 184
    _globals["_TRAITTYPEOBSERVEPARAMS"]._serialized_end = 228
    _globals["_TRAITID"]._serialized_start = 230
    _globals["_TRAITID"]._serialized_end = 281
    _globals["_PATCH"]._serialized_start = 283
    _globals["_PATCH"]._serialized_end = 328
    _globals["_TRAITSTATE"]._serialized_start = 330
    _globals["_TRAITSTATE"]._serialized_end = 431
    _globals["_OBSERVERESPONSE"]._serialized_start = 433
    _globals["_OBSERVERESPONSE"]._serialized_end = 504
    _globals["_STREAMBODY"]._serialized_start = 506
    _globals["_STREAMBODY"]._serialized_end = 535
    _globals["_TRAITINSTANCEID"]._serialized_start = 537
    _globals["_TRAITINSTANCEID"]._serialized_end = 616
    _globals["_TRAITSETPROPERTY"]._serialized_start = 618
    _globals["_TRAITSETPROPERTY"]._serialized_end = 731
    _globals["_BATCHUPDATESTATEREQUEST"]._serialized_start = 733
    _globals["_BATCHUPDATESTATEREQUEST"]._serialized_end = 826
