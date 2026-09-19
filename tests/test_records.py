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


def test_one_shot_is_encoded_as_loop_at_the_end(blank_sample):
    w = WaveHeader(blank_sample, 9)
    w.length = 500
    w.loop = 100
    assert w.loops is True
    assert w.one_shot is False
    assert w.loop_window == 400

    w.make_one_shot()
    assert w.one_shot is True
    assert w.loops is False
    assert w.loop == 500
    assert w.loop_window == 0


def test_set_looping_round_trips(blank_sample):
    w = WaveHeader(blank_sample, 10)
    w.length = 800
    w.set_looping(False)
    assert w.one_shot is True
    w.set_looping(True, 250)
    assert w.loops is True
    assert w.loop == 250


def test_set_looping_clamps_inside_the_wave(blank_sample):
    w = WaveHeader(blank_sample, 11)
    w.length = 100
    w.set_looping(True, 5000)
    assert w.loop == 99
    assert w.loops is True


def test_known_bad_loop_list_is_the_tg101_one():
    from tg100.waves import KNOWN_BAD_LOOPS

    assert len(KNOWN_BAD_LOOPS) == 64
    for expected in (11, 29, 38, 209, 449, 511):
        assert expected in KNOWN_BAD_LOOPS


def test_no_voice_bank_can_reach_voice_memory(blank_program):
    """A fifth bank would start at 0x10400 and run 240 bytes into voice 0.

    That is not hypothetical: the editor used to offer a Drums bank there, and
    writing to it overwrote voice names and element data.
    """
    for i in range(layout.NUM_VOICE_BANKS):
        bank = blank_program.bank(i)
        assert bank.offset + bank.size <= layout.VOICE_MEM


def test_a_fifth_bank_is_refused(blank_program):
    with pytest.raises(IndexError):
        blank_program.bank(layout.NUM_VOICE_BANKS)


def test_bank_names_match_bank_count():
    assert len(layout.VOICE_BANK_NAMES) == layout.NUM_VOICE_BANKS


def test_editing_every_bank_leaves_voice_memory_alone(blank_program):
    before = bytes(blank_program.data[layout.VOICE_MEM :])
    for i in range(layout.NUM_VOICE_BANKS):
        bank = blank_program.bank(i)
        for program in range(128):
            bank.set_voice_index(program, 99)
    assert bytes(blank_program.data[layout.VOICE_MEM :]) == before


def test_native_sample_rate_is_the_hardware_clock():
    """9.4 MHz divided by 224, from TG101. Guessing this makes every export flat."""
    from tg100.waves import NATIVE_SAMPLE_RATE

    assert NATIVE_SAMPLE_RATE == 9.4e6 / 224.0
    assert round(NATIVE_SAMPLE_RATE, 4) == 41964.2857


def test_writing_an_odd_wave_keeps_the_neighbours_nibble(blank_sample):
    """An odd sample count shares its final byte with whatever follows.

    Waves 47 and 52 overlap on byte 0x05F5F3 in the factory ROM exactly this
    way, so zeroing the spare nibble corrupts an unrelated sound.
    """
    import numpy as np

    w = WaveHeader(blank_sample, 0)
    w.start = 0x2000
    w.length = 3
    blank_sample.data[0x2000 + 4] = 0xAB  # the byte holding the spare nibble
    w.write_samples(np.array([100, -100, 50], dtype="i2"))
    assert blank_sample.data[0x2000 + 4] & 0xF0 == 0xA0


def test_write_samples_refuses_too_many_samples_before_touching_the_rom(blank_sample):
    import numpy as np

    w = WaveHeader(blank_sample, 0)
    w.start = 0x2000
    w.length = 100
    before = bytes(blank_sample.data)
    with pytest.raises(ValueError, match="65535"):
        w.write_samples(np.zeros(70000, dtype="i2"), relocate=True)
    assert bytes(blank_sample.data) == before


def test_saving_does_not_destroy_the_known_dump_flag(blank_program, tmp_path):
    blank_program._original_sha1 = blank_program.expected_sha1
    assert blank_program.is_known_dump is True
    blank_program.voice(0).name = "Edited"
    blank_program.save(tmp_path / "out.bin")
    blank_program.mark_saved()
    assert blank_program.is_known_dump is True
    assert blank_program.modified is False
