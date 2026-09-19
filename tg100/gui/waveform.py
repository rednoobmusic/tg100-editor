"""Waveform preview with loop markers, zoom and a playback cursor."""

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets


class WaveformView(QtWidgets.QWidget):
    """Draws a wave and lets you point at it.

    Zoomed out it draws a min and max envelope per pixel column, which is the
    only way 100k samples read as anything other than a solid block. Once there
    are fewer samples than pixels it switches to a polyline and shows the
    individual sample points, so you can see what the 12 bit quantisation is
    actually doing.
    """

    positionClicked = QtCore.Signal(int)
    loopDragged = QtCore.Signal(int)

    BG = QtGui.QColor("#16181d")
    GRID = QtGui.QColor("#262a33")
    AXIS = QtGui.QColor("#3a404e")
    WAVE = QtGui.QColor("#5ac8fa")
    PEAK_FILL = QtGui.QColor(90, 200, 250, 90)
    RMS_FILL = QtGui.QColor(125, 214, 255, 235)
    WAVE_LOOP = QtGui.QColor("#ffd66b")
    LOOP_FILL = QtGui.QColor(255, 214, 107, 28)
    LOOP_LINE = QtGui.QColor("#ffd66b")
    CURSOR = QtGui.QColor("#ff6b6b")
    TEXT = QtGui.QColor("#8b93a5")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMouseTracking(True)

        self._samples = np.zeros(0, dtype=np.int16)
        self._loop = 0
        self._loops = False
        self._view_start = 0
        self._view_len = 0
        self._cursor = None
        self._hover = None
        self._dragging_loop = False

    def set_wave(self, samples, loop=0, loops=False):
        self._samples = np.asarray(samples)
        self._loop = int(loop)
        self._loops = bool(loops)
        self.reset_zoom()

    def clear(self):
        self.set_wave(np.zeros(0, dtype=np.int16))

    def reset_zoom(self):
        self._view_start = 0
        self._view_len = len(self._samples)
        self._cursor = None
        self.update()

    def set_cursor(self, pos):
        self._cursor = pos
        self.update()

    @property
    def view(self):
        return self._view_start, self._view_len

    def zoom_at(self, factor, anchor_frac=0.5):
        n = len(self._samples)
        if n == 0:
            return
        new_len = int(round(self._view_len * factor))
        new_len = max(16, min(n, new_len))
        anchor = self._view_start + self._view_len * anchor_frac
        start = int(round(anchor - new_len * anchor_frac))
        self._view_start = max(0, min(n - new_len, start))
        self._view_len = new_len
        self.update()

    def scroll_by(self, fraction):
        n = len(self._samples)
        if n == 0:
            return
        step = int(self._view_len * fraction)
        self._view_start = max(0, min(n - self._view_len, self._view_start + step))
        self.update()

    def _x_to_sample(self, x):
        if self._view_len == 0 or self.width() == 0:
            return 0
        return int(self._view_start + (x / self.width()) * self._view_len)

    def _sample_to_x(self, pos):
        if self._view_len == 0:
            return -1
        return (pos - self._view_start) / self._view_len * self.width()

    def wheelEvent(self, event):
        if len(self._samples) == 0:
            return
        frac = event.position().x() / max(1, self.width())
        steps = event.angleDelta().y() / 120.0
        if steps:
            self.zoom_at(0.8**steps, frac)
        event.accept()

    def mousePressEvent(self, event):
        if len(self._samples) == 0:
            return
        pos = self._x_to_sample(event.position().x())
        if event.button() == QtCore.Qt.RightButton:
            self._dragging_loop = True
            self.loopDragged.emit(max(0, min(len(self._samples), pos)))
        else:
            self.positionClicked.emit(max(0, min(len(self._samples) - 1, pos)))

    def mouseMoveEvent(self, event):
        self._hover = self._x_to_sample(event.position().x())
        if self._dragging_loop:
            self.loopDragged.emit(max(0, min(len(self._samples), self._hover)))
        self.update()

    def mouseReleaseEvent(self, event):
        self._dragging_loop = False

    def leaveEvent(self, event):
        self._hover = None
        self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (QtCore.Qt.Key_Plus, QtCore.Qt.Key_Equal):
            self.zoom_at(0.5)
        elif key == QtCore.Qt.Key_Minus:
            self.zoom_at(2.0)
        elif key == QtCore.Qt.Key_Left:
            self.scroll_by(-0.25)
        elif key == QtCore.Qt.Key_Right:
            self.scroll_by(0.25)
        elif key == QtCore.Qt.Key_0:
            self.reset_zoom()
        else:
            super().keyPressEvent(event)

    def _envelope(self, width):
        """Peak and RMS per pixel column for the visible slice.

        Peaks alone make every busy sample look like a solid block, so the RMS
        goes in as well. The bright inner band is the average level and the
        pale outer shape is the peaks, which is how a sample's shape actually
        reads at a glance.
        """
        view = self._samples[self._view_start : self._view_start + self._view_len]
        n = len(view)
        if n == 0:
            return None
        cols = max(1, min(width, n))
        edges = np.linspace(0, n, cols + 1).astype(np.int64)
        starts = edges[:-1]
        # reduceat needs strictly increasing indices, so drop empty columns
        keep = np.concatenate([[True], starts[1:] > starts[:-1]])
        starts = starts[keep]

        lo = np.minimum.reduceat(view, starts)
        hi = np.maximum.reduceat(view, starts)

        squares = view.astype(np.float64) ** 2
        sums = np.add.reduceat(squares, starts)
        counts = np.diff(np.append(starts, n)).astype(np.float64)
        rms = np.sqrt(sums / np.maximum(counts, 1.0))

        xs = starts / n * width
        return xs, lo, hi, rms

    @staticmethod
    def _band(xs, upper, lower, mid, scale):
        """A closed path tracing one edge out and the other back."""
        path = QtGui.QPainterPath()
        path.moveTo(float(xs[0]), mid - float(upper[0]) * scale)
        for x, v in zip(xs[1:], upper[1:]):
            path.lineTo(float(x), mid - float(v) * scale)
        for x, v in zip(reversed(xs), reversed(lower)):
            path.lineTo(float(x), mid - float(v) * scale)
        path.closeSubpath()
        return path

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), self.BG)

        mid = h / 2.0
        # Fixed to the full 12 bit range, never to the loudest sample in view.
        # A quiet wave is meant to look quiet, and two waves are meant to be
        # comparable by eye.
        scale = (h / 2.0 - 6) / 2048.0

        p.setPen(QtGui.QPen(self.GRID, 1))
        for frac in (0.25, 0.75):
            p.drawLine(0, int(h * frac), w, int(h * frac))

        if len(self._samples) == 0:
            p.setPen(self.TEXT)
            p.drawText(self.rect(), QtCore.Qt.AlignCenter, "no wave selected")
            return

        if self._loops:
            lx = self._sample_to_x(self._loop)
            ex = self._sample_to_x(len(self._samples))
            if ex > 0 and lx < w:
                rect = QtCore.QRectF(max(0, lx), 0, min(w, ex) - max(0, lx), h)
                p.fillRect(rect, self.LOOP_FILL)

        p.setPen(QtGui.QPen(self.AXIS, 1))
        p.drawLine(0, int(mid), w, int(mid))

        env = self._envelope(w)
        if env is not None:
            xs, lo, hi, rms = env
            view_n = min(self._view_len, len(self._samples) - self._view_start)

            if view_n <= w:
                view = self._samples[
                    self._view_start : self._view_start + self._view_len
                ]
                step = w / max(1, view_n)
                path = QtGui.QPainterPath()
                for i, v in enumerate(view):
                    x = i * step
                    y = mid - float(v) * scale
                    if i == 0:
                        path.moveTo(x, y)
                    else:
                        path.lineTo(x, y)
                p.setPen(QtGui.QPen(self.WAVE, 1.4))
                p.drawPath(path)
                if view_n < w / 4:
                    p.setBrush(self.WAVE)
                    p.setPen(QtCore.Qt.NoPen)
                    for i, v in enumerate(view):
                        p.drawEllipse(
                            QtCore.QPointF(i * step, mid - float(v) * scale), 2.2, 2.2
                        )
            elif len(xs) > 1:
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(self.PEAK_FILL)
                p.drawPath(self._band(xs, hi, lo, mid, scale))
                p.setBrush(self.RMS_FILL)
                p.drawPath(self._band(xs, rms, -rms, mid, scale))
                p.setPen(QtGui.QPen(self.WAVE, 0.9))
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawPath(self._band(xs, hi, lo, mid, scale))

        if self._loops:
            lx = self._sample_to_x(self._loop)
            if 0 <= lx <= w:
                p.setPen(QtGui.QPen(self.LOOP_LINE, 1.2, QtCore.Qt.DashLine))
                p.drawLine(int(lx), 0, int(lx), h)

        if self._cursor is not None:
            cx = self._sample_to_x(self._cursor)
            if 0 <= cx <= w:
                p.setPen(QtGui.QPen(self.CURSOR, 1.2))
                p.drawLine(int(cx), 0, int(cx), h)

        p.setPen(self.TEXT)
        font = p.font()
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1))
        p.setFont(font)
        n = len(self._samples)
        label = f"{self._view_start} .. {self._view_start + self._view_len} of {n}"
        if self._hover is not None and 0 <= self._hover < n:
            label += f"    at {self._hover}: {int(self._samples[self._hover])}"
        p.drawText(6, h - 6, label)
