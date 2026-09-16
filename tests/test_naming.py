from tg100 import naming


def test_note_names_use_yamaha_numbering():
    assert naming.note_name(60) == "C3"
    assert naming.note_name(0) == "C-2"
    assert naming.note_name(127) == "G8"


def test_pan_describes_both_sides_and_the_follow_case():
    assert naming.pan(0) == "follows voice"
    assert naming.pan(8) == "centre"
    assert naming.pan(1) == "L7"
    assert naming.pan(15) == "R7"


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
    assert naming.percussion_name(87) == "Open Surdo"
