"""Field packing for the records, checked without needing a real ROM."""

import pytest

from tg100 import layout
from tg100.rom import ProgramRom, SampleRom
from tg100.waves import WaveHeader


@pytest.fixture
def blank_sample():
    return SampleRom(bytes(layout.SMPL_ROM_SIZE))


@pytest.fixture
def blank_program():
    return ProgramRom(bytes(layout.PROG_ROM_SIZE))


def test_wrong_size_is_rejected():
    with pytest.raises(Exception, match="should be"):
        SampleRom(b"too short")


def test_wave_address_survives_a_round_trip(blank_sample):
    w = WaveHeader(blank_sample, 7)
    w.format = 3
    w.start = 0x1FABCD
    w.length = 12345
    w.loop = 999
    assert w.start == 0x1FABCD
    assert w.length == 12345
    assert w.loop == 999
    assert w.format == 3
    assert w.loops is True


def test_zero_length_reads_back_as_zero(blank_sample):
    w = WaveHeader(blank_sample, 0)
    w.length = 0
    assert w.length == 0


def test_wave_start_outside_the_rom_raises(blank_sample):
    with pytest.raises(ValueError, match="outside the ROM"):
        WaveHeader(blank_sample, 0).start = layout.SMPL_ROM_SIZE + 1


def test_wave_nibble_fields_do_not_collide(blank_sample):
    w = WaveHeader(blank_sample, 3)
    w.eg_attack_rate = 15
    w.eg_decay1_rate = 0
    w.eg_decay_level = 9
    w.eg_decay2_rate = 6
    w.eg_rate_scale = 1
    w.eg_release_rate = 14
    assert (w.eg_attack_rate, w.eg_decay1_rate) == (15, 0)
    assert (w.eg_decay_level, w.eg_decay2_rate) == (9, 6)
    assert (w.eg_rate_scale, w.eg_release_rate) == (1, 14)


def test_wave_bit_fields_do_not_collide(blank_sample):
    w = WaveHeader(blank_sample, 4)
    w.lfo_speed = 7
    w.vibrato_depth = 5
    assert (w.lfo_speed, w.vibrato_depth) == (7, 5)


def test_voice_name_is_padded_and_trimmed(blank_program):
    v = blank_program.voice(5)
    v.name = "Bass"
    assert v.name == "Bass"
    assert v.raw()[16:24] == b"Bass    "
    v.name = "WayTooLongName"
    assert v.name == "WayTooLo"


def test_voice_name_rejects_non_ascii(blank_program):
    with pytest.raises(ValueError, match="ASCII"):
        blank_program.voice(0).name = "café ☕"


def test_voice_elements_are_separate(blank_program):
    v = blank_program.voice(0)
    v.mode = 1
    v.element(0).wave_no = 12
    v.element(1).wave_no = 130
    assert v.element(0).wave_no == 12
    assert v.element(1).wave_no == 130


def test_split_nibble_values_round_trip(blank_program):
    bank = blank_program.bank(0)
    for program, index in ((0, 0), (1, 191), (127, 255)):
        bank.set_voice_index(program, index)
        assert bank.voice_index(program) == index


def test_out_of_range_field_raises(blank_program):
    with pytest.raises(ValueError):
        blank_program.voice(0).element(0).pan = 99
    with pytest.raises(ValueError):
        blank_program.voice(0).set_level(0, 200)


def test_bad_indices_raise(blank_program):
    with pytest.raises(IndexError):
        blank_program.voice(layout.NUM_VOICES)
    with pytest.raises(IndexError):
        blank_program.voice(0).element(2)


def test_drum_sound_signed_pitch(blank_program):
    ds = blank_program.drum_sound(3)
    ds.pitch_coarse = -37
    assert ds.pitch_coarse == -37
    ds.pitch_coarse = 17
    assert ds.pitch_coarse == 17


def test_drum_sound_shares_a_byte_between_pan_and_reverb(blank_program):
    ds = blank_program.drum_sound(0)
    ds.pan = 12
    ds.reverb_depth = 4
    assert (ds.pan, ds.reverb_depth) == (12, 4)
