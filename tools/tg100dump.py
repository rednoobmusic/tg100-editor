#!/usr/bin/env python3
"""Dump ROM contents to the terminal, for when a GUI is more than you need.

    python3 tools/tg100dump.py tg100prog.bin tg100smpl.bin voices
    python3 tools/tg100dump.py tg100prog.bin tg100smpl.bin waves --limit 20
    python3 tools/tg100dump.py tg100prog.bin tg100smpl.bin export 494 out.wav
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tg100 import ProgramRom, SampleRom, codec, naming  # noqa: E402
from tg100.waves import NATIVE_SAMPLE_RATE  # noqa: E402


def cmd_voices(prog, smpl, names, args):
    for v in prog.voices():
        waves = names.wave_no(v.element(0).wave_no)
        if v.mode:
            waves += " + " + names.wave_no(v.element(1).wave_no)
        print(f"{v.index:3d}  {v.name:8s}  {v.mode_name:6s}  {waves}")


def cmd_waves(prog, smpl, names, args):
    shown = 0
    for w in smpl.used_waves():
        loop = f"loop {w.loop}" if w.loops else "one shot"
        secs = w.length / NATIVE_SAMPLE_RATE
        print(
            f"{w.index:3d}  0x{w.start:06X}  {w.length:6d} samples  "
            f"{secs:6.3f}s  {loop:12s}  {names.wave(w.index)}"
        )
        shown += 1
        if args.limit and shown >= args.limit:
            break


def cmd_drums(prog, smpl, names, args):
    for kit in prog.drum_kits():
        print(f"\n{kit.index}  {kit.name}")
        for note in kit.mapped_notes():
            ds = prog.drum_sound(kit.sound_index(note))
            print(
                f"   {note:3d} {naming.note_name(note):5s} "
                f"{naming.percussion_name(note):20s} wave {ds.wave_index:3d}  "
                f"{naming.semitones(ds.pitch_coarse):14s} {naming.pan(ds.pan)}"
            )


def cmd_banks(prog, smpl, names, args):
    for i in range(-1, 5):
        bank = prog.bank(i)
        print(f"\n{bank.name}")
        for p in range(128):
            idx = bank.voice_index(p)
            print(f"   {p:3d}  {idx:3d}  {names.voice(idx)}")


def cmd_space(prog, smpl, names, args):
    used = smpl.used_waves()
    total = sum(w.byte_length for w in used)
    distinct = sum(b - a for a, b in smpl.used_regions()) - 0x1800
    print(f"headers in use          {len(used)} of 512")
    print(f"sum of header lengths   {total} bytes")
    print(f"distinct sample bytes   {distinct} bytes")
    print(f"saved by sharing data   {total - distinct} bytes")
    print(f"free                    {smpl.free_bytes()} bytes "
          f"in {len(smpl.free_regions())} gaps")
    big = sorted(((b - a, a) for a, b in smpl.free_regions()), reverse=True)[:5]
    for size, start in big:
        if size > 1:
            print(f"   gap at 0x{start:06X}  {size} bytes")


def cmd_export(prog, smpl, names, args):
    w = smpl.wave(args.index)
    if w.is_empty:
        raise SystemExit(f"wave {args.index} is an unused slot")
    codec.write_wav(args.out, w.samples(), NATIVE_SAMPLE_RATE)
    print(f"wrote {args.out}: {w.length} samples, {names.wave(w.index)}")


COMMANDS = {
    "voices": cmd_voices,
    "waves": cmd_waves,
    "drums": cmd_drums,
    "banks": cmd_banks,
    "space": cmd_space,
    "export": cmd_export,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prog_rom", help="tg100prog.bin")
    ap.add_argument("smpl_rom", help="tg100smpl.bin")
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("index", nargs="?", type=int, help="wave index, for export")
    ap.add_argument("out", nargs="?", help="output path, for export")
    ap.add_argument("--limit", type=int, default=0, help="stop after N rows")
    args = ap.parse_args()

    prog = ProgramRom.load(args.prog_rom)
    smpl = SampleRom.load(args.smpl_rom)
    for rom, label in ((prog, "program"), (smpl, "sample")):
        if not rom.is_known_dump:
            print(f"warning: {label} ROM is not the dump this was checked "
                  f"against, offsets may be wrong", file=sys.stderr)

    names = naming.Names(prog)
    if args.command == "export" and (args.index is None or not args.out):
        raise SystemExit("export needs a wave index and an output path")
    COMMANDS[args.command](prog, smpl, names, args)


if __name__ == "__main__":
    main()
