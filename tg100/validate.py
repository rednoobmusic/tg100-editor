"""Check that the two ROMs still make sense together.

There are around 1700 references between the program ROM and the sample ROM,
and almost none of them are visible while you are editing. A sample set points
at a wave, a drum kit points at a drum sound which points at another wave, a
bank points at a voice which points at a wave number which resolves through a
table into a run of sample sets. Break any link and the module goes quiet in a
way that is very hard to trace back to the edit that caused it.

Nothing here modifies a ROM. Run it before saving and read the result.
"""

from . import layout

ERROR = "error"
WARNING = "warning"


class Issue:
    __slots__ = ("level", "where", "message", "hint")

    def __init__(self, level, where, message, hint=""):
        self.level = level
        self.where = where
        self.message = message
        self.hint = hint

    @property
    def is_error(self):
        return self.level == ERROR

    def __repr__(self):
        return f"<{self.level} {self.where}: {self.message}>"

    def __str__(self):
        out = f"{self.level}: {self.where}: {self.message}"
        return f"{out}\n    {self.hint}" if self.hint else out


def _check_waves(smpl, out):
    for w in smpl.waves():
        if w.is_empty:
            continue
        if w.start < layout.SAMPLE_DATA_START:
            out.append(Issue(
                ERROR, f"wave {w.index}",
                f"starts at 0x{w.start:06X}, inside the header table",
                "wave data has to begin at 0x1800 or later",
            ))
        if w.start + w.byte_length > smpl.size:
            out.append(Issue(
                ERROR, f"wave {w.index}",
                f"runs to 0x{w.start + w.byte_length:06X}, past the end of the ROM",
            ))
        if w.format != 3:
            out.append(Issue(
                WARNING, f"wave {w.index}",
                f"format is {w.format}, every wave in the factory ROM is 12 bit",
            ))
        if w.loops and w.loop >= w.length:
            out.append(Issue(
                ERROR, f"wave {w.index}",
                f"loop point {w.loop} is past its length {w.length}",
            ))


def _check_sample_sets(prog, smpl, out):
    table = prog.sample_set_table()
    for wave_no in range(layout.NUM_WAVE_NOS):
        start, stop = table.span(wave_no)
        if start > stop:
            out.append(Issue(
                ERROR, f"wave number {wave_no}",
                f"its sample set span runs backwards, {start} to {stop}",
                "the wave number table has to increase, so this wave number "
                "resolves to nothing and the voice goes silent",
            ))

    for i in range(layout.NUM_SAMPLE_SETS):
        ss = prog.sample_set(i)
        if ss.note_low > ss.note_high:
            out.append(Issue(
                ERROR, f"sample set {i}",
                f"key range runs backwards, {ss.note_low} down to {ss.note_high}",
            ))
        if ss.wave_index == layout.END_OF_SAMPLE_SETS:
            continue
        if ss.wave_index >= layout.NUM_WAVES:
            out.append(Issue(
                ERROR, f"sample set {i}",
                f"points at wave {ss.wave_index}, which does not exist",
            ))
        elif smpl is not None and smpl.wave(ss.wave_index).is_empty:
            out.append(Issue(
                ERROR, f"sample set {i}",
                f"points at wave {ss.wave_index}, which is an empty slot",
                "that key range will make no sound",
            ))


def _check_drums(prog, smpl, out):
    for kit in prog.drum_kits():
        for note in range(128):
            idx = kit.sound_index(note)
            if idx == layout.DRUM_SOUND_OFF:
                continue
            if idx >= layout.NUM_DRUM_SOUNDS:
                out.append(Issue(
                    ERROR, f"{kit.name} kit note {note}",
                    f"points at drum sound {idx}, which does not exist",
                ))

    for i in range(layout.NUM_DRUM_SOUNDS):
        ds = prog.drum_sound(i)
        if ds.wave_index == layout.DRUM_SOUND_OFF:
            continue
        if ds.wave_index >= layout.NUM_WAVES:
            out.append(Issue(
                ERROR, f"drum sound {i}",
                f"points at wave {ds.wave_index}, which does not exist",
            ))
        elif smpl is not None and smpl.wave(ds.wave_index).is_empty:
            out.append(Issue(
                ERROR, f"drum sound {i}",
                f"points at wave {ds.wave_index}, which is an empty slot",
            ))


def _check_banks(prog, out):
    for index in range(-1, layout.NUM_VOICE_BANKS):
        bank = prog.bank(index)
        for program in range(128):
            voice = bank.voice_index(program)
            if voice == layout.VOICE_OFF:
                continue
            if voice >= layout.NUM_VOICES:
                out.append(Issue(
                    ERROR, f"{bank.name} bank program {program}",
                    f"points at voice {voice}, but there are only "
                    f"{layout.NUM_VOICES}",
                ))


def _check_voices(prog, out):
    for v in prog.voices():
        for i in range(2 if v.mode else 1):
            wave_no = v.element(i).wave_no
            if wave_no >= layout.NUM_WAVE_NOS:
                out.append(Issue(
                    ERROR, f"voice {v.index} ({v.name}) element {i + 1}",
                    f"uses wave number {wave_no}, but there are only "
                    f"{layout.NUM_WAVE_NOS}",
                ))
            elif not prog.sample_sets_for(wave_no):
                out.append(Issue(
                    WARNING, f"voice {v.index} ({v.name}) element {i + 1}",
                    f"wave number {wave_no} has no sample sets, so it is silent",
                ))


def _check_shared_bytes(prog, out):
    """The one place two unrelated structures share ROM bytes.

    The sample set table ends at 0x18534 and the drum sounds begin at 0x18532,
    so drum sound 0's wave index word IS the table's end marker. Changing one
    changes the other, and nothing about either screen would tell you.
    """
    table_end = layout.SAMPLE_SET_TBL + (layout.NUM_WAVE_NOS + 1) * 2
    if layout.DRUM_SOUNDS < table_end:
        terminator = prog.sample_set_table().first(layout.NUM_WAVE_NOS)
        if terminator != layout.END_OF_SAMPLE_SETS:
            out.append(Issue(
                ERROR, "sample set table",
                f"its end marker reads {terminator} rather than "
                f"{layout.END_OF_SAMPLE_SETS}",
                "drum sound 0's wave index is the same two bytes, so editing "
                "that drum sound moved the marker and wave number 139 lost its "
                "sample sets",
            ))


def check(prog=None, smpl=None):
    """Return every problem found. An empty list means both ROMs hang together."""
    out = []
    if smpl is not None:
        _check_waves(smpl, out)
    if prog is not None:
        _check_sample_sets(prog, smpl, out)
        _check_drums(prog, smpl, out)
        _check_banks(prog, out)
        _check_voices(prog, out)
        _check_shared_bytes(prog, out)
    return out


def errors(issues):
    return [i for i in issues if i.is_error]


def summarise(issues):
    bad = len(errors(issues))
    warn = len(issues) - bad
    if not issues:
        return "no problems found"
    bits = []
    if bad:
        bits.append(f"{bad} error{'s' if bad != 1 else ''}")
    if warn:
        bits.append(f"{warn} warning{'s' if warn != 1 else ''}")
    return " and ".join(bits)
