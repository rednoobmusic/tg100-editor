"""The sysex format, checked without needing a real dump.

The reference dumps these rules came from are not ours to ship, so the shapes
are rebuilt here from scratch. Point TG100_SYX_DIR at a directory of real .syx
captures and the last test in this file will round trip every one of them.
"""

import os
from pathlib import Path

import pytest

from tg100 import layout, sysex


def test_checksum_makes_the_low_seven_bits_come_out_zero():
    payload = bytes((0x30, 0x00, 0x0A, 0x00))
    check = sysex.checksum(payload)
    assert (sum(payload) + check) & 0x7F == 0
    assert check == 0x46


# The built in demo song changes the reverb with ordinary sysex writes. These
# three messages are lifted verbatim from the program ROM at 0x19643, 0x196D9
# and 0x196E3, which is the proof that one byte writes and whole dumps use the
# same message and not two different formats.
DEMO_SONG_MESSAGES = (
    ("F0 43 10 27 30 00 0A 00 46 F7", lambda: sysex.set_reverb_type(0)),
    ("F0 43 10 27 30 00 0B 21 24 F7", lambda: sysex.set_reverb_time(0x21)),
    ("F0 43 10 27 30 00 0C 40 04 F7", lambda: sysex.set_reverb_output_level(0x40)),
)


@pytest.mark.parametrize("expected,build", DEMO_SONG_MESSAGES)
def test_the_demo_song_reverb_messages_are_reproduced_exactly(expected, build):
    assert build() == bytes.fromhex(expected.replace(" ", ""))


def test_address_bytes_are_seven_bit():
    message = sysex.encode(0x0C0190, b"\x01")
    address, data = sysex.decode(message)
    assert message[4:7] == bytes((0x30, 0x03, 0x10))
    assert address == 0x0C0190
    assert data == b"\x01"


def test_device_number_lands_in_the_low_nibble():
    assert sysex.encode(0x0C0000, b"\x00", device=5)[2] == 0x15
    with pytest.raises(ValueError):
        sysex.encode(0x0C0000, b"\x00", device=16)


def test_decode_rejects_a_broken_checksum():
    message = bytearray(sysex.encode(0x0C0000, b"\x01"))
    message[-2] ^= 1
    with pytest.raises(sysex.SysexError, match="checksum"):
        sysex.decode(bytes(message))


def test_decode_rejects_another_makers_message():
    with pytest.raises(sysex.SysexError, match="Yamaha"):
        sysex.decode(bytes.fromhex("F0410027300000007FF7"))


def test_data_bytes_must_fit_in_seven_bits():
    with pytest.raises(ValueError, match="0..127"):
        sysex.encode(0x0C0000, b"\x80")


def test_stray_bytes_between_messages_are_skipped():
    blob = sysex.encode(0x0C0000, b"\x01") + b"\xC0\x00" + sysex.encode(0x0C0001, b"\x02")
    assert len(sysex.messages(blob)) == 2
    dump = sysex.Dump.from_syx(blob)
    assert dump.stray_bytes == 2


def test_an_unterminated_message_is_an_error():
    with pytest.raises(sysex.SysexError, match="never closed"):
        sysex.messages(b"\xF0\x43\x10\x27\x30\x00\x00")


def _filled_dump():
    dump = sysex.Dump(banks=bytearray(sysex.BANKS_SIZE))
    dump.system.master_tune = 128
    dump.system.transpose = 64
    dump.system.device_no = sysex.DEVICE_ALL
    dump.system.master_volume = 127
    dump.reverb.type = 1
    dump.reverb.time = 54
    dump.reverb.output_level = 70
    for i, part in enumerate(dump.parts):
        part.midi_channel = i
        part.program = i * 3
        part.volume = 100
        part.lfo_speed = 64
        part.eg_attack_rate = 57
        part.eg_release_rate = 71
        part.reverb_depth = 4
        part.detune = 128
        part.note_shift = 64
        part.aftertouch_pitch_control = 64
        part.lfo_depth = 64
        part.pitch_bend_range = 2
    for i, voice in enumerate(dump.voices):
        voice.name = f"Patch{i:02d}"[:8]
    for setup in dump.drum_setups:
        setup.level = 127
        setup.reverb_depth = 4
    return dump


def test_a_dump_survives_a_round_trip_in_both_styles():
    dump = _filled_dump()
    for style in sysex.STYLES:
        blob = dump.to_syx(style)
        back = sysex.Dump.from_syx(blob)
        assert back.multi == dump.multi
        if style == sysex.ALL:
            assert back.banks == dump.banks
        assert back.system.master_tune == 128
        assert back.reverb.type_name == "Hall2"
        assert back.part(3).program == 9
        assert back.voice(7).name == "Patch07"


def test_the_two_styles_have_the_sizes_the_hardware_sends():
    dump = _filled_dump()
    assert len(sysex.messages(dump.to_syx(sysex.ALL))) == 168
    assert len(dump.to_syx(sysex.ALL)) == 9323
    assert len(sysex.messages(dump.to_syx(sysex.SETUP))) == 164
    assert len(dump.to_syx(sysex.SETUP)) == 8266


def test_every_message_carries_exactly_one_record():
    dump = _filled_dump()
    sizes = {len(data) for _, data in dump.to_messages(sysex.ALL)}
    assert sizes == {3, 10, 24, 96, 256}
    sizes = {len(data) for _, data in dump.to_messages(sysex.SETUP)}
    assert sizes == {3, 6, 10, 24, 96}


def test_an_all_dump_puts_the_system_block_last():
    dump = _filled_dump()
    address, data = dump.to_messages(sysex.ALL)[-1]
    assert address == sysex.MULTI_BASE
    assert len(data) == sysex.SYSTEM_SIZE


def test_an_all_dump_leaves_the_three_unused_reverb_bytes_alone():
    dump = _filled_dump()
    reverb = [m for m in dump.to_messages(sysex.ALL) if m[0] == sysex.MULTI_BASE + sysex.REVERB_OFS]
    assert len(reverb) == 1 and len(reverb[0][1]) == 3
    back = sysex.Dump.from_syx(dump.to_syx(sysex.ALL))
    assert back.missing == [0x0C000D, 0x0C000E, 0x0C000F]


def test_a_setup_dump_cannot_be_asked_for_bank_maps_it_does_not_have():
    dump = sysex.Dump()
    assert not dump.has_banks
    with pytest.raises(sysex.SysexError, match="program change maps"):
        dump.to_syx(sysex.ALL)
    dump.add_banks()
    assert len(dump.to_syx(sysex.ALL)) == 9323


def test_part_slots_are_not_part_numbers():
    dump = sysex.Dump()
    assert dump.part(0).part_number == 10
    assert dump.part(1).part_number == 1
    assert dump.part(9).part_number == 9
    assert dump.part(10).part_number == 11
    assert dump.part(15).part_number == 16


def test_a_voice_in_ram_is_the_same_record_as_one_in_the_rom():
    dump = sysex.Dump()
    voice = dump.voice(3)
    assert voice.size == layout.VOICE_SIZE
    assert voice.offset == sysex.VOICES_OFS + 3 * layout.VOICE_SIZE
    voice.name = "dingus"
    voice.mode = 1
    voice.element(1).lfo_speed = 5
    back = sysex.Dump.from_syx(dump.to_syx(sysex.SETUP))
    assert back.voice(3).name == "dingus"
    assert back.voice(3).mode == 1
    assert back.voice(3).element(1).lfo_speed == 5


def test_drum_setups_cover_notes_27_to_108():
    dump = sysex.Dump()
    assert len(dump.drum_setups) == 82
    assert dump.drum_setup(27).offset == sysex.DRUMS_OFS
    assert dump.drum_setup(108).offset == sysex.DRUMS_OFS + 81 * 3
    with pytest.raises(IndexError):
        dump.drum_setup(26)
    with pytest.raises(IndexError):
        dump.drum_setup(109)


def test_out_of_range_notices_a_value_the_panel_could_not_produce():
    dump = _filled_dump()
    assert dump.out_of_range() == []
    dump.part(2).lfo_speed = 12
    found = dump.out_of_range()
    assert [f[0] for f in found] == ["part[2].lfo_speed"]
    assert found[0][1:] == (12, (57, 71))


def test_addresses_outside_the_known_regions_are_kept_not_dropped():
    blob = sysex.encode(0x000000, b"\x7F")
    dump = sysex.Dump.from_syx(blob)
    assert dump.extra == [(0x000000, b"\x7F")]


def test_a_later_message_wins_over_an_earlier_one():
    blob = sysex.encode(0x0C0011, b"\x05") + sysex.encode(0x0C0011, b"\x09")
    dump = sysex.Dump.from_syx(blob)
    assert dump.part(0).program == 9


def test_voice_message_refuses_the_wrong_length():
    with pytest.raises(ValueError, match="96 bytes"):
        sysex.voice_message(0, bytes(95))
    assert len(sysex.voice_message(0, bytes(96))) == 96 + 9


CORPUS = os.environ.get("TG100_SYX_DIR")


@pytest.mark.skipif(not CORPUS, reason="set TG100_SYX_DIR to a directory of real dumps")
def test_real_dumps_round_trip_byte_for_byte():
    paths = sorted(Path(CORPUS).glob("*.syx"))
    assert paths, f"no .syx files in {CORPUS}"
    for path in paths:
        raw = path.read_bytes()
        dump = sysex.Dump.from_syx(raw)
        assert dump.extra == [], f"{path.name} writes outside the known regions"
        assert dump.out_of_range() == [], f"{path.name} has values the panel cannot make"

        # A capture can hold a dump plus whatever the owner did next, so
        # compare only files whose messages each land on a distinct address.
        pairs = sysex.parse(raw)
        if len({address for address, _ in pairs}) != len(pairs):
            continue
        clean = b"".join(sysex.messages(raw))
        assert dump.to_syx() == clean, f"{path.name} did not come back the same"
