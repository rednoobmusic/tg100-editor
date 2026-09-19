"""Editable curves, because a curve is easier to drag than to type.

An envelope described by nine numbers is unreadable until you draw it, and
once it is drawn the obvious thing to do is grab it. These widgets own the
editing: drag a handle and the ROM byte changes underneath. The numbers stay
visible beside them for when you want an exact value, but they are no longer
the only way in.
"""

from PySide6 import QtCore, QtGui, QtWidgets

BG = QtGui.QColor("#13151a")
GRID = QtGui.QColor("#242833")
GUIDE = QtGui.QColor("#39404f")
LINE = QtGui.QColor("#5ac8fa")
FILL = QtGui.QColor(90, 200, 250, 46)
HANDLE = QtGui.QColor("#9fe0ff")
HANDLE_HOT = QtGui.QColor("#ffd66b")
MARK = QtGui.QColor("#ffd66b")
TEXT = QtGui.QColor("#8b93a5")

GRAB = 11.0


class _Curve(QtWidgets.QWidget):
    """Shared painting and hit testing for the draggable curves."""

    edited = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(132)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self.setMouseTracking(True)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._hot = None
        self._drag = None

    @property
    def _pad(self):
        return 12.0, 10.0, 14.0  # left/right, top, bottom

    def _handles(self):
        """[(x, y)] in widget coordinates, one per draggable point."""
        return []

    def _move_handle(self, index, pos):
        """Apply a drag. Subclasses write the value and emit edited."""

    def _nearest(self, pos):
        best, best_d = None, GRAB
        for i, (hx, hy) in enumerate(self._handles()):
            d = ((pos.x() - hx) ** 2 + (pos.y() - hy) ** 2) ** 0.5
            if d < best_d:
                best, best_d = i, d
        return best

    def mousePressEvent(self, event):
        self._drag = self._nearest(event.position())
        if self._drag is not None:
            self._move_handle(self._drag, event.position())

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            self._move_handle(self._drag, event.position())
            return
        hot = self._nearest(event.position())
        if hot != self._hot:
            self._hot = hot
            self.update()

    def mouseReleaseEvent(self, event):
        self._drag = None

    def leaveEvent(self, event):
        self._hot = None
        self.update()

    def _frame(self, p):
        p.fillRect(self.rect(), BG)
        p.setPen(QtGui.QPen(GRID, 1))
        for f in (0.25, 0.5, 0.75):
            y = self.height() * f
            p.drawLine(0, int(y), self.width(), int(y))

    def _draw_handles(self, p, points):
        for i, (x, y) in enumerate(points):
            hot = i == self._hot or i == self._drag
            p.setBrush(HANDLE_HOT if hot else HANDLE)
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(QtCore.QPointF(x, y), 4.2 if hot else 3.2, 4.2 if hot else 3.2)

    def _caption(self, p, text):
        p.setPen(TEXT)
        font = p.font()
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1.5))
        p.setFont(font)
        p.drawText(6, self.height() - 4, text)


class PitchEGEditor(_Curve):
    """The pitch envelope, dragged rather than typed.

    Up and down is pitch, where the dashed line is the note you played. Left
    and right is time: drag a point sideways and the rate of the segment
    leading into it changes, faster to the left and slower to the right.
    """

    levelChanged = QtCore.Signal(int, int)
    rateChanged = QtCore.Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.levels = [64] * 5
        self.rates = [0] * 4
        self.octaves = ""

    def set_envelope(self, levels, rates, octaves=""):
        self.levels, self.rates, self.octaves = list(levels), list(rates), octaves
        self.update()

    def _geometry(self):
        left, top, bottom = self._pad
        w, h = self.width(), self.height()
        y_top, y_bot = top, h - bottom - 10
        widths = [1.0 + (63 - r) / 63.0 * 3.0 for r in self.rates]
        total = sum(widths) or 1.0
        usable = w - 2 * left
        xs, x = [left], left
        for width in widths:
            x += usable * (width / total)
            xs.append(x)
        return xs, y_top, y_bot, left, usable

    def _y_for(self, level, y_top, y_bot):
        return y_bot - (level / 127.0) * (y_bot - y_top)

    def _handles(self):
        xs, y_top, y_bot, _, _ = self._geometry()
        return [(x, self._y_for(lv, y_top, y_bot)) for x, lv in zip(xs, self.levels)]

    def _move_handle(self, index, pos):
        xs, y_top, y_bot, left, usable = self._geometry()

        span = max(1.0, y_bot - y_top)
        level = int(round((y_bot - pos.y()) / span * 127.0))
        level = max(0, min(127, level))
        if level != self.levels[index]:
            self.levels[index] = level
            self.levelChanged.emit(index, level)

        # dragging sideways retimes the segment arriving at this point
        if index > 0:
            prev_x = xs[index - 1]
            want = max(2.0, pos.x() - prev_x)
            share = want / max(1.0, usable)
            # width 1 is the fastest rate, width 4 the slowest
            width = max(1.0, min(4.0, share * 4.0 * len(self.rates)))
            rate = int(round(63 - (width - 1.0) / 3.0 * 63))
            rate = max(0, min(63, rate))
            if rate != self.rates[index - 1]:
                self.rates[index - 1] = rate
                self.rateChanged.emit(index - 1, rate)

        self.update()
        self.edited.emit()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self._frame(p)
        xs, y_top, y_bot, _, _ = self._geometry()
        ys = [self._y_for(lv, y_top, y_bot) for lv in self.levels]
        centre = self._y_for(64, y_top, y_bot)

        path = QtGui.QPainterPath()
        path.moveTo(xs[0], ys[0])
        for i in range(1, len(xs)):
            path.lineTo(xs[i], ys[i])

        under = QtGui.QPainterPath(path)
        under.lineTo(xs[-1], centre)
        under.lineTo(xs[0], centre)
        under.closeSubpath()
        p.fillPath(under, FILL)

        p.setPen(QtGui.QPen(GUIDE, 1, QtCore.Qt.DashLine))
        p.drawLine(0, int(centre), self.width(), int(centre))
        p.setPen(QtGui.QPen(MARK, 1, QtCore.Qt.DashLine))
        p.drawLine(int(xs[-2]), 0, int(xs[-2]), self.height())

        p.setPen(QtGui.QPen(LINE, 1.8))
        p.drawPath(path)
        self._draw_handles(p, list(zip(xs, ys)))

        flat = all(v == self.levels[0] for v in self.levels)
        state = "flat, no pitch movement" if flat else f"range {self.octaves}"
        self._caption(p, f"drag up for pitch, sideways for time. {state}")


class LevelScaleEditor(_Curve):
    """Loudness across the keyboard, with four draggable breakpoints.

    Sideways moves the breakpoint to a different key, up and down changes the
    level there. 128 is neutral, so the dashed line is no change at all.
    """

    NEUTRAL = 128
    pointChanged = QtCore.Signal(int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.breakpoints = [0, 42, 85, 127]
        self.offsets = [128] * 4

    def set_points(self, breakpoints, offsets):
        self.breakpoints, self.offsets = list(breakpoints), list(offsets)
        self.update()

    def _geometry(self):
        left, top, bottom = self._pad
        return left, self.width() - left, top, self.height() - bottom - 10

    def _x_for(self, note):
        x0, x1, _, _ = self._geometry()
        return x0 + (note / 127.0) * (x1 - x0)

    def _y_for(self, value):
        _, _, y0, y1 = self._geometry()
        return y1 - (value / 255.0) * (y1 - y0)

    def _handles(self):
        return [
            (self._x_for(n), self._y_for(v))
            for n, v in zip(self.breakpoints, self.offsets)
        ]

    def _move_handle(self, index, pos):
        x0, x1, y0, y1 = self._geometry()
        note = int(round((pos.x() - x0) / max(1.0, x1 - x0) * 127.0))
        value = int(round((y1 - pos.y()) / max(1.0, y1 - y0) * 255.0))
        note = max(0, min(127, note))
        value = max(0, min(255, value))
        if note != self.breakpoints[index] or value != self.offsets[index]:
            self.breakpoints[index] = note
            self.offsets[index] = value
            self.pointChanged.emit(index, note, value)
            self.update()
            self.edited.emit()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self._frame(p)
        points = sorted(zip(self.breakpoints, self.offsets))
        neutral = self._y_for(self.NEUTRAL)

        path = QtGui.QPainterPath()
        path.moveTo(self._x_for(0), self._y_for(points[0][1]))
        for note, value in points:
            path.lineTo(self._x_for(note), self._y_for(value))
        path.lineTo(self._x_for(127), self._y_for(points[-1][1]))

        under = QtGui.QPainterPath(path)
        under.lineTo(self._x_for(127), neutral)
        under.lineTo(self._x_for(0), neutral)
        under.closeSubpath()
        p.fillPath(under, FILL)

        p.setPen(QtGui.QPen(GUIDE, 1, QtCore.Qt.DashLine))
        p.drawLine(0, int(neutral), self.width(), int(neutral))
        p.setPen(QtGui.QPen(GRID, 1))
        _, _, _, y1 = self._geometry()
        for note in range(0, 128, 12):
            x = int(self._x_for(note))
            p.drawLine(x, int(y1), x, int(y1) + 3)

        p.setPen(QtGui.QPen(LINE, 1.8))
        p.drawPath(path)
        self._draw_handles(p, self._handles())

        flat = all(v == self.offsets[0] for v in self.offsets)
        state = "flat across the keyboard" if flat else "shaped"
        self._caption(p, f"drag a breakpoint. 128 is neutral, ticks are octaves. {state}")


class TableEditor(_Curve):
    """A whole lookup table, drawn on rather than typed.

    Velocity curves and the like are 128 or more values. Nobody edits that in a
    spin box, so dragging paints the curve and the values follow.
    """

    valuesChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(190)
        self.values = []
        self.top = 255
        self.readonly = True
        self._last = None

    def set_values(self, values, top=None, readonly=True):
        self.values = list(values)
        self.top = top or max(1, max(self.values) if self.values else 1)
        self.readonly = readonly
        self.setCursor(
            QtCore.Qt.ArrowCursor if readonly else QtCore.Qt.CrossCursor
        )
        self.update()

    def _geometry(self):
        left, top, bottom = self._pad
        return left, self.width() - left, top, self.height() - bottom - 10

    def _index_at(self, x):
        x0, x1, _, _ = self._geometry()
        n = len(self.values)
        if n < 2:
            return 0
        frac = (x - x0) / max(1.0, x1 - x0)
        return max(0, min(n - 1, int(round(frac * (n - 1)))))

    def _value_at(self, y):
        _, _, y0, y1 = self._geometry()
        frac = (y1 - y) / max(1.0, y1 - y0)
        return max(0, min(self.top, int(round(frac * self.top))))

    def mousePressEvent(self, event):
        if self.readonly:
            return
        self._last = None
        self._paint_at(event.position())

    def mouseMoveEvent(self, event):
        if self.readonly or not (event.buttons() & QtCore.Qt.LeftButton):
            return
        self._paint_at(event.position())

    def mouseReleaseEvent(self, event):
        self._last = None

    def _paint_at(self, pos):
        i = self._index_at(pos.x())
        v = self._value_at(pos.y())
        if self._last is not None:
            # join up to the previous point so a quick drag leaves no gaps
            last_i, last_v = self._last
            lo, hi = (last_i, i) if last_i <= i else (i, last_i)
            for k in range(lo, hi + 1):
                t = 0.0 if hi == lo else (k - lo) / (hi - lo)
                a, b = (last_v, v) if last_i <= i else (v, last_v)
                self.values[k] = int(round(a + (b - a) * t))
        else:
            self.values[i] = v
        self._last = (i, v)
        self.update()
        self.valuesChanged.emit()
        self.edited.emit()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        self._frame(p)
        if not self.values:
            self._caption(p, "no table selected")
            return
        x0, x1, y0, y1 = self._geometry()
        n = len(self.values)

        path = QtGui.QPainterPath()
        for i, v in enumerate(self.values):
            x = x0 + (i / max(1, n - 1)) * (x1 - x0)
            y = y1 - (v / max(1, self.top)) * (y1 - y0)
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)

        under = QtGui.QPainterPath(path)
        under.lineTo(x1, y1)
        under.lineTo(x0, y1)
        under.closeSubpath()
        p.fillPath(under, FILL)
        p.setPen(QtGui.QPen(LINE, 1.6))
        p.drawPath(path)

        how = "read only" if self.readonly else "drag to redraw"
        self._caption(p, f"{n} entries, peak {max(self.values)}. {how}.")
