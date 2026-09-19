"""Loading, editing and saving the two ROM images."""

import hashlib
from pathlib import Path

from . import layout, tables
from .drums import DrumBank, DrumKit, DrumSound
from .samplesets import SampleSet, SampleSetTable
from .voices import Voice, VoiceBank
from .waves import WaveHeader


class RomError(Exception):
    pass


class _RomImage:
    """Shared loading and saving. Subclasses say how big they should be."""

    size = 0
    expected_sha1 = ""
    label = "ROM"

    def __init__(self, data):
        if len(data) != self.size:
            raise RomError(
                f"{self.label} should be {self.size} bytes, got {len(data)}"
            )
        self.data = bytearray(data)
        # Two separate things. One never changes, so the known dump warning
        # stays honest after a save, the other tracks unsaved edits.
        self._original_sha1 = hashlib.sha1(bytes(data)).hexdigest()
        self._saved_sha1 = self._original_sha1

    @classmethod
    def load(cls, path):
        path = Path(path)
        try:
            blob = path.read_bytes()
        except OSError as exc:
            raise RomError(f"could not read {path}: {exc}") from exc
        rom = cls(blob)
        rom.path = path
        return rom

    path = None

    @property
    def sha1(self):
        return hashlib.sha1(bytes(self.data)).hexdigest()

    @property
    def is_known_dump(self):
        """True if this is the dump every offset here was checked against."""
        return self._original_sha1 == self.expected_sha1

    @property
    def modified(self):
        return self.sha1 != self._saved_sha1

    def save(self, path=None):
        target = Path(path) if path else self.path
        if target is None:
            raise RomError("no path to save to")
        target.write_bytes(bytes(self.data))
        self.path = target
        return target

    def mark_saved(self):
        self._saved_sha1 = self.sha1


class ProgramRom(_RomImage):
    """The 128K program ROM. H8/520 code below, lookup tables above."""

    size = layout.PROG_ROM_SIZE
    expected_sha1 = layout.PROG_ROM_SHA1
    label = "program ROM"

    def voice(self, index):
        return Voice(self, index)

    def voices(self):
        return [Voice(self, i) for i in range(layout.NUM_VOICES)]

    def voice_names(self):
        return [v.name for v in self.voices()]

    def bank(self, index):
        """Banks 0..3 sit in the block at 0x10000, -1 is Internal.

        There is no fifth bank. The address a fifth would occupy holds the
        firmware version string and then overlaps voice memory, so asking for
        one is refused rather than quietly handing back somewhere to write.
        """
        if index == -1:
            return VoiceBank(self, layout.BANK_INTERNAL, "Internal")
        if not 0 <= index < layout.NUM_VOICE_BANKS:
            raise IndexError(
                f"bank index out of range: {index}, the ROM has "
                f"{layout.NUM_VOICE_BANKS} banks plus Internal"
            )
        offset = layout.BANK_GM + index * 256
        if offset + 256 > layout.VOICE_MEM:
            raise RomError(
                f"bank {index} at 0x{offset:05X} would run into voice memory "
                f"at 0x{layout.VOICE_MEM:05X}"
            )
        return VoiceBank(self, offset, layout.VOICE_BANK_NAMES[index])

    def firmware_stamp(self):
        """The ASCII build stamp between the bank block and voice memory."""
        raw = bytes(
            self.data[layout.FIRMWARE_STAMP : layout.FIRMWARE_STAMP + layout.FIRMWARE_STAMP_LEN]
        )
        return raw.decode("ascii", "replace").strip()

    def banks(self):
        return [self.bank(i) for i in range(layout.NUM_VOICE_BANKS)]

    def bank_for_midi(self, midi_bank):
        """Resolve a MIDI bank select value through the bank table."""
        if not 0 <= midi_bank <= 127:
            raise IndexError(f"MIDI bank out of range: {midi_bank}")
        v = self.data[layout.VOICE_BANK_TBL + midi_bank]
        return v - 256 if v >= 128 else v

    def drum_bank(self):
        return DrumBank(self)

    def drum_kit(self, index):
        return DrumKit(self, index)

    def drum_kits(self):
        return [DrumKit(self, i) for i in range(layout.NUM_DRUM_KITS)]

    def drum_sound(self, index):
        return DrumSound(self, index)

    def sample_set(self, index):
        return SampleSet(self, index)

    def sample_set_table(self):
        return SampleSetTable(self)

    def sample_sets_for(self, wave_no):
        start, stop = self.sample_set_table().span(wave_no)
        return [SampleSet(self, i) for i in range(start, stop)]

    def drum_kit_names(self):
        return tables.drum_kit_names(self)

    def reverb_type_names(self):
        return tables.reverb_type_names(self)

    def table(self, name):
        return tables.read(self, name)


class SampleRom(_RomImage):
    """The 2M wave ROM. 512 headers, then packed 12 bit PCM."""

    size = layout.SMPL_ROM_SIZE
    expected_sha1 = layout.SMPL_ROM_SHA1
    label = "sample ROM"

    def wave(self, index):
        return WaveHeader(self, index)

    def waves(self):
        return [WaveHeader(self, i) for i in range(layout.NUM_WAVES)]

    def used_waves(self):
        return [w for w in self.waves() if not w.is_empty]

    def used_regions(self):
        """Byte ranges the wave data occupies, merged and in order."""
        spans = sorted(
            (w.start, w.end_address) for w in self.used_waves() if w.length
        )
        merged = [(0, layout.SAMPLE_DATA_START)]
        for start, stop in spans:
            last_start, last_stop = merged[-1]
            if start <= last_stop:
                merged[-1] = (last_start, max(last_stop, stop))
            else:
                merged.append((start, stop))
        return merged

    def free_regions(self):
        """Gaps between the used regions, largest last in address order."""
        gaps = []
        cursor = 0
        for start, stop in self.used_regions():
            if start > cursor:
                gaps.append((cursor, start))
            cursor = max(cursor, stop)
        if cursor < self.size:
            gaps.append((cursor, self.size))
        return gaps

    def free_bytes(self):
        return sum(stop - start for start, stop in self.free_regions())

    def allocate(self, nbytes):
        """Find a gap big enough for nbytes and return its start address.

        The factory ROM is packed almost solid, so this will usually fail
        until something else has been shortened first.
        """
        if nbytes <= 0:
            raise ValueError("cannot allocate zero bytes")
        for start, stop in self.free_regions():
            if stop - start >= nbytes:
                return start
        raise RomError(
            f"no free run of {nbytes} bytes in the sample ROM "
            f"({self.free_bytes()} bytes free in total, but fragmented). "
            f"Shorten or remove another wave first."
        )

    def waves_with_known_bad_loops(self):
        """Waves still looping that TG101 treats as single hits."""
        from .waves import KNOWN_BAD_LOOPS

        return [
            w
            for w in self.used_waves()
            if w.index in KNOWN_BAD_LOOPS and w.loops
        ]

    def fix_known_bad_loops(self):
        """Turn every known bad loop into a one shot. Returns the indices changed."""
        changed = []
        for w in self.waves_with_known_bad_loops():
            w.make_one_shot()
            changed.append(w.index)
        return changed

    def contains_waves(self, index):
        """Other waves whose audio sits entirely inside this one.

        One wave in the factory ROM does this: wave 45 swallows twenty others.
        Its stored length word is 0x0006, which decodes to 65530 samples, and
        every other wave in the ROM is under 40000. It is the data that is odd
        rather than the reading of it, but a wave like this cannot be edited
        meaningfully, so it is worth saying so out loud.
        """
        target = self.wave(index)
        if target.is_empty or not target.length:
            return []
        lo, hi = target.start, target.end_address
        out = []
        for w in self.used_waves():
            if w.index == index or not w.length:
                continue
            if w.start >= lo and w.end_address <= hi and w.byte_length < target.byte_length:
                out.append(w.index)
        return out

    def shares_data_with(self, index):
        """Other waves whose audio overlaps this one.

        Yamaha pointed several headers at the same or overlapping audio to save
        ROM, so editing one can change the others. Worth knowing before you
        write to it.
        """
        target = self.wave(index)
        if target.is_empty or not target.length:
            return []
        lo, hi = target.start, target.end_address
        out = []
        for w in self.used_waves():
            if w.index == index or not w.length:
                continue
            if w.start < hi and lo < w.end_address:
                out.append(w.index)
        return out
