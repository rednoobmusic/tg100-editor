"""Human readable names and units for everything in the ROMs.

Two kinds of name live here. The fixed lists (GM programs, percussion notes)
are standards the TG100 follows. Everything else is worked out from the ROM
itself, because the ROM is the authority on what a wave is actually used for
and no name list can go stale that way.

The neutral points below were checked against the dump rather than assumed. Of
249 sounding elements, 191 have detune 64 and 233 have note shift 64, and note
shift spans exactly 40 to 88, which is plus or minus two octaves in semitones.
Pitch rate scale centre is 60 on 249 of them, middle C. Sample set root notes
span 31 to 109 and match the "note" field in vampirefrog's region dump.
"""

from . import layout

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

DETUNE_CENTRE = 64
NOTE_SHIFT_CENTRE = 64
PAN_CENTRE = 8
PAN_FOLLOWS_VOICE = 0


def note_name(n):
    """MIDI note number to name. 60 is C3 in Yamaha's numbering."""
    if not 0 <= n <= 127:
        return str(n)
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 2}"


def note_range(low, high):
    return f"{note_name(low)} to {note_name(high)}"


def detune(value):
    d = value - DETUNE_CENTRE
    return "centre" if d == 0 else f"{d:+d}"


def semitones(d):
    if d == 0:
        return "none"
    return f"{d:+d} semitone{'s' if abs(d) != 1 else ''}"


def note_shift(value):
    return semitones(value - NOTE_SHIFT_CENTRE)


def pan(value):
    """0 means the element follows the voice, 1 to 15 are fixed positions."""
    if value == PAN_FOLLOWS_VOICE:
        return "follows voice"
    d = value - PAN_CENTRE
    if d == 0:
        return "centre"
    return f"{'L' if d < 0 else 'R'}{abs(d)}"


def attenuation(value):
    return "full level" if value == 0 else f"-{value}"


def fine_tune(value):
    return "in tune" if value == 0 else f"+{value} cents"


GM_PROGRAMS = (
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano",
    "Honky-tonk Piano", "Electric Piano 1", "Electric Piano 2", "Harpsichord",
    "Clavi", "Celesta", "Glockenspiel", "Music Box", "Vibraphone", "Marimba",
    "Xylophone", "Tubular Bells", "Dulcimer", "Drawbar Organ",
    "Percussive Organ", "Rock Organ", "Church Organ", "Reed Organ",
    "Accordion", "Harmonica", "Tango Accordion", "Acoustic Guitar (nylon)",
    "Acoustic Guitar (steel)", "Electric Guitar (jazz)",
    "Electric Guitar (clean)", "Electric Guitar (muted)", "Overdriven Guitar",
    "Distortion Guitar", "Guitar Harmonics", "Acoustic Bass",
    "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2", "Violin",
    "Viola", "Cello", "Contrabass", "Tremolo Strings", "Pizzicato Strings",
    "Orchestral Harp", "Timpani", "String Ensemble 1", "String Ensemble 2",
    "SynthStrings 1", "SynthStrings 2", "Choir Aahs", "Voice Oohs",
    "Synth Voice", "Orchestra Hit", "Trumpet", "Trombone", "Tuba",
    "Muted Trumpet", "French Horn", "Brass Section", "Synth Brass 1",
    "Synth Brass 2", "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet", "Piccolo", "Flute",
    "Recorder", "Pan Flute", "Blown Bottle", "Shakuhachi", "Whistle",
    "Ocarina", "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)",
    "Lead 4 (chiff)", "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)",
    "Lead 8 (bass + lead)", "Pad 1 (new age)", "Pad 2 (warm)",
    "Pad 3 (polysynth)", "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)",
    "Pad 7 (halo)", "Pad 8 (sweep)", "FX 1 (rain)", "FX 2 (soundtrack)",
    "FX 3 (crystal)", "FX 4 (atmosphere)", "FX 5 (brightness)",
    "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)", "Sitar", "Banjo",
    "Shamisen", "Koto", "Kalimba", "Bag pipe", "Fiddle", "Shanai",
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock", "Taiko Drum",
    "Melodic Tom", "Synth Drum", "Reverse Cymbal", "Guitar Fret Noise",
    "Breath Noise", "Seashore", "Bird Tweet", "Telephone Ring", "Helicopter",
    "Applause", "Gunshot",
)

# Yamaha's extended percussion map. Notes 35 to 81 are plain GM, the rest are
# the XG additions the TG100 also carries. Notes 29 and 30 mapping to drum
# sounds 0 and 1 lines up with TG101 naming those Scratch Push and Scratch
# Pull, which is what confirms this map rather than the plain GM one.
PERCUSSION = {
    25: "Snare Roll", 26: "Finger Snap", 27: "High Q", 28: "Slap",
    29: "Scratch Push", 30: "Scratch Pull", 31: "Sticks",
    32: "Square Click", 33: "Metronome Click", 34: "Metronome Bell",
    35: "Acoustic Bass Drum", 36: "Bass Drum 1", 37: "Side Stick",
    38: "Acoustic Snare", 39: "Hand Clap", 40: "Electric Snare",
    41: "Low Floor Tom", 42: "Closed Hi-hat", 43: "High Floor Tom",
    44: "Pedal Hi-hat", 45: "Low Tom", 46: "Open Hi-hat", 47: "Low-Mid Tom",
    48: "Hi-Mid Tom", 49: "Crash Cymbal 1", 50: "High Tom",
    51: "Ride Cymbal 1", 52: "Chinese Cymbal", 53: "Ride Bell",
    54: "Tambourine", 55: "Splash Cymbal", 56: "Cowbell",
    57: "Crash Cymbal 2", 58: "Vibraslap", 59: "Ride Cymbal 2",
    60: "Hi Bongo", 61: "Low Bongo", 62: "Mute Hi Conga",
    63: "Open Hi Conga", 64: "Low Conga", 65: "High Timbale",
    66: "Low Timbale", 67: "High Agogo", 68: "Low Agogo", 69: "Cabasa",
    70: "Maracas", 71: "Short Whistle", 72: "Long Whistle",
    73: "Short Guiro", 74: "Long Guiro", 75: "Claves",
    76: "Hi Wood Block", 77: "Low Wood Block", 78: "Mute Cuica",
    79: "Open Cuica", 80: "Mute Triangle", 81: "Open Triangle",
    82: "Shaker", 83: "Jingle Bell", 84: "Bell Tree", 85: "Castanets",
    86: "Mute Surdo", 87: "Open Surdo",
}


def percussion_name(note):
    return PERCUSSION.get(note, f"note {note}")


def gm_program(program):
    if 0 <= program < len(GM_PROGRAMS):
        return GM_PROGRAMS[program]
    return f"program {program}"


class Names:
    """Names worked out from a loaded program ROM.

    Build one after loading and hand it to the widgets. Everything is computed
    once because walking 140 wave numbers and 10 drum kits on every repaint
    would be silly.
    """

    def __init__(self, prog):
        self.prog = prog
        self.voice_names = prog.voice_names()
        self.wave_no_names = {}
        self.wave_no_users = {}
        self.wave_users = {}
        self.wave_names = {}
        self._build()

    def _build(self):
        # Which voices use each wave number. Order matters: the lowest voice
        # index wins the name, because the GM banks are laid out in program
        # order so voice 0 really is the grand piano. Sorting alphabetically
        # would label wave number 1 "ElPiano2", which helps nobody.
        by_wave_no = {}
        for v in self.prog.voices():
            for i in range(2 if v.mode else 1):
                by_wave_no.setdefault(v.element(i).wave_no, []).append(
                    (v.index, v.name)
                )

        for wave_no in range(layout.NUM_WAVE_NOS):
            users = by_wave_no.get(wave_no, [])
            if not users:
                self.wave_no_names[wave_no] = ""
                continue
            seen = []
            for _, name in sorted(users):
                if name not in seen:
                    seen.append(name)
            self.wave_no_names[wave_no] = seen[0]
            self.wave_no_users[wave_no] = seen

        # Which sample sets and drum sounds point at each wave table slot.
        for wave_no in range(layout.NUM_WAVE_NOS):
            label = self.wave_no_names.get(wave_no, "")
            if not label:
                continue
            for ss in self.prog.sample_sets_for(wave_no):
                self.wave_users.setdefault(ss.wave_index, []).append(
                    f"{label} {note_range(ss.note_low, ss.note_high)}"
                )

        for kit in self.prog.drum_kits():
            for note in kit.mapped_notes():
                ds = self.prog.drum_sound(kit.sound_index(note))
                self.wave_users.setdefault(ds.wave_index, []).append(
                    f"{kit.name} {percussion_name(note)}"
                )

        for index in range(layout.NUM_WAVES):
            users = self.wave_users.get(index, [])
            if not users:
                self.wave_names[index] = ""
                continue
            extra = len(users) - 1
            self.wave_names[index] = (
                users[0] if not extra else f"{users[0]} and {extra} more"
            )

    def wave(self, index):
        return self.wave_names.get(index, "")

    def wave_no(self, wave_no):
        """Name of a wave number, or a plain label if nothing uses it."""
        return self.wave_no_names.get(wave_no) or f"wave no {wave_no}"

    def voices_using(self, wave_no):
        return self.wave_no_users.get(wave_no, [])

    def users_of(self, index):
        return self.wave_users.get(index, [])

    def voice(self, index):
        if 0 <= index < len(self.voice_names):
            return self.voice_names[index]
        return "off" if index == layout.VOICE_OFF else f"voice {index}"
