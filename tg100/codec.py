"""Packing and unpacking of the TG100's 12 bit PCM.

Three bytes hold two samples. Given bytes b0 b1 b2 the middle byte is split,
its low nibble finishing the even sample and its high nibble finishing the odd
one:

    even = (b0 << 4) | (b1 & 0x0F)
    odd  = (b2 << 4) | (b1 >> 4)

Both values are two's complement, so 0x800..0xFFF are negative.

A note on the nibble order, because the two public references disagree. TG101
assigns b1's high nibble to the even sample and its low nibble to the odd one,
which is the opposite of what is written above. The difference only touches the
bottom four bits of each sample so it is far too quiet to hear, but it is
measurable: decode all 489 waves both ways and compare the mean absolute second
difference, and the order used here comes out smoother on 439 of them against
18 for TG101's. Smoother wins because real recorded audio is correlated sample
to sample while a misplaced nibble is not. Flip NIBBLE_ORDER_TG101 if a
hardware capture ever says otherwise.
"""

import wave as wave_module

import numpy as np

NIBBLE_ORDER_TG101 = False

# TG101 renders these samples with a negative scale, so the ROM may store
# inverted PCM. Every wave is inverted the same way, so it cannot be heard and
# nothing here depends on it. Left as a switch for anyone comparing to hardware.
INVERT_POLARITY = False

SAMPLE_MIN = -2048
SAMPLE_MAX = 2047


def packed_size(count):
    """Bytes needed to hold count samples. An odd tail costs two bytes."""
    if count < 0:
        raise ValueError("count must not be negative")
    return (count * 3 + 1) // 2


def unpack(data, offset, count):
    """Read count samples starting at a byte offset. Returns int16, signed."""
    if count == 0:
        return np.zeros(0, dtype=np.int16)

    need = packed_size(count)
    if offset < 0 or offset + need > len(data):
        raise ValueError(
            f"wave runs off the end of the ROM: needs {need} bytes at "
            f"0x{offset:06X}, ROM is {len(data)} bytes"
        )

    pairs = (count + 1) // 2
    raw = np.frombuffer(data, dtype=np.uint8, count=need, offset=offset)
    if need < pairs * 3:
        # an odd final sample only occupies b0 and half of b1
        raw = np.concatenate([raw, np.zeros(pairs * 3 - need, dtype=np.uint8)])
    tri = raw.reshape(pairs, 3).astype(np.uint16)
    b0, b1, b2 = tri[:, 0], tri[:, 1], tri[:, 2]

    if NIBBLE_ORDER_TG101:
        even = (b0 << 4) | (b1 >> 4)
        odd = (b2 << 4) | (b1 & 0x0F)
    else:
        even = (b0 << 4) | (b1 & 0x0F)
        odd = (b2 << 4) | (b1 >> 4)

    out = np.empty(pairs * 2, dtype=np.uint16)
    out[0::2] = even
    out[1::2] = odd
    out = out[:count]

    signed = out.astype(np.int16)
    signed = np.where(signed >= 2048, signed - 4096, signed).astype(np.int16)
    return -signed if INVERT_POLARITY else signed


def pack(samples):
    """Inverse of unpack. Values outside 12 bit range are clipped."""
    samples = np.asarray(samples)
    if samples.size == 0:
        return b""

    if INVERT_POLARITY:
        samples = -samples.astype(np.int32)
    samples = np.clip(samples, SAMPLE_MIN, SAMPLE_MAX).astype(np.int32)

    count = samples.size
    pairs = (count + 1) // 2
    padded = np.zeros(pairs * 2, dtype=np.int32)
    padded[:count] = samples
    u = (padded & 0xFFF).astype(np.uint16)

    even, odd = u[0::2], u[1::2]
    tri = np.empty((pairs, 3), dtype=np.uint8)

    if NIBBLE_ORDER_TG101:
        tri[:, 0] = (even >> 4) & 0xFF
        tri[:, 1] = ((even & 0x0F) << 4) | (odd & 0x0F)
        tri[:, 2] = (odd >> 4) & 0xFF
    else:
        tri[:, 0] = (even >> 4) & 0xFF
        tri[:, 1] = (even & 0x0F) | ((odd & 0x0F) << 4)
        tri[:, 2] = (odd >> 4) & 0xFF

    return tri.tobytes()[: packed_size(count)]


def to_int16(samples):
    """Scale 12 bit up to full range 16 bit for playback or WAV export."""
    return (np.asarray(samples).astype(np.int32) << 4).astype(np.int16)


def to_float(samples):
    """Scale to -1.0 .. 1.0 for drawing and for Qt audio."""
    return np.asarray(samples).astype(np.float32) / 2048.0


def from_int16(samples):
    """Scale 16 bit down to 12 bit, rounding rather than truncating."""
    x = np.asarray(samples).astype(np.int32)
    x = (x + 8) >> 4
    return np.clip(x, SAMPLE_MIN, SAMPLE_MAX).astype(np.int16)


def write_wav(path, samples, sample_rate):
    """Write 12 bit samples out as a mono 16 bit WAV."""
    with wave_module.open(str(path), "wb") as fp:
        fp.setnchannels(1)
        fp.setsampwidth(2)
        fp.setframerate(int(round(sample_rate)))
        fp.writeframes(to_int16(samples).tobytes())


def read_wav(path):
    """Read a WAV back to 12 bit samples. Returns (samples, sample_rate).

    Stereo is mixed down to mono because the wave table is mono. 8, 16 and 32
    bit integer PCM are accepted, anything else is rejected rather than guessed
    at.
    """
    with wave_module.open(str(path), "rb") as fp:
        channels = fp.getnchannels()
        width = fp.getsampwidth()
        rate = fp.getframerate()
        raw = fp.readframes(fp.getnframes())

    if width == 1:
        # WAV 8 bit is unsigned
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.int32)
        data = (data - 128) << 8
    elif width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.int32)
    elif width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.int32) >> 16
    else:
        raise ValueError(f"unsupported WAV sample width: {width} bytes")

    if channels > 1:
        usable = (data.size // channels) * channels
        data = data[:usable].reshape(-1, channels).mean(axis=1).astype(np.int32)

    return from_int16(data), rate
