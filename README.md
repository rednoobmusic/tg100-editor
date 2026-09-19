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

**Waves.** All 512 wave table slots, 489 of which are used. The list sorts on
any column and filters as you type, which matters because Yamaha's wave order
follows the ROM layout rather than anything musical. Sorting by name pulls a
multisample back together, so Alto Sax reads 1/13 through 13/13 even though
those thirteen recordings sit at scattered indices. Typing drum, instrument,
unused or named narrows the list to those.

Since the sample ROM holds no text, every name is a guess. If you listen to one
and recognise it, type what you hear into the Call it box and that name sticks.
It is written to a small JSON file beside the ROM, so the ROM itself stays
exactly what the hardware expects, and the guess stays visible next to your
name in case you want it back.

Waveform display
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

**Sysex.** Reads and writes the TG100's system exclusive dumps, so an edit can
be heard on real hardware without burning anything. Pick a voice, send it to
one of the module's 64 internal slots over MIDI, and listen. The format was
worked out from 24 captures off one owner's module rather than assumed from
other Yamaha gear of the period, and the whole corpus round trips byte for
byte. There is one message shape, not the two the era usually uses:

```
F0 43 1n 27 <a2> <a1> <a0> <data ...> <checksum> F7
```

A 21 bit address carried as three seven bit bytes, and a two's complement
checksum over the address and the data. All 4017 messages in the corpus satisfy
it, as do the five Yamaha wrote into the ROM's own demo song.

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

## Talking to the hardware

`tg100.sysex` reads and writes the TG100's own MIDI system exclusive dumps, so
a voice edited here can be sent to a real module and heard without reflashing
anything. The format was worked out from 24 dumps taken off one owner's TG100
and checked against the firmware, and every one of those files comes back out
of this code byte for byte.

There is only one message. Bulk dumps and single parameter changes are the same
thing at different lengths:

```
F0 43 1n 27 <a2> <a1> <a0> <data ...> <checksum> F7
```

`n` is the device number, `27` is the model, and the three address bytes carry
seven bits each, high first, so the address is `a2 << 14 | a1 << 7 | a0`. The
checksum is `(-sum(address + data)) & 0x7F`. The demo song in the program ROM
proves the one byte case: at `0x19643` it changes the reverb type mid song with
`F0 43 10 27 30 00 0A 00 46 F7`.

Two address regions appear, and each message carries exactly one record:

| Address | Size | What it is |
| --- | --- | --- |
| `0x0C0000` | 10 | system: master tune, transpose, device number, master volume |
| `0x0C000A` | 6 | reverb type, time and output level, then three unused bytes |
| `0x0C0010` | 384 | 16 parts of 24 bytes |
| `0x0C0190` | 6144 | 64 voices of 96 bytes, the voice RAM |
| `0x0C1990` | 246 | 82 drum setups of 3 bytes, notes 27 to 108 |
| `0x090000` | 1024 | the four program change maps, the RAM copy of `0x10000` |

The voice record is the same 96 bytes as in the program ROM, so
`tg100.voices.Voice` reads both. The 64 voices at `0x0C0190` are the internal
voice RAM, which MIDI bank numbers 64 to 111 select, and they start out as a
copy of the first 64 ROM voices. That is the route from this editor to a real
module: write a voice into a RAM slot, then select bank 64 and its program
number on a part.

Part slot 0 is the drum part, which the front panel calls part 10. Slots 1 to 9
are parts 1 to 9 and slots 10 to 15 are parts 11 to 16, so the slot number and
the part number are not the same.

The hardware sends two dump styles and this writes both. `"all"` is 168
messages and 9323 bytes, ending with the system block because that block holds
the device number and changing it halfway through would orphan the rest.
`"setup"` is 164 messages and 8266 bytes and leaves the program change maps
out.

```python
from tg100.sysex import Dump

dump = Dump.load("savestate.syx")
print(dump.reverb.type_name, dump.part(1).program, dump.voice(0).name)
dump.voice(0).name = "dingus"
dump.save("edited.syx")
```

## Credits

The ROM layout came from work other people did first:

- [TaleTN's TG101](https://github.com/TaleTN/TG101), a TG100 engine in C++, and
  the source of nearly every offset here
- [vampirefrog/tg100](https://github.com/vampirefrog/tg100), reverse
  engineering notes, region dumps and the scanned manuals
- [furmilion's tg100_re](https://github.com/furmilion/stuffs/tree/main/scripts/yamaha/tg100_re)
- [kreth608/tg100](https://github.com/kreth608/tg100), sysex dumps
