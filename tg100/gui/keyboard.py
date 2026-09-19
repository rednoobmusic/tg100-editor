"""A clickable keyboard, for auditioning a sample at pitch rather than at one note.

Hearing a wave at its root note tells you very little. What you want to know is
how far it stretches before it falls apart, which means playing it up and down
the range the way the sample set maps it.
"""

from PySide6 import QtCore, QtGui, QtWidgets

WHITE = {0, 2, 4, 5, 7, 9, 11}
NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


class PianoKeyboard(QtWidgets.QWidget):
    """Click a key to play. Right click drags across keys to glissando."""

    notePressed = QtCore.Signal(int)

    KEY_W = QtGui.QColor("#d9dee6")
    KEY_W_LIT = QtGui.QColor("#5ac8fa")
    KEY_W_EDGE = QtGui.QColor("#0f1115")
    KEY_B = QtGui.QColor("#1a1d23")
    KEY_B_LIT = QtGui.QColor("#2f7fa8")
    IN_RANGE = QtGui.QColor("#2b3a44")
    ROOT = QtGui.QColor("#ffd66b")
    TEXT = QtGui.QColor("#6b7280")

    def __init__(self, low=36, high=96, parent=None):
        super().__init__(parent)
        self.low, self.high = low, high
        self.setMinimumHeight(64)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self._lit = set()
        self._range = None
        self._root = None
        self.setMouseTracking(True)

    def set_range(self, low, high):
        """Shade the keys a sample set actually covers."""
        self._range = (low, high) if low is not None else None
        self.update()

    def set_root(self, note):
        """Mark the note the recording was made at."""
        self._root = note
        self.update()

    def light(self, note, on=True):
        if on:
            self._lit.add(note)
        else:
            self._lit.discard(note)
        self.update()

    def clear_lights(self):
        self._lit.clear()
        self.update()

    def _white_notes(self):
        return [n for n in range(self.low, self.high + 1) if n % 12 in WHITE]

    def _white_width(self):
        count = len(self._white_notes()) or 1
        return self.width() / count

    def _note_at(self, pos):
        ww = self._white_width()
        whites = self._white_notes()
        # black keys sit on top, so try them first
        for i, n in enumerate(whites):
            if n % 12 in (4, 11):  # no black key above E or B
                continue
            x = (i + 1) * ww - ww * 0.3
            if x <= pos.x() <= x + ww * 0.6 and pos.y() <= self.height() * 0.62:
                candidate = n + 1
                if self.low <= candidate <= self.high:
                    return candidate
        index = int(pos.x() // ww) if ww else 0
        if 0 <= index < len(whites):
            return whites[index]
        return None

    def mousePressEvent(self, event):
        note = self._note_at(event.position())
        if note is not None:
            self.notePressed.emit(note)

    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.RightButton:
            note = self._note_at(event.position())
            if note is not None and note not in self._lit:
                self.notePressed.emit(note)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, False)
        p.fillRect(self.rect(), QtGui.QColor("#13151a"))
        h = self.height()
        ww = self._white_width()
        whites = self._white_notes()

        for i, n in enumerate(whites):
            x = i * ww
            rect = QtCore.QRectF(x, 0, ww - 1, h)
            if n in self._lit:
                colour = self.KEY_W_LIT
            elif self._range and self._range[0] <= n <= self._range[1]:
                colour = self.IN_RANGE
            else:
                colour = self.KEY_W
            p.fillRect(rect, colour)
            p.setPen(self.KEY_W_EDGE)
            p.drawRect(rect)
            if n % 12 == 0:
                p.setPen(self.TEXT)
                p.drawText(
                    QtCore.QRectF(x, h - 15, ww, 14),
                    QtCore.Qt.AlignCenter,
                    f"C{n // 12 - 2}",
                )
            if self._root == n:
                p.fillRect(QtCore.QRectF(x + 2, h - 5, ww - 5, 3), self.ROOT)

        bh = h * 0.62
        for i, n in enumerate(whites):
            if n % 12 in (4, 11):
                continue
            black = n + 1
            if not self.low <= black <= self.high:
                continue
            x = (i + 1) * ww - ww * 0.3
            rect = QtCore.QRectF(x, 0, ww * 0.6, bh)
            p.fillRect(rect, self.KEY_B_LIT if black in self._lit else self.KEY_B)
            p.setPen(self.KEY_W_EDGE)
            p.drawRect(rect)
            if self._root == black:
                p.fillRect(
                    QtCore.QRectF(x + 1, bh - 5, ww * 0.6 - 2, 3), self.ROOT
                )


def note_name(n):
    return f"{NAMES[n % 12]}{n // 12 - 2}"
