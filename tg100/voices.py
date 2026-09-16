"""Voices and the bank tables that select them.

A voice is 96 bytes: a common block with the name and the settings shared by
both elements, then two 36 byte elements. In single mode only element 1 sounds.
Dual mode layers both, which is how the TG100 gets its thicker patches out of a
2M wave ROM.
"""

from . import layout
from .fields import Bits, Byte, Record, SplitNibbles

SINGLE = 0
DUAL = 1
MODE_NAMES = {SINGLE: "single", DUAL: "dual"}

PITCH_LFO_WAVES = ("triangle", "sample and hold")
PITCH_EG_RANGES = ("half octave", "1 octave", "2 octaves", "8 octaves")
PITCH_RATE_SCALES = ("100%", "50%", "20%", "10%", "5%", "0%")

PEG_RATES = ("attack", "decay 1", "decay 2", "release")
PEG_LEVELS = ("initial", "attack", "decay 1", "decay 2", "release")

# Pan 0 means follow the voice's own pan rather than a fixed position.
PAN_FOLLOWS_VOICE = 0


class VoiceElement(Record):
    """One of the two layers of a voice."""

    wave_no = SplitNibbles(0, "index into the 140 entry wave number table")
    eg_attack_rate = Byte(2, 0x7F)
    eg_release_rate = Byte(3, 0x7F)

    pan = Bits(16, 0, 4)
    lfo_speed = Bits(17, 0, 3)
    lfo_delay = Byte(18, 0x7F)
    lfo_pitch_depth = Bits(20, 0, 4)
    lfo_amp_depth = Bits(21, 0, 3)

    pitch_lfo_wave = Bits(22, 0, 1)
    pitch_eg_range = Bits(23, 0, 2)
    pitch_eg_velocity_switch = Bits(24, 0, 1)
    pitch_eg_rate_scale = Bits(25, 0, 3)
    velocity_curve = Bits(35, 0, 3)

    def __init__(self, rom, offset):
        super().__init__(rom, offset, layout.VOICE_ELEMENT_SIZE)

    def level_scale_breakpoint(self, i):
        """Note number where one of the four level scaling segments starts."""
        self._check_scale_index(i)
        return self._read(4 + i) & 0x7F

    def set_level_scale_breakpoint(self, i, note):
        self._check_scale_index(i)
        if not 0 <= note <= 127:
            raise ValueError(f"breakpoint note out of range: {note}")
        self._write(4 + i, note)

    def level_scale_offset(self, i):
        self._check_scale_index(i)
        base = 8 + i * 2
        return ((self._read(base) << 4) & 0xFF) | (self._read(base + 1) & 0x0F)

    def set_level_scale_offset(self, i, value):
        self._check_scale_index(i)
        if not 0 <= value <= 255:
            raise ValueError(f"level scale offset out of range: {value}")
        base = 8 + i * 2
        self._write(base, (value >> 4) & 0x0F)
        self._write(base + 1, value & 0x0F)

    def pitch_eg_rate(self, i):
        if not 0 <= i < len(PEG_RATES):
            raise IndexError(f"pitch EG rate index out of range: {i}")
        return self._read(26 + i) & 0x3F

    def set_pitch_eg_rate(self, i, value):
        if not 0 <= i < len(PEG_RATES):
            raise IndexError(f"pitch EG rate index out of range: {i}")
        if not 0 <= value <= 63:
            raise ValueError(f"pitch EG rate out of range: {value}")
        self._write(26 + i, value)

    def pitch_eg_level(self, i):
        if not 0 <= i < len(PEG_LEVELS):
            raise IndexError(f"pitch EG level index out of range: {i}")
        return self._read(30 + i) & 0x7F

    def set_pitch_eg_level(self, i, value):
        if not 0 <= i < len(PEG_LEVELS):
            raise IndexError(f"pitch EG level index out of range: {i}")
        if not 0 <= value <= 127:
            raise ValueError(f"pitch EG level out of range: {value}")
        self._write(30 + i, value)

    @staticmethod
    def _check_scale_index(i):
        if not 0 <= i < 4:
            raise IndexError(f"level scale index out of range: {i}")

    def __repr__(self):
        return f"<VoiceElement wave={self.wave_no} pan={self.pan}>"


class Voice(Record):
    """One of the 192 voices in the program ROM."""

    mode = Bits(0, 0, 1)
    portamento_time = Byte(5, 0x7F)
    mod_lfo_pitch_depth = Bits(6, 0, 4)
    aftertouch_lfo_pitch_depth = Bits(8, 0, 4)

    def __init__(self, rom, index):
        if not 0 <= index < layout.NUM_VOICES:
            raise IndexError(f"voice index out of range: {index}")
        self.index = index
        super().__init__(
            rom, layout.VOICE_MEM + index * layout.VOICE_SIZE, layout.VOICE_SIZE
        )

    __slots__ = ("index",)

    @property
    def name(self):
        raw = self.raw()[layout.VOICE_NAME_OFS : layout.VOICE_NAME_OFS + layout.VOICE_NAME_LEN]
        return raw.decode("ascii", "replace").rstrip(" \0")

    @name.setter
    def name(self, value):
        text = value[: layout.VOICE_NAME_LEN].ljust(layout.VOICE_NAME_LEN)
        try:
            blob = text.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("voice names are ASCII only") from exc
        base = self.offset + layout.VOICE_NAME_OFS
        self.rom.data[base : base + layout.VOICE_NAME_LEN] = blob

    @property
    def mode_name(self):
        return MODE_NAMES.get(self.mode, "?")

    def element(self, i):
        if i not in (0, 1):
            raise IndexError(f"a voice has two elements, not {i}")
        return VoiceElement(self.rom, self.offset + 24 + i * layout.VOICE_ELEMENT_SIZE)

    @property
    def elements(self):
        """Only the elements that actually sound, so one in single mode."""
        return [self.element(0)] if self.mode == SINGLE else [self.element(0), self.element(1)]

    def level(self, i):
        return self._read(1 + i) & 0x7F

    def set_level(self, i, value):
        if not 0 <= value <= 127:
            raise ValueError(f"level out of range: {value}")
        self._write(1 + i, value)

    def detune(self, i):
        return self._read(3 + i) & 0x7F

    def set_detune(self, i, value):
        if not 0 <= value <= 127:
            raise ValueError(f"detune out of range: {value}")
        self._write(3 + i, value)

    def note_shift(self, i):
        return self._read(12 + i) & 0x7F

    def set_note_shift(self, i, value):
        if not 0 <= value <= 127:
            raise ValueError(f"note shift out of range: {value}")
        self._write(12 + i, value)

    def pitch_rate_scale(self, i):
        return min(self._read(10 + i * 4), len(PITCH_RATE_SCALES) - 1)

    def set_pitch_rate_scale(self, i, value):
        if not 0 <= value < len(PITCH_RATE_SCALES):
            raise ValueError(f"pitch rate scale out of range: {value}")
        self._write(10 + i * 4, value)

    def pitch_rate_scale_center(self, i):
        return self._read(11 + i * 4) & 0x7F

    def set_pitch_rate_scale_center(self, i, note):
        if not 0 <= note <= 127:
            raise ValueError(f"pitch rate scale centre out of range: {note}")
        self._write(11 + i * 4, note)

    def __repr__(self):
        return f"<Voice {self.index} {self.name!r} {self.mode_name}>"


class VoiceBank(Record):
    """128 program numbers, each naming a voice index. 255 means silent."""

    def __init__(self, rom, offset, name=""):
        self.name = name
        super().__init__(rom, offset, 256)

    __slots__ = ("name",)

    def voice_index(self, program):
        if not 0 <= program <= 127:
            raise IndexError(f"program out of range: {program}")
        base = program * 2
        return ((self._read(base) << 4) & 0xFF) | (self._read(base + 1) & 0x0F)

    def set_voice_index(self, program, index):
        if not 0 <= program <= 127:
            raise IndexError(f"program out of range: {program}")
        if not 0 <= index <= 255:
            raise ValueError(f"voice index out of range: {index}")
        base = program * 2
        self._write(base, (index >> 4) & 0x0F)
        self._write(base + 1, index & 0x0F)

    def __repr__(self):
        return f"<VoiceBank {self.name!r}>"
