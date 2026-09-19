"""The validator, the relayout engine and the sample processing."""

import numpy as np
import pytest

from tg100 import dsp, layout, repack, validate
from tg100.rom import ProgramRom, SampleRom
from tg100.waves import WaveHeader


@pytest.fixture
def rom():
    smpl = SampleRom(bytes(layout.SMPL_ROM_SIZE))
    for i, (start, count) in enumerate(((0x2000, 100), (0x3000, 200), (0x5000, 50))):
        w = WaveHeader(smpl, i)
        w.format = 3
        w.start = start
        w.length = count
        w.make_one_shot()
    return smpl


def test_blocks_group_overlapping_waves(rom):
    # point wave 1 inside wave 0's range, they must end up in one block
    rom.wave(1).start = 0x2010
    rom.wave(1).length = 20
    found = repack.blocks(rom)
    shared = [b for b in found if len(b.waves) > 1]
    assert shared and set(shared[0].waves) == {0, 1}


def test_repack_moves_data_down_without_changing_it(rom):
    before = {w.index: bytes(w.samples()) for w in rom.used_waves()}
    result = repack.repack(rom)
    after = {w.index: bytes(w.samples()) for w in rom.used_waves()}
    assert before == after
    assert result.moved == 3
    assert rom.wave(0).start == layout.SAMPLE_DATA_START


def test_repack_keeps_shared_waves_sharing(rom):
    rom.wave(1).start = 0x2010
    rom.wave(1).length = 20
    repack.repack(rom)
    assert rom.wave(1).start - rom.wave(0).start == 0x10


def test_repack_frees_space_after_a_wave_shrinks(rom):
    rom.wave(1).write_samples(np.zeros(10, dtype="i2"))
    before = repack.largest_free_run(rom)
    repack.repack(rom)
    assert repack.largest_free_run(rom) > before


def test_validator_passes_a_consistent_rom(rom):
    assert validate.check(None, rom) == []


def test_validator_catches_a_wave_past_the_end(rom):
    rom.data[0 * 12 + 0] = 0x3F
    rom.data[0 * 12 + 1] = 0xFF
    rom.data[0 * 12 + 2] = 0xF0
    issues = validate.check(None, rom)
    assert any("past the end" in i.message for i in issues)


def test_validator_catches_a_bogus_voice_index():
    prog = ProgramRom(bytes(layout.PROG_ROM_SIZE))
    prog.bank(0).set_voice_index(5, 200)
    issues = validate.check(prog, None)
    assert any("points at voice 200" in i.message for i in issues)
    assert validate.errors(issues)


def test_validator_summary_counts_both_kinds():
    assert validate.summarise([]) == "no problems found"
    issues = [
        validate.Issue(validate.ERROR, "a", "bad"),
        validate.Issue(validate.WARNING, "b", "iffy"),
    ]
    assert validate.summarise(issues) == "1 error and 1 warning"


def test_trim_silence_keeps_the_loud_part():
    body = np.array([0, 0, 0, 900, -900, 500, 0, 0, 0], dtype=np.int16)
    assert list(dsp.trim_silence(body)) == [900, -900, 500]


def test_trim_silence_on_pure_silence_returns_nothing():
    assert len(dsp.trim_silence(np.zeros(100, dtype=np.int16))) == 0


def test_normalize_reaches_full_scale_without_clipping():
    out = dsp.normalize(np.array([100, -50, 25], dtype=np.int16))
    assert int(np.abs(out).max()) == 2047
    assert out.min() >= -2048


def test_resample_halves_the_length():
    assert len(dsp.resample(np.zeros(1000, dtype=np.int16), 2.0)) == 500


def test_pitch_shift_up_an_octave_halves_it():
    assert len(dsp.pitch_shift(np.zeros(1000, dtype=np.int16), 12)) == 500


def test_zero_crossing_snaps_to_a_sign_change():
    wave = (np.sin(np.linspace(0, 8 * np.pi, 800)) * 1000).astype(np.int16)
    snapped = dsp.nearest_zero_crossing(wave, 210)
    assert abs(int(wave[snapped])) < 60


def test_suggest_loop_finds_one_in_a_steady_tone():
    wave = (np.sin(np.linspace(0, 200 * np.pi, 8000)) * 1000).astype(np.int16)
    assert dsp.suggest_loop(wave) is not None


def test_suggest_loop_declines_on_a_decayed_hit():
    n = 4000
    wave = (np.sin(np.linspace(0, 120 * np.pi, n))
            * np.exp(-np.linspace(0, 9, n)) * 2000).astype(np.int16)
    assert dsp.suggest_loop(wave) is None


def test_gain_is_reversible_within_rounding():
    start = np.array([400, -400, 200], dtype=np.int16)
    back = dsp.gain(dsp.gain(start, 6.0), -6.0)
    assert np.all(np.abs(back - start) <= 1)
