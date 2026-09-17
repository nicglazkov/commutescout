"""The slice of the protobuf wire format the Waze RT protocol needs.

The Java original (highway-radar-sabre-plus) generates message classes from
``app/src/main/proto/waze.proto``. A relay that has to build and read a
handful of messages does not need a code generator, so this module encodes
and decodes the four wire types those messages use, and ``proto.py`` writes
the field numbers on top of it.

Encoding rules that matter for byte-for-byte compatibility:

* Fields are written in ascending field-number order, as protobuf's own
  generated writers do.
* ``int32`` and ``int64`` are plain varints, never zig-zag, so a negative
  value is its two's complement in 64 bits and costs ten bytes.
* A present-but-empty message field is written as a tag with length 0, which
  is how ``Register`` and ``ReportAdsSettings`` are sent.
"""

from __future__ import annotations

VARINT = 0
FIXED64 = 1
LENGTH = 2
FIXED32 = 5

_MASK64 = (1 << 64) - 1


def varint(value: int) -> bytes:
    """One unsigned base-128 varint."""
    v = value & _MASK64
    out = bytearray()
    while True:
        chunk = v & 0x7F
        v >>= 7
        if v:
            out.append(chunk | 0x80)
        else:
            out.append(chunk)
            return bytes(out)


def tag(field: int, wire_type: int) -> bytes:
    return varint((field << 3) | wire_type)


def num(field: int, value: int) -> bytes:
    """An int32, int64, bool or enum field."""
    return tag(field, VARINT) + varint(int(value))


def double(field: int, value: float) -> bytes:
    import struct

    return tag(field, FIXED64) + struct.pack("<d", float(value))


def raw(field: int, value: bytes) -> bytes:
    """A bytes field, and the carrier for strings and nested messages."""
    return tag(field, LENGTH) + varint(len(value)) + value


def string(field: int, value: str) -> bytes:
    return raw(field, value.encode("utf-8"))


def message(field: int, body: bytes) -> bytes:
    """A nested message, including an empty one (tag plus length 0)."""
    return raw(field, body)


def as_int32(value: int) -> int:
    """A varint read back as protobuf reads an ``int32``: the low 32 bits,
    sign-extended. Waze sends longitude as an unsigned micro-degree value on
    some builds and as a negative int32 on others; both land here correctly."""
    v = value & 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def as_int64(value: int) -> int:
    v = value & _MASK64
    return v - (1 << 64) if v >= (1 << 63) else v


def fields(buf: bytes) -> dict[int, list]:
    """Every field in a message, keyed by field number.

    Values are ints for varints and the fixed widths, and bytes for
    length-delimited fields. Unknown fields come back with the rest: the
    caller reads the ones it knows and ignores everything else, which is what
    keeps this compatible with the parts of the schema we never declared.
    """
    out: dict[int, list] = {}
    i, n = 0, len(buf)
    while i < n:
        key, i = _read_varint(buf, i)
        field, wire_type = key >> 3, key & 0x07
        if wire_type == VARINT:
            value, i = _read_varint(buf, i)
        elif wire_type == FIXED64:
            value = int.from_bytes(buf[i:i + 8], "little")
            i += 8
        elif wire_type == LENGTH:
            length, i = _read_varint(buf, i)
            value = buf[i:i + length]
            i += length
        elif wire_type == FIXED32:
            value = int.from_bytes(buf[i:i + 4], "little")
            i += 4
        else:
            raise ValueError(f"unsupported wire type {wire_type} for field {field}")
        out.setdefault(field, []).append(value)
    return out


def first(msg: dict[int, list], field: int, default=None):
    """The first value of a field, or ``default`` when it is absent."""
    values = msg.get(field)
    return values[0] if values else default


def sub(msg: dict[int, list], field: int) -> dict[int, list] | None:
    """A nested message field, parsed, or None when it is absent."""
    body = first(msg, field)
    return fields(body) if isinstance(body, bytes) else None


def text(msg: dict[int, list], field: int) -> str:
    body = first(msg, field)
    return body.decode("utf-8", "replace") if isinstance(body, bytes) else ""


def _read_varint(buf: bytes, i: int) -> tuple[int, int]:
    value = shift = 0
    while True:
        if i >= len(buf):
            raise ValueError("truncated varint")
        byte = buf[i]
        i += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, i
        shift += 7
        if shift > 63:
            raise ValueError("varint too long")
