"""The codec has to be exactly reversible or editing a ROM corrupts it."""

import numpy as np
import pytest

from tg100 import codec


@pytest.mark.parametrize("count", [0, 1, 2, 3, 5, 64, 999, 4502, 65535])
def test_round_trip(count):
    rng = np.random.default_rng(count)
    samples = rng.integers(-2048, 2048, count).astype(np.int16)
    packed = codec.pack(samples)
    assert len(packed) == codec.packed_size(count)
    assert np.array_equal(codec.unpack(packed, 0, count), samples)


def test_extremes_survive():
    samples = np.array([-2048, -1, 0, 1, 2047], dtype=np.int16)
    assert np.array_equal(codec.unpack(codec.pack(samples), 0, 5), samples)


def test_packed_size_odd_tail_costs_two_bytes():
    assert codec.packed_size(2) == 3
    assert codec.packed_size(3) == 5
    assert codec.packed_size(4) == 6


def test_out_of_range_is_clipped_not_wrapped():
    samples = np.array([5000, -5000], dtype=np.int32)
    out = codec.unpack(codec.pack(samples), 0, 2)
    assert out[0] == codec.SAMPLE_MAX
    assert out[1] == codec.SAMPLE_MIN


def test_unpack_past_the_end_raises():
    with pytest.raises(ValueError, match="off the end"):
        codec.unpack(b"\x00" * 10, 0, 100)


def test_nibbles_land_where_the_format_says():
    # even = (b0 << 4) | (b1 & 0x0F), odd = (b2 << 4) | (b1 >> 4)
    out = codec.unpack(bytes([0x12, 0x34, 0x56]), 0, 2)
    assert int(out[0]) == 0x124
    assert int(out[1]) == 0x563


def test_values_above_half_scale_read_back_negative():
    # 0x904 has bit 11 set, so it is two's complement negative
    out = codec.unpack(bytes([0x90, 0x04, 0x00]), 0, 2)
    assert int(out[0]) == 0x904 - 4096
    assert int(out[1]) == 0


def test_int16_scaling_is_reversible():
    samples = np.array([-2048, -7, 0, 7, 2047], dtype=np.int16)
    assert np.array_equal(codec.from_int16(codec.to_int16(samples)), samples)


def test_wav_round_trip(tmp_path):
    samples = (np.sin(np.linspace(0, 40, 2000)) * 2000).astype(np.int16)
    path = tmp_path / "t.wav"
    codec.write_wav(path, samples, 33075)
    back, rate = codec.read_wav(path)
    assert rate == 33075
    assert np.array_equal(back, samples)
