# TG100 ROM editor

An editor for the ROMs inside the Yamaha TG100, the half rack General MIDI
module Yamaha shipped in 1991. It reads both ROM images, shows you what is
actually in them with real names instead of raw numbers, and writes the changes
back out.

No ROM data ships with this project. You supply your own dumps.

## Status

Early but working. Waves, voices, drum kits and program change maps are all
editable and save correctly. The lookup tables are readable but not yet
editable from the interface, though `tg100.tables` can write them.

## Running it

```
pip install -r requirements.txt
python3 -m tg100 tg100prog.bin tg100smpl.bin
```

Both file arguments are optional, and either can be opened from the File menu
later. Files are recognised by size, so the order does not matter.

There is a terminal tool as well, for when you want to grep something:

```
python3 tools/tg100dump.py tg100prog.bin tg100smpl.bin waves
python3 tools/tg100dump.py tg100prog.bin tg100smpl.bin space
python3 tools/tg100dump.py tg100prog.bin tg100smpl.bin export 494 piano.wav
```

## What it does

**Waves.** All 512 wave table slots, 489 of which are used. Waveform display
with the loop region shaded, zoom down to individual samples, and audition at
any pitch. Export any wave to WAV and replace it from a WAV. The per wave LFO,
vibrato, tremolo and five stage amplitude envelope are editable.

There is a One shot tick box, because the format has no loop flag and encodes a
single hit as a loop point sitting on the end of the wave. Nobody would guess
that from a loop point box, so the interface says it in words and shows how many
samples actually repeat. Sixty four waves in the factory ROM are single hits
whose loop point sits three to thirty one samples early, which leaves the
hardware repeating a sliver of near silence instead of stopping. TG101 disables
those on load. Tools has a menu item that does the same here, and each of them
says so when you select it.

**Voices.** All 192 voices, both elements, with names you can edit and every
parameter labelled. Values that have a neutral point show it, so detune 64
reads as "centre" and note shift 76 reads as "+12 semitones" rather than
leaving you to work it out.

**Drums.** Ten kits with proper percussion names, and the drum sounds behind
them. The list says how many kits share each sound before you change it.

**Checking and space.** Tools has a check that walks every reference between
the two ROMs, about 1700 of them, and says which edit broke what. It runs
before every save. Alongside it is a space report and a repack, described
below.

**Editing the audio.** Trim silence, normalize, fade, halve the sample rate,
snap a loop point to the nearest zero crossing, and search for a loop whose
seam matches the tail. The loop search declines rather than guessing when a
wave has decayed into silence, because a single hit has nothing to loop.

**Banks.** The Internal map plus the four in the block at `0x10000`, with the
General MIDI name alongside so you can see where Yamaha's choice differs from
the standard. There is no fifth bank, whatever the voice bank names might
suggest. The address one would occupy holds the firmware build stamp and then
runs 240 bytes into voice memory.

## Three things worth knowing before you edit

**The sample ROM is full.** There are 144 free bytes across 142 gaps, and the
largest is 3 bytes. A longer replacement sample has to go somewhere, so the
editor offers to truncate it or to move it, and moving only works once you have
freed a run somewhere else.

Freeing a run has two steps. Shorten something, then repack. Repack slides
every wave down so the holes close and the free space collects in one run at
the top, which is the only way a longer sample ever fits. Only addresses move,
never sample data, and waves that share audio move together and keep sharing.

Be warned about where the space comes from. Trimming the silence off every
single wave in the ROM is worth under 3 KB, because Yamaha already trimmed it.
Real room comes from giving something up: halving the sample rate of one long
wave frees 23 KB on its own, which is eight times what trimming the entire ROM
achieves. The editor shows you the budget, but it cannot invent space that is
not there.

**Waves share their audio.** 489 headers point at only 324 distinct regions.
Wave 2, 143 and 144 are the same recording, and ten headers share the region at
0x0678D8. That aliasing saves Yamaha about 2.1M in a 2M ROM, and it means
replacing one wave can change several sounds at once. The editor warns you and
names the others.

One wave is worth singling out. Wave 45 stores its length as the word `0x0006`,
which decodes to 65530 samples, and it is the only wave in the ROM past 40000.
It starts where wave 28 starts and runs straight across twenty other waves, so
most of what you hear in it is bongos and congas and then a choir that has
nothing to do with it. Both public references decode that field the same way, so
it is the data that is strange rather than the reading of it. The editor says so
when you select it.

**Wave names are guesses.** The sample ROM holds no text at all, so there is
nothing to look up and every name here is worked out from the program ROM. A
wave is named after the voices that play it, preferring a voice that plays it
alone over one that only layers it underneath something else. That distinction
matters more than it sounds. Wave number 10 is played alone by Vibes and layered
by MusicBox, and naming it after the lower numbered voice would call a
vibraphone a music box. 41 of the 140 wave numbers have no voice that plays them
alone at all, so their names rest on nothing but a layer. Those are marked with a
question mark in the list, and the panel underneath names every voice that uses
the wave and how, rather than showing you one winner and hiding the rest.

## ROM layout

Worked out from TaleTN's TG101 engine and vampirefrog's notes, then checked
against the v1.10 dump, SHA1 `483103a2…`. Everything lives in the upper 64K of
the program ROM, with the H8/520 code below it.

| Offset | Contents |
| --- | --- |
| `0x10000` | Program change maps, four banks: GM, Disk Orchestra, two C/M 64 |
| `0x10400` | ASCII build stamp, `#0068  VER=1.10` in this dump |
| `0x10410` | 192 voices, 96 bytes each |
| `0x14C10` | Program number to drum kit |
| `0x14C90` | MIDI bank select to bank index |
| `0x14D10` | Internal bank program changes |
| `0x14E2C` | Pitch table, 1200 words, one per cent |
| `0x1578C` | Volume table |
| `0x1580C` | Eight velocity curves of 128 |
| `0x1640C` | Portamento time |
| `0x164A8` | Pitch EG rate |
| `0x167D8` | Reverb type names |
| `0x16A80` | Drum kit names |
| `0x17160` | Reverb time, feedback at `0x171A8`, gain at `0x173D0` |
| `0x176A2` | 383 sample sets, 9 bytes each |
| `0x1841A` | Wave number to sample set index |
| `0x18532` | 274 drum sounds, 6 bytes each |
| `0x18B9E` | 10 drum kits, 256 bytes each |

The sample ROM is simpler: 512 headers of 12 bytes at the start, then packed
12 bit PCM from `0x1800` to the very end of the 2M. The wave table clocks at
9.4 MHz divided by 224, or 41964.29 Hz, which is the rate an exported wave
plays back at.

## A note on the sample format

Three bytes hold two samples. The middle byte is split, and the two public
references disagree about which way round:

```
even = (b0 << 4) | (b1 & 0x0F)
odd  = (b2 << 4) | (b1 >> 4)
```

TG101 assigns those nibbles the other way. The difference only touches the
bottom four bits of each sample, which is why it has gone unnoticed, but it is
measurable. Decoding all 489 waves both ways and comparing the mean absolute
second difference, the order above is smoother on 439 waves against 18 for
TG101's, and real recorded audio is correlated sample to sample where a
misplaced nibble is not. Set `NIBBLE_ORDER_TG101` in `tg100/codec.py` if a
hardware capture ever settles it the other way.

## Credits

The ROM layout came from work other people did first:

- [TaleTN's TG101](https://github.com/TaleTN/TG101), a TG100 engine in C++, and
  the source of nearly every offset here
- [vampirefrog/tg100](https://github.com/vampirefrog/tg100), reverse
  engineering notes, region dumps and the scanned manuals
- [furmilion's tg100_re](https://github.com/furmilion/stuffs/tree/main/scripts/yamaha/tg100_re)
- [kreth608/tg100](https://github.com/kreth608/tg100), sysex dumps
