"""Sample sets, the layer between a wave number and the actual wave table.

A voice element names a wave number from 0 to 139. That number indexes a table
of 141 words, and the span between one entry and the next is a run of sample
sets, one per key range. So a single "wave" that a voice refers to is usually a
multisample of up to a dozen recordings.
"""

from . import layout
from .fields import Byte, Nibble, Record, Word


class SampleSet(Record):
    """One key range of a multisample, 9 bytes."""

    wave_index = Word(0, 0x1FF)
    note_low = Byte(2, 0x7F)
    note_high = Byte(3, 0x7F)
    root_note = Byte(4, 0x7F, "the note this recording was sampled at")
    fine_tune = Byte(5, 0x7F, "cents above the root note, 0 to 99")
    attenuation = Byte(6, 0x7F)
    eg_decay1_rate = Nibble(7, False)
    eg_attack_rate = Nibble(7, True)
    eg_release_rate = Nibble(8, False)
    eg_rate_scale = Nibble(8, True)

    def __init__(self, rom, index):
        if not 0 <= index < layout.NUM_SAMPLE_SETS:
            raise IndexError(f"sample set index out of range: {index}")
        self.index = index
        super().__init__(
            rom,
            layout.SAMPLE_SETS + index * layout.SAMPLE_SET_SIZE,
            layout.SAMPLE_SET_SIZE,
        )

    __slots__ = ("index",)

    def covers(self, note):
        return self.note_low <= note <= self.note_high

    def __repr__(self):
        return (
            f"<SampleSet {self.index} wave={self.wave_index} "
            f"notes {self.note_low}-{self.note_high} root={self.root_note}>"
        )


class SampleSetTable(Record):
    """Wave number to the first sample set of its multisample."""

    def __init__(self, rom):
        super().__init__(
            rom, layout.SAMPLE_SET_TBL, (layout.NUM_WAVE_NOS + 1) * 2
        )

    def first(self, wave_no):
        if not 0 <= wave_no <= layout.NUM_WAVE_NOS:
            raise IndexError(f"wave number out of range: {wave_no}")
        base = wave_no * 2
        return (self._read(base) << 8) | self._read(base + 1)

    def span(self, wave_no):
        """The (start, stop) sample set range for a wave number."""
        if not 0 <= wave_no < layout.NUM_WAVE_NOS:
            raise IndexError(f"wave number out of range: {wave_no}")
        start = min(self.first(wave_no), layout.NUM_SAMPLE_SETS)
        stop = min(self.first(wave_no + 1), layout.NUM_SAMPLE_SETS)
        return start, stop
