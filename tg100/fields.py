"""Small descriptors for the regular byte fields in the program ROM.

The voice, drum and sample set records are mostly one value per byte, or a
value split across two bytes as high nibble then low nibble. Writing thirty
near identical property pairs by hand invites typos, so they are declared
instead. The wave headers do not use these because their address and length
fields are packed in their own way.
"""


class Byte:
    """One byte, optionally masked to the bits the hardware actually reads."""

    def __init__(self, index, mask=0xFF, doc=None):
        self.index = index
        self.mask = mask
        self.__doc__ = doc

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return obj._read(self.index) & self.mask

    def __set__(self, obj, value):
        if not 0 <= value <= self.mask:
            raise ValueError(f"{self.name} out of range 0..{self.mask}: {value}")
        obj._write(self.index, value)


class Signed:
    """One byte read as two's complement."""

    def __init__(self, index, doc=None):
        self.index = index
        self.__doc__ = doc

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        v = obj._read(self.index)
        return v - 256 if v >= 128 else v

    def __set__(self, obj, value):
        if not -128 <= value <= 127:
            raise ValueError(f"{self.name} out of range -128..127: {value}")
        obj._write(self.index, value & 0xFF)


class Nibble:
    """Half a byte. Set high=True for the top four bits."""

    def __init__(self, index, high, doc=None):
        self.index = index
        self.high = high
        self.__doc__ = doc

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        b = obj._read(self.index)
        return (b >> 4) if self.high else (b & 0x0F)

    def __set__(self, obj, value):
        if not 0 <= value <= 15:
            raise ValueError(f"{self.name} out of range 0..15: {value}")
        b = obj._read(self.index)
        if self.high:
            obj._write(self.index, (b & 0x0F) | (value << 4))
        else:
            obj._write(self.index, (b & 0xF0) | value)


class Bits:
    """A run of bits inside one byte."""

    def __init__(self, index, shift, width, doc=None):
        self.index = index
        self.shift = shift
        self.mask = (1 << width) - 1
        self.__doc__ = doc

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return (obj._read(self.index) >> self.shift) & self.mask

    def __set__(self, obj, value):
        if not 0 <= value <= self.mask:
            raise ValueError(f"{self.name} out of range 0..{self.mask}: {value}")
        b = obj._read(self.index)
        b &= ~(self.mask << self.shift) & 0xFF
        obj._write(self.index, b | (value << self.shift))


class SplitNibbles:
    """A value stored as high nibble in one byte, low nibble in the next.

    Yamaha used this all over the TG100 tables. The first byte holds the value
    shifted right by four, the second holds the remainder in its low nibble.
    """

    def __init__(self, index, doc=None):
        self.index = index
        self.__doc__ = doc

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        hi = obj._read(self.index)
        lo = obj._read(self.index + 1)
        return ((hi << 4) & 0xFF) | (lo & 0x0F)

    def __set__(self, obj, value):
        if not 0 <= value <= 0xFF:
            raise ValueError(f"{self.name} out of range 0..255: {value}")
        obj._write(self.index, (value >> 4) & 0x0F)
        obj._write(self.index + 1, value & 0x0F)


class Word:
    """A big endian 16 bit value, optionally masked."""

    def __init__(self, index, mask=0xFFFF, doc=None):
        self.index = index
        self.mask = mask
        self.__doc__ = doc

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        return ((obj._read(self.index) << 8) | obj._read(self.index + 1)) & self.mask

    def __set__(self, obj, value):
        if not 0 <= value <= self.mask:
            raise ValueError(f"{self.name} out of range 0..{self.mask}: {value}")
        obj._write(self.index, (value >> 8) & 0xFF)
        obj._write(self.index + 1, value & 0xFF)


class Record:
    """Base for a fixed size record viewed in place inside a ROM image."""

    __slots__ = ("rom", "offset", "size")

    def __init__(self, rom, offset, size):
        self.rom = rom
        self.offset = offset
        self.size = size

    def _read(self, i):
        return self.rom.data[self.offset + i]

    def _write(self, i, value):
        self.rom.data[self.offset + i] = value & 0xFF

    def raw(self):
        return bytes(self.rom.data[self.offset : self.offset + self.size])

    def replace(self, blob):
        if len(blob) != self.size:
            raise ValueError(f"expected {self.size} bytes, got {len(blob)}")
        self.rom.data[self.offset : self.offset + self.size] = blob
