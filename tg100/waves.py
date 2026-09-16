"""The wave table at the front of the sample ROM.

512 slots of 12 bytes. 489 are used in the v1.10 dump, the rest are zeroed.
Each header carries where the sample lives, how it loops, and a small set of
per wave modulation settings the chip applies before the voice layer ever sees
the sound.

    byte 0   bits 7-6 format, bits 5-0 top of the start address
    byte 1   start address, middle
    byte 2   start address, low
    byte 3-4 loop point, in samples from the start
    byte 5-6 negated length, in samples
    byte 7   bits 6-4 LFO speed, bits 2-0 vibrato depth
    byte 8   high nibble EG attack rate, low nibble EG decay 1 rate
    byte 9   high nibble EG decay level, low nibble EG decay 2 rate
    byte 10  high nibble EG rate scale, low nibble EG release rate
    byte 11  bits 2-0 tremolo depth
"""

from . import codec, layout

FORMAT_8_BIT = 0
FORMAT_16_BIT = 2
FORMAT_12_BIT = 3

FORMAT_NAMES = {
    FORMAT_8_BIT: "8 bit",
    FORMAT_16_BIT: "16 bit",
    FORMAT_12_BIT: "12 bit",
}

# The chip clocks the wave table at this rate. Everything else is a pitch shift
# away from it, so it is what a raw dump of a wave should be played back at.
NATIVE_SAMPLE_RATE = 33075.0


class WaveHeader:
    """A mutable view onto one 12 byte slot. Writes go straight to the ROM."""

    __slots__ = ("rom", "index")

    def __init__(self, rom, index):
        if not 0 <= index < layout.NUM_WAVES:
            raise IndexError(f"wave index out of range: {index}")
        self.rom = rom
        self.index = index

    @property
    def _ofs(self):
        return layout.WAVE_HDR_BASE + self.index * layout.WAVE_HDR_SIZE

    def raw(self):
        o = self._ofs
        return bytes(self.rom.data[o : o + layout.WAVE_HDR_SIZE])

    def _get(self, i):
        return self.rom.data[self._ofs + i]

    def _set(self, i, value):
        self.rom.data[self._ofs + i] = value & 0xFF

    @property
    def is_empty(self):
        return self.raw()[:4] == b"\0\0\0\0"

    @property
    def format(self):
        return self._get(0) >> 6

    @format.setter
    def format(self, value):
        self._set(0, (self._get(0) & 0x3F) | ((value & 3) << 6))

    @property
    def format_name(self):
        return FORMAT_NAMES.get(self.format, f"unknown ({self.format})")

    @property
    def start(self):
        return ((self._get(0) & 0x3F) << 16) | (self._get(1) << 8) | self._get(2)

    @start.setter
    def start(self, value):
        if not 0 <= value < layout.SMPL_ROM_SIZE:
            raise ValueError(f"start address outside the ROM: 0x{value:X}")
        self._set(0, (self._get(0) & 0xC0) | ((value >> 16) & 0x3F))
        self._set(1, (value >> 8) & 0xFF)
        self._set(2, value & 0xFF)

    @property
    def loop(self):
        return (self._get(3) << 8) | self._get(4)

    @loop.setter
    def loop(self, value):
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"loop point out of range: {value}")
        self._set(3, (value >> 8) & 0xFF)
        self._set(4, value & 0xFF)

    @property
    def length(self):
        """Sample count. Stored negated, so a length of 0 reads back as 0."""
        return (-((self._get(5) << 8) | self._get(6))) & 0xFFFF

    @length.setter
    def length(self, value):
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"length out of range: {value}")
        stored = (-value) & 0xFFFF
        self._set(5, (stored >> 8) & 0xFF)
        self._set(6, stored & 0xFF)

    @property
    def loops(self):
        return self.loop < self.length

    @property
    def byte_length(self):
        return codec.packed_size(self.length)

    @property
    def end_address(self):
        return self.start + self.byte_length

    def _nib(self, i, high):
        b = self._get(i)
        return (b >> 4) if high else (b & 0x0F)

    def _set_nib(self, i, high, value):
        b = self._get(i)
        value &= 0x0F
        self._set(i, (b & 0x0F) | (value << 4) if high else (b & 0xF0) | value)

    @property
    def lfo_speed(self):
        return (self._get(7) >> 4) & 7

    @lfo_speed.setter
    def lfo_speed(self, v):
        self._set(7, (self._get(7) & 0x8F) | ((v & 7) << 4))

    @property
    def vibrato_depth(self):
        return self._get(7) & 7

    @vibrato_depth.setter
    def vibrato_depth(self, v):
        self._set(7, (self._get(7) & 0xF8) | (v & 7))

    @property
    def eg_attack_rate(self):
        return self._nib(8, True)

    @eg_attack_rate.setter
    def eg_attack_rate(self, v):
        self._set_nib(8, True, v)

    @property
    def eg_decay1_rate(self):
        return self._nib(8, False)

    @eg_decay1_rate.setter
    def eg_decay1_rate(self, v):
        self._set_nib(8, False, v)

    @property
    def eg_decay_level(self):
        return self._nib(9, True)

    @eg_decay_level.setter
    def eg_decay_level(self, v):
        self._set_nib(9, True, v)

    @property
    def eg_decay2_rate(self):
        return self._nib(9, False)

    @eg_decay2_rate.setter
    def eg_decay2_rate(self, v):
        self._set_nib(9, False, v)

    @property
    def eg_rate_scale(self):
        return self._nib(10, True)

    @eg_rate_scale.setter
    def eg_rate_scale(self, v):
        self._set_nib(10, True, v)

    @property
    def eg_release_rate(self):
        return self._nib(10, False)

    @eg_release_rate.setter
    def eg_release_rate(self, v):
        self._set_nib(10, False, v)

    @property
    def tremolo_depth(self):
        return self._get(11) & 7

    @tremolo_depth.setter
    def tremolo_depth(self, v):
        self._set(11, (self._get(11) & 0xF8) | (v & 7))

    def samples(self):
        """Decode this wave to signed 12 bit values."""
        if self.is_empty:
            import numpy as np

            return np.zeros(0, dtype="i2")
        return codec.unpack(self.rom.data, self.start, self.length)

    def write_samples(self, samples, relocate=False):
        """Replace the audio for this wave.

        Shorter or equal fits in place. Longer needs somewhere to go, so pass
        relocate=True to move it into free space and let the caller deal with
        the fact that the old region becomes a hole.
        """
        need = codec.packed_size(len(samples))
        if need <= self.byte_length:
            dest = self.start
        elif relocate:
            dest = self.rom.allocate(need)
        else:
            raise ValueError(
                f"wave {self.index} needs {need} bytes but only has "
                f"{self.byte_length}, pass relocate=True to move it"
            )

        blob = codec.pack(samples)
        self.rom.data[dest : dest + len(blob)] = blob
        self.start = dest
        self.length = len(samples)
        if self.loop >= self.length:
            self.loop = self.length

    def describe(self):
        if self.is_empty:
            return f"wave {self.index}: empty"
        loop = f"loop {self.loop}" if self.loops else "one shot"
        return (
            f"wave {self.index}: 0x{self.start:06X} "
            f"{self.length} samples, {loop}, {self.format_name}"
        )

    def __repr__(self):
        return f"<WaveHeader {self.index} start=0x{self.start:06X} len={self.length}>"
