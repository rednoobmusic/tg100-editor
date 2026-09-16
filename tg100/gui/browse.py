"""The lookup table viewer.

These curves are shared by every voice, so there is no per voice context to
show alongside them. Editing them is possible through tg100.tables but is not
wired up here yet, because getting one wrong detunes the whole module.
"""

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from .. import tables as tbl

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def note_name(n):
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"


def _table(columns):
    t = QtWidgets.QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels(columns)
    t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
    t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def _fill(table, rows):
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            table.setItem(r, c, QtWidgets.QTableWidgetItem(str(text)))
    table.resizeColumnsToContents()


class CurveView(QtWidgets.QWidget):
    """Plots a lookup table so its shape is obvious at a glance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = []
        self.setMinimumHeight(220)

    def set_values(self, values):
        self.values = list(values)
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtGui.QColor("#16181d"))
        if not self.values:
            return
        w, h = self.width(), self.height()
        pad = 8
        arr = np.asarray(self.values, dtype=float)
        top = max(1.0, float(arr.max()))
        p.setPen(QtGui.QPen(QtGui.QColor("#262a33"), 1))
        for f in (0.25, 0.5, 0.75):
            p.drawLine(0, int(h * f), w, int(h * f))
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.setPen(QtGui.QPen(QtGui.QColor("#5ac8fa"), 1.5))
        path = QtGui.QPainterPath()
        n = len(arr)
        for i, v in enumerate(arr):
            x = pad + (w - 2 * pad) * (i / max(1, n - 1))
            y = h - pad - (h - 2 * pad) * (v / top)
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        p.drawPath(path)
        p.setPen(QtGui.QColor("#8b93a5"))
        p.drawText(6, 14, f"{n} entries, peak {arr.max():.0f}")


class TablesTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.prog = None

        self.picker = QtWidgets.QComboBox()
        for name in sorted(tbl.SPECS):
            self.picker.addItem(f"{name}  ({tbl.SPECS[name][3]})", name)
        self.picker.currentIndexChanged.connect(self._show)

        self.curve = CurveView()
        self.values = QtWidgets.QPlainTextEdit()
        self.values.setReadOnly(True)
        self.values.setFont(
            QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        )

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Table"))
        top.addWidget(self.picker, 1)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addLayout(top)
        lay.addWidget(self.curve, 1)
        lay.addWidget(self.values, 1)

    def set_rom(self, prog):
        self.prog = prog
        self._show()

    def _show(self):
        if self.prog is None:
            self.curve.set_values([])
            self.values.clear()
            return
        name = self.picker.currentData()
        values = self.prog.table(name)
        self.curve.set_values(values)
        lines = []
        for i in range(0, len(values), 16):
            chunk = " ".join(f"{v:5d}" for v in values[i : i + 16])
            lines.append(f"{i:5d}  {chunk}")
        self.values.setPlainText("\n".join(lines))
