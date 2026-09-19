"""Rebuild the sample ROM's layout so freed space becomes usable.

The factory ROM is packed solid, 144 free bytes in 142 gaps with the largest
being 3. That is why the editor can only ever swap a wave for one the same size
or smaller. Nothing is wasted, so there is nothing to reclaim by tidying.

Space only appears when you shorten something, and then it appears in the wrong
place: a hole in the middle of the ROM that no other wave happens to fit. This
module moves every wave down to close those holes, so the free space ends up in
one run at the top where a longer sample can actually use it.

The tricky part is that waves share audio. 489 headers point at 324 regions,
and 38 of those overlaps are partial rather than exact, so a wave can start
part way into another one. Moving waves individually would break that. Instead
the data is grouped into blocks of overlapping waves, and a block moves as a
unit with every wave inside keeping its offset. Aliasing survives exactly as it
was.
"""

from . import layout


class Block:
    """A run of sample data that one or more waves point into."""

    __slots__ = ("start", "end", "waves")

    def __init__(self, start, end, waves):
        self.start = start
        self.end = end
        self.waves = waves

    @property
    def size(self):
        return self.end - self.start

    def __repr__(self):
        return f"<Block 0x{self.start:06X}+{self.size} waves={self.waves}>"


class RepackResult:
    __slots__ = ("blocks", "moved", "freed_before", "freed_after", "largest_run")

    def __init__(self, blocks, moved, freed_before, freed_after, largest_run):
        self.blocks = blocks
        self.moved = moved
        self.freed_before = freed_before
        self.freed_after = freed_after
        self.largest_run = largest_run

    @property
    def gained(self):
        return self.largest_run - self.freed_before

    def __str__(self):
        return (
            f"{self.blocks} blocks, {self.moved} waves moved, "
            f"largest free run went from {self.freed_before} bytes to "
            f"{self.largest_run}"
        )


def blocks(smpl):
    """Group wave data into runs that overlap, in address order."""
    items = sorted(
        (w.start, w.end_address, w.index)
        for w in smpl.used_waves()
        if w.length
    )
    out = []
    for start, end, index in items:
        if out and start <= out[-1].end:
            out[-1].end = max(out[-1].end, end)
            out[-1].waves.append(index)
        else:
            out.append(Block(start, end, [index]))
    return out


def used_bytes(smpl):
    return sum(b.size for b in blocks(smpl))


def free_after_repack(smpl):
    """How much contiguous space a repack would leave at the top."""
    return smpl.size - layout.SAMPLE_DATA_START - used_bytes(smpl)


def largest_free_run(smpl):
    regions = smpl.free_regions()
    return max((b - a for a, b in regions), default=0)


def plan(smpl):
    """What a repack would do, without doing it."""
    bl = blocks(smpl)
    return RepackResult(
        blocks=len(bl),
        moved=sum(len(b.waves) for b in bl),
        freed_before=largest_free_run(smpl),
        freed_after=free_after_repack(smpl),
        largest_run=free_after_repack(smpl),
    )


def repack(smpl):
    """Slide every block down to close the gaps. Returns a RepackResult.

    Sample data is untouched, only its address changes, so this cannot alter
    how anything sounds. Run the validator afterwards anyway.
    """
    before_largest = largest_free_run(smpl)
    bl = blocks(smpl)

    payload = bytearray()
    moves = []
    cursor = layout.SAMPLE_DATA_START
    for b in bl:
        # copy out before writing anything back, so overlapping moves are safe
        payload += bytes(smpl.data[b.start : b.end])
        for index in b.waves:
            w = smpl.wave(index)
            moves.append((index, cursor + (w.start - b.start)))
        cursor += b.size

    if cursor > smpl.size:
        from .rom import RomError

        raise RomError(
            f"the wave data needs {cursor - layout.SAMPLE_DATA_START} bytes "
            f"but the ROM only has {smpl.size - layout.SAMPLE_DATA_START}"
        )

    end = layout.SAMPLE_DATA_START + len(payload)
    smpl.data[layout.SAMPLE_DATA_START : end] = payload
    smpl.data[end:] = bytes(smpl.size - end)

    for index, new_start in moves:
        smpl.wave(index).start = new_start

    return RepackResult(
        blocks=len(bl),
        moved=len(moves),
        freed_before=before_largest,
        freed_after=smpl.size - end,
        largest_run=smpl.size - end,
    )


def budget(smpl):
    """A readable space report for the interface."""
    bl = blocks(smpl)
    used = sum(b.size for b in bl)
    total = smpl.size - layout.SAMPLE_DATA_START
    return {
        "total": total,
        "used": used,
        "free_now": smpl.free_bytes(),
        "largest_run_now": largest_free_run(smpl),
        "free_after_repack": total - used,
        "blocks": len(bl),
        "waves": sum(len(b.waves) for b in bl),
    }
