"""Sample playback.

Kept deliberately small. This plays one wave at a time so you can hear what you
are editing, it is not a synth voice. Pitch is a plain resample of the decoded
12 bit data, and the loop is rendered ahead of time rather than streamed.
"""

import numpy as np
from PySide6 import QtCore

from ..waves import NATIVE_SAMPLE_RATE

try:
    from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

    AVAILABLE = True
except ImportError:  # pragma: no cover, depends on the Qt build
    AVAILABLE = False


def resample(samples, ratio):
    """Linear resample. Good enough for auditioning, not for rendering."""
    n = len(samples)
    if n == 0 or ratio == 1.0:
        return np.asarray(samples, dtype=np.float32)
    out_n = max(1, int(round(n / ratio)))
    src = np.arange(out_n, dtype=np.float64) * ratio
    src = np.clip(src, 0, n - 1)
    lo = src.astype(np.int64)
    hi = np.minimum(lo + 1, n - 1)
    frac = (src - lo).astype(np.float32)
    a = np.asarray(samples, dtype=np.float32)
    return a[lo] * (1.0 - frac) + a[hi] * frac


def render(samples, loop=0, loops=False, semitones=0.0, seconds=2.0, fade=0.01):
    """Build a playable buffer from a wave, repeating the loop to fill time."""
    a = np.asarray(samples, dtype=np.float32)
    if a.size == 0:
        return np.zeros(0, dtype=np.float32)

    ratio = 2.0 ** (semitones / 12.0)
    want = int(NATIVE_SAMPLE_RATE * seconds)

    if loops and 0 <= loop < len(a):
        head, body = a[:loop], a[loop:]
        if body.size:
            repeats = max(1, int(np.ceil((want - head.size) / body.size)))
            a = np.concatenate([head, np.tile(body, repeats)])
    a = a[:want]

    out = resample(a, ratio) / 2048.0

    # a short fade out stops the buffer ending on a click
    tail = min(len(out), int(NATIVE_SAMPLE_RATE * fade))
    if tail > 1:
        out[-tail:] *= np.linspace(1.0, 0.0, tail, dtype=np.float32)
    return np.clip(out, -1.0, 1.0)


class Player(QtCore.QObject):
    """Plays float buffers through the default output device."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sink = None
        self._buffer = None
        self._device = None

    @property
    def available(self):
        return AVAILABLE

    def play(self, samples, sample_rate=NATIVE_SAMPLE_RATE, volume=0.8):
        if not AVAILABLE or len(samples) == 0:
            return False
        self.stop()

        pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()

        fmt = QAudioFormat()
        fmt.setSampleRate(int(round(sample_rate)))
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.Int16)

        device = QMediaDevices.defaultAudioOutput()
        if device is None or device.isNull():
            return False

        self._sink = QAudioSink(device, fmt, self)
        self._sink.setVolume(volume)
        self._buffer = QtCore.QBuffer(self)
        self._buffer.setData(pcm)
        self._buffer.open(QtCore.QIODevice.ReadOnly)
        self._sink.start(self._buffer)
        return True

    def stop(self):
        if self._sink is not None:
            self._sink.stop()
            self._sink = None
        if self._buffer is not None:
            self._buffer.close()
            self._buffer = None
