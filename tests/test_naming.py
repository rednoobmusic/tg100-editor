from tg100 import naming


def test_note_names_use_yamaha_numbering():
    assert naming.note_name(60) == "C3"
    assert naming.note_name(0) == "C-2"
    assert naming.note_name(127) == "G8"


def test_pan_follows_the_hardware_mix_table():
    """Checked against TG101's mPanMixTbl, which is not a symmetric sweep.

    0 is both channels at 0 dB, 8 mutes both, and the left half counts
    backwards from 9. Treating 8 as the centre gets every value wrong.
    """
    assert naming.pan(0) == "centre"
    assert naming.pan(8) == "silent"
    assert naming.pan(7) == "hard right"
    assert naming.pan(9) == "hard left"
    assert naming.pan(1) == "right 1"
    assert naming.pan(15) == "left 1"
    assert naming.pan(10) == "left 6"


def test_pan_never_calls_two_values_the_same_thing():
    labels = [naming.pan(v) for v in range(16)]
    assert len(set(labels)) == 16


def test_semitones_gets_the_plural_right():
    assert naming.semitones(0) == "none"
    assert naming.semitones(1) == "+1 semitone"
    assert naming.semitones(-1) == "-1 semitone"
    assert naming.semitones(12) == "+12 semitones"


def test_detune_centre():
    assert naming.detune(64) == "centre"
    assert naming.detune(70) == "+6"


def test_gm_and_percussion_lists_are_complete():
    assert len(naming.GM_PROGRAMS) == 128
    assert naming.gm_program(0) == "Acoustic Grand Piano"
    assert naming.percussion_name(36) == "Bass Drum 1"
    # the XG additions the TG100 also carries
    assert naming.percussion_name(29) == "Scratch Push"
    # The TG100 puts taiko drums at 86 and 87, not the XG surdos. Standard kit
    # note 86 goes to wave 265 and note 87 to wave 69, which TG101 names
    # Taiko-Drum High and Taiko-Drum Low.
    assert naming.percussion_name(86) == "Taiko Drum High"
    assert naming.percussion_name(87) == "Taiko Drum Low"


class _FakeElement:
    def __init__(self, wave_no):
        self.wave_no = wave_no


class _FakeVoice:
    def __init__(self, index, name, mode, waves):
        self.index, self.name, self.mode = index, name, mode
        self._waves = waves

    def element(self, i):
        return _FakeElement(self._waves[i])


class _FakeBank:
    def __init__(self, name, mapping):
        self.name = name
        self._mapping = mapping

    def voice_index(self, program):
        return self._mapping.get(program, 255)


class _FakeProg:
    """Just enough of a ProgramRom for the naming rules."""

    def __init__(self, voices, banks=None):
        self._voices = voices
        self._banks = banks or {}

    def bank(self, index):
        return _FakeBank(
            {0: "General MIDI", 1: "Disk Orchestra"}.get(index, f"bank {index}"),
            self._banks.get(index, {}),
        )

    def voice_names(self):
        return [v.name for v in self._voices]

    def voices(self):
        return self._voices

    def sample_sets_for(self, wave_no):
        return []

    def drum_kits(self):
        return []


def test_a_voice_that_plays_a_wave_alone_beats_a_lower_numbered_layer():
    # This is the MusicBox / Vibes case from the real ROM. MusicBox is the lower
    # voice number but only layers the wave, Vibes plays it on its own.
    prog = _FakeProg([
        _FakeVoice(10, "MusicBox", 1, [99, 10]),
        _FakeVoice(11, "Vibes", 0, [10, 0]),
    ])
    names = naming.Names(prog)
    assert names.wave_no(10) == "Vibes"
    assert names.is_weak(10) is False


def test_a_wave_only_ever_layered_is_marked_as_a_guess():
    prog = _FakeProg([_FakeVoice(150, "EfctJngl", 1, [99, 95])])
    names = naming.Names(prog)
    assert names.wave_no(95) == "EfctJngl"
    assert names.is_weak(95) is True


def test_roles_are_reported_for_every_voice():
    prog = _FakeProg([
        _FakeVoice(10, "MusicBox", 1, [99, 10]),
        _FakeVoice(11, "Vibes", 0, [10, 0]),
    ])
    roles = naming.Names(prog).voice_roles(10)
    assert "Vibes (whole voice)" in roles
    assert "MusicBox (layer 2)" in roles


def test_an_unused_wave_number_has_no_name_and_is_not_weak():
    names = naming.Names(_FakeProg([_FakeVoice(0, "GrandPno", 0, [1, 0])]))
    assert names.is_weak(77) is False
    assert names.wave_no(77) == "wave no 77"


def test_zone_numbers_a_multisample():
    """A piano is ten recordings, so "4 of 10" beats a bare key range."""
    class _Set:
        def __init__(self, wave, low, high):
            self.wave_index, self.note_low, self.note_high = wave, low, high

    class _Prog(_FakeProg):
        def sample_sets_for(self, wave_no):
            if wave_no != 1:
                return []
            return [_Set(494 + i, 20 + i * 9, 28 + i * 9) for i in range(10)]

    prog = _Prog([_FakeVoice(0, "GrandPno", 0, [1, 0])])
    names = naming.Names(prog)
    assert names.zone(494) == (1, 10)
    assert names.zone(497) == (4, 10)
    assert "GrandPno 4/10" in names.short(497)
    assert names.category(497) == "instrument"


def test_category_tells_drums_from_instruments():
    names = naming.Names(_FakeProg([_FakeVoice(0, "GrandPno", 0, [1, 0])]))
    assert names.category(999 % 512) == "unused"


def test_voice_family_comes_from_where_it_is_reachable():
    """GM groups programs in families of eight, and the TG100 follows that."""
    prog = _FakeProg(
        [_FakeVoice(0, "GrandPno", 0, [1, 0]), _FakeVoice(48, "Ensmble1", 0, [9, 0])],
        banks={0: {0: 0, 48: 48}},
    )
    names = naming.Names(prog)
    assert names.voice_family(0) == "Piano"
    assert names.voice_family(48) == "Ensemble"
    assert "General MIDI 0" in names.voice_usage(0)


def test_a_voice_no_bank_points_at_is_flagged():
    prog = _FakeProg([_FakeVoice(0, "GrandPno", 0, [1, 0])], banks={0: {}})
    assert naming.Names(prog).voice_family(0) == "unreachable"


def test_a_voice_only_in_another_bank_has_no_gm_family():
    prog = _FakeProg([_FakeVoice(5, "SynHarmo", 0, [1, 0])], banks={1: {33: 5}})
    assert naming.Names(prog).voice_family(5) == "other banks"


def test_gm_families_cover_all_128_programs():
    assert len(naming.GM_FAMILIES) == 16
    assert naming.gm_family(0) == "Piano"
    assert naming.gm_family(127) == "Sound effects"
    assert naming.gm_family(200) == ""
