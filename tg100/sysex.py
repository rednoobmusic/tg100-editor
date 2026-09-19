"""The TG100's MIDI system exclusive format: parsing dumps and writing them.

Everything here was derived from 24 dumps taken off a real TG100 and checked
against the firmware ROM. Nothing is assumed from what Yamaha did on other
machines of the period.

One message shape, not two
--------------------------

The TG100 has a single sysex message. There is no separate bulk dump format::

    F0 43 1n 27 <a2> <a1> <a0> <data ...> <checksum> F7

``n`` is the device number nibble, ``27`` is the model, and the three address
bytes are seven bits each, most significant first, so the address is
``a2 << 14 | a1 << 7 | a0``.  The data can be anything from one byte up; the
device writes it at that address and keeps going.  A whole 6790 byte dump is
just 164 of these, and the built in demo song holds the same message with a
single data byte in it to change reverb type mid song (at ROM 0x19643,
``F0 43 10 27 30 00 0A 00 46 F7``).

The checksum is Yamaha's usual two's complement over the address and the data,
the value that makes the low seven bits of the sum come to zero::

    checksum = (-sum(address_bytes + data)) & 0x7F

All 4017 messages in the corpus satisfy it.

The address space
-----------------

Two regions appear, and every message carries exactly one record::

    0x0C0000  6790 bytes  the multi: system, reverb, parts, voices, drum setup
    0x090000  1024 bytes  the four program change maps

Inside the multi::

    0x0C0000   10   system, the TG101 System block
    0x0C000A    6   reverb, the TG101 MultiCommon block, last 3 bytes unused
    0x0C0010  384   16 parts of 24 bytes, TG101 MultiPart
    0x0C0190 6144   64 voices of 96 bytes, the same record as the program ROM
    0x0C1990  246   82 drum setups of 3 bytes, notes 27 to 108

The 64 voices are the internal voice RAM, which is what MIDI bank numbers 64
to 111 select.  They start life as a copy of the first 64 program ROM voices,
which is why an untouched dump reads GrandPno, BritePno, El.Grand and so on.

Dump styles
-----------

The hardware emits two, and this module reproduces both byte for byte.

``"all"``    168 messages, 9323 bytes.  Parts, then reverb as a 3 byte write
             that skips the three unused bytes, then voices, drum setups, the
             four program change maps, and the system block last.  System goes
             last because it carries the device number, and changing that
             halfway through a dump would orphan the rest of it.

``"setup"``  164 messages, 8266 bytes.  System first, then all 6 reverb bytes,
             parts, voices, drum setups.  No program change maps.
"""

from . import layout
from .fields import Bits, Byte, Record, SplitNibbles
from .voices import Voice, VoiceBank

SYSEX_START = 0xF0
SYSEX_END = 0xF7
YAMAHA = 0x43
MODEL_TG100 = 0x27

# region bases in the 21 bit sysex address space
MULTI_BASE = 0x0C0000
MULTI_SIZE = 0x1A86
BANKS_BASE = 0x090000
BANKS_SIZE = 0x400

# offsets inside the multi region
SYSTEM_OFS = 0x0000
SYSTEM_SIZE = 10
REVERB_OFS = 0x000A
REVERB_SIZE = 6
REVERB_USED = 3
PARTS_OFS = 0x0010
PART_SIZE = 24
NUM_PARTS = 16
VOICES_OFS = 0x0190
NUM_VOICES = 64
DRUMS_OFS = 0x1990
DRUM_SETUP_SIZE = 3
DRUM_NOTE_MIN = 27
DRUM_NOTE_MAX = 108
NUM_DRUM_NOTES = DRUM_NOTE_MAX - DRUM_NOTE_MIN + 1

NUM_BANKS = 4
BANK_SIZE = 256
BANK_NAMES = layout.VOICE_BANK_NAMES

ALL = "all"
SETUP = "setup"
STYLES = (ALL, SETUP)

# Part slot 0 is the drum part, which the TG100 puts on MIDI channel 10 by
# default. Slots 1 to 9 are parts 1 to 9 and slots 10 to 15 are parts 11 to 16,
# so the slot number and the part number on the front panel are not the same.
DRUM_SLOT = 0

CHANNEL_OFF = 16
DEVICE_ALL = 16

PAN_FOLLOWS_VOICE = 0

REVERB_TYPES = layout.REVERB_TYPE_NAMES_ORDER
SOUND_MODULE_MODES = ("General MIDI", "Disk Orchestra", "C/M 64")
VELOCITY_METERS = ("off", "auto", "on")


class SysexError(Exception):
    pass




def checksum(payload):
    """Yamaha's two's complement checksum over the address and data bytes."""
    return (-sum(payload)) & 0x7F


def encode(address, data, device=0):
    """One sysex message writing data at an address."""
    if not 0 <= address < (1 << 21):
        raise ValueError(f"address out of range: 0x{address:X}")
    if not 0 <= device <= 15:
        raise ValueError(f"device number out of range: {device}")
    data = bytes(data)
    if not data:
        raise ValueError("a message needs at least one data byte")
    if any(b > 0x7F for b in data):
        raise ValueError("sysex data bytes must be 0..127")
    payload = bytes(
        ((address >> 14) & 0x7F, (address >> 7) & 0x7F, address & 0x7F)
    ) + data
    return bytes(
        (SYSEX_START, YAMAHA, 0x10 | device, MODEL_TG100)
    ) + payload + bytes((checksum(payload), SYSEX_END))


def decode(message):
    """Take one complete message apart. Returns (address, data)."""
    if len(message) < 9:
        raise SysexError(f"message is too short to be a TG100 one: {len(message)} bytes")
    if message[0] != SYSEX_START or message[-1] != SYSEX_END:
        raise SysexError("message is not bracketed by F0 and F7")
    if message[1] != YAMAHA:
        raise SysexError(f"not a Yamaha message: manufacturer 0x{message[1]:02X}")
    if message[2] & 0xF0 != 0x10:
        raise SysexError(f"not a parameter write: 0x{message[2]:02X}")
    if message[3] != MODEL_TG100:
        raise SysexError(f"not a TG100 message: model 0x{message[3]:02X}")
    payload = message[4:-2]
    if checksum(payload) != message[-2]:
        raise SysexError(
            f"checksum is 0x{message[-2]:02X}, should be 0x{checksum(payload):02X}"
        )
    address = (payload[0] << 14) | (payload[1] << 7) | payload[2]
    return address, bytes(payload[3:])


def messages(blob):
    """Every F0..F7 message in a file, in order. Bytes in between are skipped.

    One capture in the reference set has a stray C0 00 program change sitting
    between two messages, so this tolerates that rather than refusing the file.
    """
    out = []
    i = 0
    while i < len(blob):
        if blob[i] != SYSEX_START:
            i += 1
            continue
        end = blob.find(bytes((SYSEX_END,)), i)
        if end < 0:
            raise SysexError(f"message at offset {i} is never closed by F7")
        out.append(bytes(blob[i : end + 1]))
        i = end + 1
    return out


def parse(blob):
    """Every message in a file as (address, data) pairs."""
    return [decode(m) for m in messages(blob)]




class _Buffer:
    """The minimum a fields.Record needs to live inside: a mutable .data."""

    __slots__ = ("data",)

    def __init__(self, data):
        self.data = data


class System(Record):
    """Master settings. Ten bytes at the bottom of the multi."""

    transpose = Byte(2, 0x7F, "40..88, 64 is no shift")
    device_no = Byte(3, 0xFF, "0..15, or 16 for all")
    receive_sysex = Bits(4, 0, 1)
    receive_program_change = Bits(5, 0, 1)
    receive_control_change = Bits(6, 0, 1)
    sound_module_mode = Byte(7, 0xFF, "0 GM, 1 Disk Orchestra, 2 C/M 64")
    master_volume = Byte(8, 0x7F)
    velocity_meter = Byte(9, 0xFF, "0 off, 1 auto, 2 on")

    # 28..228, 128 is centre. Stored high nibble then low nibble.
    master_tune = SplitNibbles(0, "28..228, 128 is centre")

    def __init__(self, image):
        super().__init__(image, SYSTEM_OFS, SYSTEM_SIZE)

    @property
    def mode_name(self):
        i = self.sound_module_mode
        return SOUND_MODULE_MODES[i] if i < len(SOUND_MODULE_MODES) else "General MIDI"


class Reverb(Record):
    """The one reverb the whole module shares. TG101 calls this MultiCommon.

    Six bytes are reserved, three are used. An "all" dump writes only the
    three, which is why round tripping one leaves the other three alone.
    """

    type = Bits(0, 0, 3)
    time = Byte(1, 0x7F, "3..54")
    output_level = Byte(2, 0x7F, "24..70")

    def __init__(self, image):
        super().__init__(image, REVERB_OFS, REVERB_SIZE)

    @property
    def type_name(self):
        return REVERB_TYPES[self.type]


class Part(Record):
    """One of the 16 multi parts. Twenty four bytes, TG101's MultiPart."""

    voice_bank = Byte(0, 0x7F, "MIDI bank select, 64..111 picks voice RAM")
    program = Byte(1, 0x7F)
    midi_channel = Byte(2, 0xFF, "0..15, or 16 for off")
    poly = Bits(3, 0, 1)
    detune = SplitNibbles(4, "28..228, 128 is centre")
    note_shift = Byte(6, 0x7F, "40..88, 64 is no shift")
    volume = Byte(7, 0x7F)
    velocity_sense = Bits(8, 0, 4)
    pan = Bits(9, 0, 4, "0 centre, 1..7 right, 8 follow voice, 9..15 left")
    note_limit_low = Byte(10, 0x7F)
    note_limit_high = Byte(11, 0x7F)
    reverb_depth = Byte(12, 0x0F, "0..8")
    lfo_speed = Byte(13, 0x7F, "57..71")
    lfo_depth = Byte(14, 0x7F, "49..79")
    lfo_delay = Byte(15, 0x7F)
    eg_attack_rate = Byte(16, 0x7F, "57..71")
    eg_release_rate = Byte(17, 0x7F, "57..71")
    pitch_bend_range = Byte(18, 0x1F, "0..24")
    mod_lfo_pitch_depth = Bits(19, 0, 4)
    aftertouch_pitch_control = Byte(21, 0x7F, "40..88, 64 is none")
    aftertouch_lfo_pitch_depth = Bits(22, 0, 4)

    def __init__(self, image, slot):
        if not 0 <= slot < NUM_PARTS:
            raise IndexError(f"part slot out of range: {slot}")
        self.slot = slot
        super().__init__(image, PARTS_OFS + slot * PART_SIZE, PART_SIZE)

    __slots__ = ("slot",)

    @property
    def part_number(self):
        """What the front panel calls this slot. Slot 0 is the drum part, 10."""
        if self.slot == DRUM_SLOT:
            return 10
        return self.slot if self.slot < 10 else self.slot + 1

    def __repr__(self):
        return (
            f"<Part {self.part_number} ch={self.midi_channel} "
            f"bank={self.voice_bank} prog={self.program}>"
        )


class DrumSetup(Record):
    """Level, pan and reverb for one drum note. Three bytes, notes 27 to 108."""

    level = Byte(0, 0x7F)
    pan = Bits(1, 0, 4, "0 centre, 1..7 right, 9..15 left")
    reverb_depth = Byte(2, 0x0F, "0..8")

    def __init__(self, image, note):
        if not DRUM_NOTE_MIN <= note <= DRUM_NOTE_MAX:
            raise IndexError(
                f"drum note out of range {DRUM_NOTE_MIN}..{DRUM_NOTE_MAX}: {note}"
            )
        self.note = note
        super().__init__(
            image, DRUMS_OFS + (note - DRUM_NOTE_MIN) * DRUM_SETUP_SIZE, DRUM_SETUP_SIZE
        )

    __slots__ = ("note",)


# Ranges the front panel will let you dial in, taken from TG101 and confirmed
# against every value in the reference dumps. Out of range is not automatically
# wrong, because the hardware masks rather than clamps, but it is worth saying.
EDIT_RANGES = {
    "system.master_tune": (28, 228),
    "system.transpose": (40, 88),
    "system.device_no": (0, 16),
    "system.sound_module_mode": (0, 2),
    "system.master_volume": (0, 127),
    "system.velocity_meter": (0, 2),
    "reverb.type": (0, 7),
    "reverb.time": (3, 54),
    "reverb.output_level": (24, 70),
    "part.voice_bank": (0, 127),
    "part.program": (0, 127),
    "part.midi_channel": (0, 16),
    "part.detune": (28, 228),
    "part.note_shift": (40, 88),
    "part.volume": (0, 127),
    "part.velocity_sense": (0, 15),
    "part.pan": (0, 15),
    "part.reverb_depth": (0, 8),
    "part.lfo_speed": (57, 71),
    "part.lfo_depth": (49, 79),
    "part.lfo_delay": (0, 127),
    "part.eg_attack_rate": (57, 71),
    "part.eg_release_rate": (57, 71),
    "part.pitch_bend_range": (0, 24),
    "part.mod_lfo_pitch_depth": (0, 15),
    "part.aftertouch_pitch_control": (40, 88),
    "part.aftertouch_lfo_pitch_depth": (0, 15),
    "drum.level": (0, 127),
    "drum.pan": (0, 15),
    "drum.reverb_depth": (0, 8),
}




class Dump:
    """A TG100's editable state: the multi, and optionally the bank maps."""

    def __init__(self, multi=None, banks=None):
        if multi is None:
            multi = bytearray(MULTI_SIZE)
        if len(multi) != MULTI_SIZE:
            raise SysexError(f"the multi is {MULTI_SIZE} bytes, got {len(multi)}")
        if banks is not None and len(banks) != BANKS_SIZE:
            raise SysexError(f"the bank maps are {BANKS_SIZE} bytes, got {len(banks)}")

        self._multi = _Buffer(bytearray(multi))
        self._banks = _Buffer(bytearray(banks)) if banks is not None else None
        self.missing = []
        self.extra = []
        self.stray_bytes = 0

    # -- raw access

    @property
    def multi(self):
        return self._multi.data

    @property
    def banks(self):
        return self._banks.data if self._banks is not None else None

    @property
    def has_banks(self):
        return self._banks is not None

    def add_banks(self, banks=None):
        """Give a setup style dump somewhere to keep program change maps."""
        if banks is None:
            banks = bytearray(BANKS_SIZE)
        if len(banks) != BANKS_SIZE:
            raise SysexError(f"the bank maps are {BANKS_SIZE} bytes, got {len(banks)}")
        self._banks = _Buffer(bytearray(banks))

    # -- records

    @property
    def system(self):
        return System(self._multi)

    @property
    def reverb(self):
        return Reverb(self._multi)

    def part(self, slot):
        return Part(self._multi, slot)

    @property
    def parts(self):
        return [Part(self._multi, i) for i in range(NUM_PARTS)]

    def voice(self, index):
        """One of the 64 voices in RAM, as the same record the ROM editor uses."""
        return Voice(self._multi, index, base=VOICES_OFS, count=NUM_VOICES)

    @property
    def voices(self):
        return [self.voice(i) for i in range(NUM_VOICES)]

    def drum_setup(self, note):
        return DrumSetup(self._multi, note)

    @property
    def drum_setups(self):
        return [DrumSetup(self._multi, n) for n in range(DRUM_NOTE_MIN, DRUM_NOTE_MAX + 1)]

    def bank(self, index):
        if self._banks is None:
            raise SysexError("this dump has no program change maps")
        if not 0 <= index < NUM_BANKS:
            raise IndexError(f"bank out of range: {index}")
        return VoiceBank(self._banks, index * BANK_SIZE, BANK_NAMES[index])

    @property
    def bank_maps(self):
        return [self.bank(i) for i in range(NUM_BANKS)]

    # -- reading

    @classmethod
    def from_syx(cls, blob):
        """Build a dump from a .syx file.

        Messages are applied in the order they appear, so a file that writes
        the same address twice ends up with the later value, exactly as the
        hardware would. Addresses outside the two known regions are collected
        in .extra rather than thrown away, and any byte of a region that no
        message covered is listed in .missing.
        """
        dump = cls(banks=bytearray(BANKS_SIZE))
        multi_seen = bytearray(MULTI_SIZE)
        banks_seen = bytearray(BANKS_SIZE)
        saw_banks = False

        raw = bytes(blob)
        msgs = messages(raw)
        dump.stray_bytes = len(raw) - sum(len(m) for m in msgs)

        for message in msgs:
            address, data = decode(message)
            if MULTI_BASE <= address and address + len(data) <= MULTI_BASE + MULTI_SIZE:
                start = address - MULTI_BASE
                dump.multi[start : start + len(data)] = data
                multi_seen[start : start + len(data)] = b"\x01" * len(data)
            elif BANKS_BASE <= address and address + len(data) <= BANKS_BASE + BANKS_SIZE:
                start = address - BANKS_BASE
                dump.banks[start : start + len(data)] = data
                banks_seen[start : start + len(data)] = b"\x01" * len(data)
                saw_banks = True
            else:
                dump.extra.append((address, data))

        if not saw_banks:
            dump._banks = None

        dump.missing = [MULTI_BASE + i for i, s in enumerate(multi_seen) if not s]
        if saw_banks:
            dump.missing += [BANKS_BASE + i for i, s in enumerate(banks_seen) if not s]
        return dump

    @classmethod
    def load(cls, path):
        with open(path, "rb") as handle:
            return cls.from_syx(handle.read())

    # -- writing

    def to_messages(self, style=None, device=0):
        """The dump as (address, data) pairs in the order the hardware sends.

        The default style is "all" when the dump carries program change maps
        and "setup" when it does not.
        """
        if style is None:
            style = ALL if self.has_banks else SETUP
        if style not in STYLES:
            raise ValueError(f"unknown dump style {style!r}, try one of {STYLES}")
        if style == ALL and not self.has_banks:
            raise SysexError('an "all" dump needs program change maps, see add_banks')

        multi = self.multi
        out = []

        def part_messages():
            for i in range(NUM_PARTS):
                at = PARTS_OFS + i * PART_SIZE
                out.append((MULTI_BASE + at, bytes(multi[at : at + PART_SIZE])))

        def voice_messages():
            for i in range(NUM_VOICES):
                at = VOICES_OFS + i * layout.VOICE_SIZE
                out.append((MULTI_BASE + at, bytes(multi[at : at + layout.VOICE_SIZE])))

        def drum_messages():
            for i in range(NUM_DRUM_NOTES):
                at = DRUMS_OFS + i * DRUM_SETUP_SIZE
                out.append((MULTI_BASE + at, bytes(multi[at : at + DRUM_SETUP_SIZE])))

        system = (MULTI_BASE + SYSTEM_OFS, bytes(multi[SYSTEM_OFS : SYSTEM_OFS + SYSTEM_SIZE]))

        if style == SETUP:
            out.append(system)
            out.append((MULTI_BASE + REVERB_OFS, bytes(multi[REVERB_OFS : REVERB_OFS + REVERB_SIZE])))
            part_messages()
            voice_messages()
            drum_messages()
        else:
            part_messages()
            # only the three bytes the reverb actually uses
            out.append((MULTI_BASE + REVERB_OFS, bytes(multi[REVERB_OFS : REVERB_OFS + REVERB_USED])))
            voice_messages()
            drum_messages()
            banks = self.banks
            for i in range(NUM_BANKS):
                at = i * BANK_SIZE
                out.append((BANKS_BASE + at, bytes(banks[at : at + BANK_SIZE])))
            # system last: it holds the device number, and changing that part
            # way through a dump would orphan every message after it
            out.append(system)
        return out

    def to_syx(self, style=None, device=0):
        """The dump as a .syx file the hardware will take."""
        return b"".join(
            encode(address, data, device) for address, data in self.to_messages(style, device)
        )

    def save(self, path, style=None, device=0):
        with open(path, "wb") as handle:
            handle.write(self.to_syx(style, device))

    # -- checking

    def out_of_range(self):
        """Values outside what the front panel can dial in, as (where, value).

        Empty for every dump in the reference set. A non empty result is not
        proof of a bad dump, because the hardware masks rather than clamps, but
        it does mean something was written that the panel could not produce.
        """
        found = []

        def check(key, label, value):
            low, high = EDIT_RANGES[key]
            if not low <= value <= high:
                found.append((label, value, (low, high)))

        system = self.system
        for field in ("master_tune", "transpose", "device_no", "sound_module_mode",
                      "master_volume", "velocity_meter"):
            check(f"system.{field}", f"system.{field}", getattr(system, field))

        reverb = self.reverb
        for field in ("type", "time", "output_level"):
            check(f"reverb.{field}", f"reverb.{field}", getattr(reverb, field))

        for part in self.parts:
            for field in ("voice_bank", "program", "midi_channel", "detune",
                          "note_shift", "volume", "velocity_sense", "pan",
                          "reverb_depth", "lfo_speed", "lfo_depth", "lfo_delay",
                          "eg_attack_rate", "eg_release_rate", "pitch_bend_range",
                          "mod_lfo_pitch_depth", "aftertouch_pitch_control",
                          "aftertouch_lfo_pitch_depth"):
                check(f"part.{field}", f"part[{part.slot}].{field}", getattr(part, field))

        for setup in self.drum_setups:
            for field in ("level", "pan", "reverb_depth"):
                check(f"drum.{field}", f"drum[{setup.note}].{field}", getattr(setup, field))

        return found

    def __repr__(self):
        style = "all" if self.has_banks else "setup"
        return f"<Dump {style} reverb={self.reverb.type_name}>"




def _multi_message(offset, data, device=0):
    return encode(MULTI_BASE + offset, data, device)


def set_reverb_type(value, device=0):
    """The message the demo song uses to change reverb mid song."""
    if not 0 <= value <= 7:
        raise ValueError(f"reverb type out of range 0..7: {value}")
    return _multi_message(REVERB_OFS + 0, bytes((value,)), device)


def set_reverb_time(value, device=0):
    return _multi_message(REVERB_OFS + 1, bytes((value & 0x7F,)), device)


def set_reverb_output_level(value, device=0):
    return _multi_message(REVERB_OFS + 2, bytes((value & 0x7F,)), device)


def set_part_byte(slot, index, value, device=0):
    """Write one byte of one part record."""
    if not 0 <= slot < NUM_PARTS:
        raise IndexError(f"part slot out of range: {slot}")
    if not 0 <= index < PART_SIZE:
        raise IndexError(f"part byte out of range: {index}")
    return _multi_message(PARTS_OFS + slot * PART_SIZE + index, bytes((value & 0x7F,)), device)


def voice_message(index, blob, device=0):
    """Write one whole 96 byte voice into voice RAM."""
    if not 0 <= index < NUM_VOICES:
        raise IndexError(f"voice out of range 0..{NUM_VOICES - 1}: {index}")
    if len(blob) != layout.VOICE_SIZE:
        raise ValueError(f"a voice is {layout.VOICE_SIZE} bytes, got {len(blob)}")
    return _multi_message(VOICES_OFS + index * layout.VOICE_SIZE, blob, device)


def voice_from_rom(rom, rom_index, slot, device=0):
    """Send a program ROM voice into one of the 64 RAM slots.

    This is the bridge from the ROM editor to the hardware: edit voice 12 in
    the ROM image, send it to RAM slot 3, select bank 64 program 3 on a part,
    and the TG100 plays what is on screen without reflashing anything.
    """
    base = layout.VOICE_MEM + rom_index * layout.VOICE_SIZE
    if not 0 <= rom_index < layout.NUM_VOICES:
        raise IndexError(f"ROM voice out of range: {rom_index}")
    return voice_message(slot, bytes(rom.data[base : base + layout.VOICE_SIZE]), device)
