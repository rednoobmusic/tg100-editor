"""Sample processing, so a wave can be edited rather than only replaced.

Everything here works on decoded 12 bit samples and returns new arrays. None
of it touches a ROM. Trimming matters most, because shortening waves is the
only way to free space in a ROM that ships completely full, and repack turns
that freed space into one usable run.
"""

import numpy as np

from .codec import SAMPLE_MAX, SAMPLE_MIN


def _clip(x):
    return np.clip(np.rint(x), SAMPLE_MIN, SAMPLE_MAX).astype(np.int16)


def trim(samples, start=0, end=None):
    """Keep samples[start:end]."""
    samples = np.asarray(samples)
    end = len(samples) if end is None else end
    if not 0 <= start <= end <= len(samples):
        raise ValueError(f"trim range {start}..{end} is outside 0..{len(samples)}")
    return samples[start:end].copy()


def trim_silence(samples, threshold=8, keep_head=0):
    """Drop the silent tail, and optionally the silent head.

    The threshold counts as silence anything under it in absolute value, which
    at 12 bit is a tiny fraction of full scale. Decayed one shots in this ROM
    often carry hundreds of near zero samples that cost real space.
    """
    samples = np.asarray(samples)
    if samples.size == 0:
        return samples.copy()
    loud = np.flatnonzero(np.abs(samples) > threshold)
    if loud.size == 0:
        return samples[:0].copy()
    first = loud[0] if keep_head == 0 else max(0, loud[0] - keep_head)
    return samples[first : loud[-1] + 1].copy()


def gain(samples, db):
    return _clip(np.asarray(samples).astype(np.float64) * (10.0 ** (db / 20.0)))


def normalize(samples, peak=SAMPLE_MAX):
    samples = np.asarray(samples)
    current = int(np.abs(samples).max()) if samples.size else 0
    if current == 0:
        return samples.copy()
    return _clip(samples.astype(np.float64) * (peak / current))


def fade_in(samples, length):
    samples = np.asarray(samples).astype(np.float64).copy()
    n = min(int(length), len(samples))
    if n > 1:
        samples[:n] *= np.linspace(0.0, 1.0, n)
    return _clip(samples)


def fade_out(samples, length):
    samples = np.asarray(samples).astype(np.float64).copy()
    n = min(int(length), len(samples))
    if n > 1:
        samples[-n:] *= np.linspace(1.0, 0.0, n)
    return _clip(samples)


def resample(samples, ratio):
    """Linear resample. A ratio above 1 makes the wave shorter and higher."""
    samples = np.asarray(samples)
    n = len(samples)
    if n == 0 or ratio == 1.0:
        return samples.copy()
    if ratio <= 0:
        raise ValueError(f"ratio has to be positive, got {ratio}")
    out_n = max(1, int(round(n / ratio)))
    src = np.clip(np.arange(out_n) * ratio, 0, n - 1)
    lo = src.astype(np.int64)
    hi = np.minimum(lo + 1, n - 1)
    frac = src - lo
    a = samples.astype(np.float64)
    return _clip(a[lo] * (1.0 - frac) + a[hi] * frac)


def pitch_shift(samples, semitones):
    """Resample by an interval. This changes the length, as on the hardware."""
    return resample(samples, 2.0 ** (semitones / 12.0))


def nearest_zero_crossing(samples, position, window=256):
    """Snap a loop point to where the wave crosses zero, to stop it clicking."""
    samples = np.asarray(samples)
    n = len(samples)
    if n < 2:
        return position
    position = int(np.clip(position, 0, n - 1))
    lo = max(1, position - window)
    hi = min(n - 1, position + window)
    if hi <= lo:
        return position
    seg = samples[lo:hi].astype(np.int32)
    prev = samples[lo - 1 : hi - 1].astype(np.int32)
    crossings = np.flatnonzero((seg >= 0) != (prev >= 0))
    if crossings.size == 0:
        return position
    return int(lo + crossings[np.argmin(np.abs(crossings + lo - position))])


def suggest_loop(samples, min_length=64, search=None):
    """Find a loop point whose seam matches the end of the wave.

    Compares a window taken from the end against every candidate position and
    picks the one that lines up best, which is the usual way of finding a loop
    in a sustained sample. Returns None when nothing matches well enough, for
    instance on a one shot that decays into silence.
    """
    samples = np.asarray(samples).astype(np.float64)
    n = len(samples)
    if n < min_length * 3:
        return None

    window = min(512, n // 4)
    tail = samples[-window:]

    # A wave that has decayed into silence has nothing to loop. Without this,
    # the search happily matches one silent stretch against another and returns
    # a confident loop point in the middle of nothing.
    peak = float(np.abs(samples).max())
    if peak == 0.0:
        return None
    if float(np.sqrt(np.mean(tail**2))) < peak * 0.02:
        return None
    limit = n - window - min_length
    if limit <= 0:
        return None
    start = 0 if search is None else max(0, min(search, limit))

    best, best_score = None, None
    step = max(1, (limit - start) // 4096)
    for pos in range(start, limit, step):
        seg = samples[pos : pos + window]
        score = float(np.mean((seg - tail) ** 2))
        if best_score is None or score < best_score:
            best, best_score = pos, score

    if best is None:
        return None
    scale = float(np.mean(tail**2)) or 1.0
    # a seam worse than the signal's own energy is not a loop worth having
    if best_score > scale:
        return None
    return nearest_zero_crossing(samples.astype(np.int16), best)


def crossfade_loop(samples, loop, length=128):
    """Blend the approach to the loop point with the tail, hiding the seam."""
    samples = np.asarray(samples).astype(np.float64).copy()
    n = len(samples)
    length = int(min(length, loop, n - loop))
    if length < 2:
        return _clip(samples)
    ramp = np.linspace(0.0, 1.0, length)
    head = samples[loop : loop + length]
    tail = samples[n - length :]
    samples[loop : loop + length] = tail * (1.0 - ramp) + head * ramp
    return _clip(samples)
