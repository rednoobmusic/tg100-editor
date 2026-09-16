"""The lookup tables in the upper half of the program ROM.

These are the curves the firmware reads at runtime: how a cent maps to an F
number, how MIDI volume maps to attenuation, the eight velocity curves, and the
reverb coefficients. Editing them changes the feel of the whole module rather
than any one voice.
"""

import struct

from . import layout

BYTE = "byte"
WORD = "word"

# name: (offset, count, width, what it does)
SPECS = {
    "pitch": (layout.PITCH_TBL, 1200, WORD, "cents to F number, one per cent"),
    "volume": (layout.VOLUME_TBL, 128, BYTE, "MIDI volume to attenuation"),
    "velocity": (layout.VELOCITY_TBL, 8 * 128, BYTE, "eight velocity curves of 128"),
    "portamento_time": (layout.PORTA_TIME_TBL, 128, BYTE, "portamento time"),
    "pitch_eg_rate": (layout.PITCH_EG_RATE_TBL, 64, BYTE, "pitch EG rate"),
    "reverb_time": (layout.REVERB_TIME_TBL, 60, BYTE, "reverb time"),
    "reverb_feedback": (layout.REVERB_FEEDBACK_TBL, 256, WORD, "reverb feedback"),
    "reverb_gain": (layout.REVERB_GAIN_TBL, 256, WORD, "reverb gain"),
}


def read(rom, name):
    """Return a table as a list of ints."""
    try:
        offset, count, width, _ = SPECS[name]
    except KeyError:
        raise KeyError(f"unknown table {name!r}, try one of {sorted(SPECS)}") from None

    if width == BYTE:
        return list(rom.data[offset : offset + count])
    return list(struct.unpack_from(f">{count}H", rom.data, offset))


def write(rom, name, values):
    """Replace a table. The length has to match what the firmware expects."""
    try:
        offset, count, width, _ = SPECS[name]
    except KeyError:
        raise KeyError(f"unknown table {name!r}, try one of {sorted(SPECS)}") from None

    if len(values) != count:
        raise ValueError(f"{name} holds {count} entries, got {len(values)}")

    if width == BYTE:
        if any(not 0 <= v <= 0xFF for v in values):
            raise ValueError(f"{name} values must fit in a byte")
        rom.data[offset : offset + count] = bytes(values)
    else:
        if any(not 0 <= v <= 0xFFFF for v in values):
            raise ValueError(f"{name} values must fit in a word")
        struct.pack_into(f">{count}H", rom.data, offset, *values)


def velocity_curve(rom, curve):
    """One of the eight velocity curves, as 128 values."""
    if not 0 <= curve <= 7:
        raise IndexError(f"velocity curve out of range: {curve}")
    base = layout.VELOCITY_TBL + curve * 128
    return list(rom.data[base : base + 128])


def _fixed_names(rom, offset, count, width=8):
    out = []
    for i in range(count):
        base = offset + i * width
        raw = bytes(rom.data[base : base + width])
        out.append(raw.decode("ascii", "replace").rstrip(" \0"))
    return out


def reverb_type_names(rom):
    return _fixed_names(rom, layout.REVERB_TYPE_NAMES, 8)


def drum_kit_names(rom):
    """Kit names in kit order. The block they live in is not in kit order."""
    out = []
    for i in range(layout.NUM_DRUM_KITS):
        base = layout.DRUM_KIT_NAMES + layout.DRUM_KIT_NAME_OFS[i]
        raw = bytes(rom.data[base : base + 8])
        out.append(raw.decode("ascii", "replace").rstrip(" \0"))
    return out


def jazz_kit_name(rom):
    """Program 32 swaps the Standard kit's name for this one."""
    base = layout.DRUM_KIT_NAMES + layout.DRUM_KIT_NAME_OFS[10]
    return bytes(rom.data[base : base + 8]).decode("ascii", "replace").rstrip(" \0")
