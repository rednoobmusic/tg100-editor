"""Drum sounds, kits, and the program number to kit mapping.

A kit is a plain lookup of 128 notes to drum sound indices. A drum sound points
at a wave and adds tuning, level and pan on top, so several kits can share one
wave and still sound different.
"""

from . import layout
from .fields import Bits, Byte, Nibble, Record, Signed, Word

DRUM_KIT_ORDER = (
    "Standard", "Room", "Power", "Electronic", "Analog",
    "Brush", "Orchestra", "Clavinova", "RX", "C/M",
)


class DrumSound(Record):
    """One struck sound, 6 bytes."""

    wave_index = Word(0, 0x1FF)
    pitch_coarse = Signed(2, "semitones")
    pitch_fine = Byte(3, 0x7F)
    attenuation = Byte(4, 0x7F)
    pan = Nibble(5, False)
    reverb_depth = Nibble(5, True)

    def __init__(self, rom, index):
        if not 0 <= index < layout.NUM_DRUM_SOUNDS:
            raise IndexError(f"drum sound index out of range: {index}")
        self.index = index
        super().__init__(
            rom,
            layout.DRUM_SOUNDS + index * layout.DRUM_SOUND_SIZE,
            layout.DRUM_SOUND_SIZE,
        )

    __slots__ = ("index",)

    def __repr__(self):
        return f"<DrumSound {self.index} wave={self.wave_index}>"


class DrumKit(Record):
    """128 notes, each naming a drum sound. 511 means the note is silent."""

    def __init__(self, rom, index):
        if not 0 <= index < layout.NUM_DRUM_KITS:
            raise IndexError(f"drum kit index out of range: {index}")
        self.index = index
        super().__init__(
            rom,
            layout.DRUM_KITS + index * layout.DRUM_KIT_SIZE,
            layout.DRUM_KIT_SIZE,
        )

    __slots__ = ("index",)

    @property
    def name(self):
        return DRUM_KIT_ORDER[self.index]

    def sound_index(self, note):
        if not 0 <= note <= 127:
            raise IndexError(f"note out of range: {note}")
        base = note * 2
        return (((self._read(base) << 8) | self._read(base + 1)) & 0x1FF)

    def set_sound_index(self, note, value):
        if not 0 <= note <= 127:
            raise IndexError(f"note out of range: {note}")
        if not 0 <= value <= 0x1FF:
            raise ValueError(f"drum sound index out of range: {value}")
        base = note * 2
        self._write(base, (value >> 8) & 0xFF)
        self._write(base + 1, value & 0xFF)

    def mapped_notes(self):
        """Notes that actually make a sound, in order."""
        return [
            n
            for n in range(layout.DRUM_NOTE_MIN, layout.DRUM_NOTE_MAX + 1)
            if self.sound_index(n) != layout.DRUM_SOUND_OFF
        ]

    def __repr__(self):
        return f"<DrumKit {self.index} {self.name!r}>"


class DrumBank(Record):
    """Program number to kit index. A negative entry means no kit there."""

    def __init__(self, rom):
        super().__init__(rom, layout.DRUM_BANK, 128)

    def kit_index(self, program):
        if not 0 <= program <= 127:
            raise IndexError(f"program out of range: {program}")
        v = self._read(program)
        return v - 256 if v >= 128 else v

    def set_kit_index(self, program, value):
        if not 0 <= program <= 127:
            raise IndexError(f"program out of range: {program}")
        if not -128 <= value <= 127:
            raise ValueError(f"kit index out of range: {value}")
        self._write(program, value & 0xFF)

    def programs(self):
        """Program numbers that select a kit, paired with the kit index."""
        return [
            (p, self.kit_index(p))
            for p in range(128)
            if 0 <= self.kit_index(p) < layout.NUM_DRUM_KITS
        ]
