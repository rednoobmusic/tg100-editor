"""Where everything lives in the two TG100 ROMs.

Offsets below were taken from TaleTN's TG101 engine and checked byte for byte
against XK731C0 v1.10. The program ROM is 128K, H8/520 code in the lower half,
lookup data in the upper half. The sample ROM is 2M, a table of 512 wave
headers followed by packed 12 bit PCM.
"""

PROG_ROM_SIZE = 128 * 1024
SMPL_ROM_SIZE = 2 * 1024 * 1024

# sha1 of the only dump anyone has, XK731C0 v1.10
PROG_ROM_SHA1 = "483103a2ffc63a90a2086c597baa2b2745c3a1c2"
SMPL_ROM_SHA1 = "32ec77a46f4d005538c735f56ad48fa7243c63be"

# program ROM
VOICE_BANK_TBL = 0x14C90       # 128 bytes, midi bank number to bank index
BANK_GM = 0x10000              # FOUR banks of 256 bytes, GM DOC CM64a CM64b
BANK_INTERNAL = 0x14D10        # 256 bytes
VOICE_MEM = 0x10410            # 192 voices
DRUM_BANK = 0x14C10            # 128 bytes, program number to kit index
DRUM_KITS = 0x18B9E            # 10 kits
SAMPLE_SET_TBL = 0x1841A       # 141 words, wave number to first sample set
SAMPLE_SETS = 0x176A2          # 383 sets
DRUM_SOUNDS = 0x18532          # 274 sounds

PITCH_TBL = 0x14E2C            # 1200 words, one per cent
VOLUME_TBL = 0x1578C           # 128 bytes
VELOCITY_TBL = 0x1580C         # 8 curves of 128
PORTA_TIME_TBL = 0x1640C       # 128 bytes
PITCH_EG_RATE_TBL = 0x164A8    # 64 bytes
REVERB_TIME_TBL = 0x17160      # 60 bytes, the last 4 of 64 are padding
REVERB_FEEDBACK_TBL = 0x171A8  # 256 words
REVERB_GAIN_TBL = 0x173D0      # 256 words
REVERB_TYPE_NAMES = 0x167D8    # 8 names of 8 chars
DRUM_KIT_NAMES = 0x16A80       # 12 slots of 8 chars

VOICE_SIZE = 96
VOICE_ELEMENT_SIZE = 36
VOICE_NAME_OFS = 16
VOICE_NAME_LEN = 8
NUM_VOICES = 192
# Four, not five. TG101 copies (kNumVoiceBanks - 1) = 4 banks from here, and its
# Drums entry falls back to General MIDI rather than having a table of its own.
# A fifth bank would start at 0x10400, which holds the firmware version string
# and then runs 240 bytes into voice memory, so writing to it destroys voice 0.
NUM_VOICE_BANKS = 4
NUM_SAMPLE_SETS = 383
SAMPLE_SET_SIZE = 9
NUM_WAVE_NOS = 140
NUM_DRUM_SOUNDS = 274
DRUM_SOUND_SIZE = 6
NUM_DRUM_KITS = 10
DRUM_KIT_SIZE = 256
DRUM_NOTE_MIN = 27
DRUM_NOTE_MAX = 108
END_OF_SAMPLE_SETS = 511
DRUM_SOUND_OFF = 511
VOICE_OFF = 255

# sample ROM
WAVE_HDR_BASE = 0x0000
WAVE_HDR_SIZE = 12
NUM_WAVES = 512
SAMPLE_DATA_START = NUM_WAVES * WAVE_HDR_SIZE  # 0x1800

# Drum kit names are not stored in kit order, these are the byte offsets into
# the name block for kits 0..9 plus the Jazz variant and an unused blank slot.
DRUM_KIT_NAME_OFS = (0, 8, 16, 24, 32, 48, 56, 72, 80, 88, 40, 64)

REVERB_TYPE_NAMES_ORDER = (
    "Hall1", "Hall2", "Room1", "Room2",
    "Plate1", "Plate2", "Delay1", "Delay2",
)

VOICE_BANK_NAMES = (
    "General MIDI",
    "Disk Orchestra",
    "C/M 64 parts 1-9",
    "C/M 64 parts 11-16",
)

# ASCII build stamp sitting between the bank block and voice memory, reading
# "#0068  VER=1.10 " in the dump this was checked against.
FIRMWARE_STAMP = 0x10400
FIRMWARE_STAMP_LEN = 16
