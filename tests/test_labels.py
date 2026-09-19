"""Custom wave names, kept beside the ROM rather than inside it."""

from tg100.labels import Labels


def test_a_name_survives_a_round_trip(tmp_path):
    rom = tmp_path / "tg100smpl.bin"
    rom.write_bytes(b"x")

    labels = Labels(Labels.sidecar_for(rom))
    labels.set_name(416, "Vibes loop")
    labels.set_note(416, "definitely not a music box")
    labels.save()

    back = Labels.load_for(rom)
    assert back.name(416) == "Vibes loop"
    assert back.note(416) == "definitely not a music box"
    assert back.has(416)
    assert len(back) == 1


def test_missing_sidecar_is_simply_empty(tmp_path):
    labels = Labels.load_for(tmp_path / "nothing.bin")
    assert len(labels) == 0
    assert labels.name(5) == ""
    assert not labels.has(5)


def test_a_corrupt_sidecar_does_not_raise(tmp_path):
    rom = tmp_path / "rom.bin"
    Labels.sidecar_for(rom).write_text("{ this is not json")
    assert len(Labels.load_for(rom)) == 0


def test_a_sidecar_holding_a_list_is_ignored(tmp_path):
    rom = tmp_path / "rom.bin"
    Labels.sidecar_for(rom).write_text("[1, 2, 3]")
    assert len(Labels.load_for(rom)) == 0


def test_clearing_a_name_removes_it(tmp_path):
    rom = tmp_path / "rom.bin"
    labels = Labels(Labels.sidecar_for(rom))
    labels.set_name(1, "Kick")
    labels.set_name(1, "   ")
    assert not labels.has(1)


def test_saving_nothing_leaves_no_file_behind(tmp_path):
    rom = tmp_path / "rom.bin"
    side = Labels.sidecar_for(rom)
    labels = Labels(side)
    labels.set_name(1, "Kick")
    labels.save()
    assert side.exists()
    labels.set_name(1, "")
    labels.save()
    assert not side.exists()


def test_string_keys_from_the_file_come_back_as_numbers(tmp_path):
    rom = tmp_path / "rom.bin"
    Labels.sidecar_for(rom).write_text('{"names": {"7": "Snare", "bad": "x"}}')
    labels = Labels.load_for(rom)
    assert labels.name(7) == "Snare"
    assert len(labels) == 1
