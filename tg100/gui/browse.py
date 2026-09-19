"""The lookup table editor.

These curves are shared by every voice, so a change here is felt everywhere.
The velocity curves are the useful ones to draw on, because they decide how
hard you have to hit a key to get a given level. The pitch table is the one to
leave alone, since redrawing it detunes the entire module, so it opens read
only and has to be unlocked deliberately.
"""

from PySide6 import QtCore, QtGui, QtWidgets

from .. import tables as tbl
from .curves import TableEditor

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


class TablesTab(QtWidgets.QWidget):
    romChanged = QtCore.Signal()

    # Redrawing this one detunes everything, so it stays locked by default.
    DANGEROUS = {"pitch"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prog = None
        self._name = None

        self.picker = QtWidgets.QComboBox()
        for name in sorted(tbl.SPECS):
            self.picker.addItem(f"{name}  ({tbl.SPECS[name][3]})", name)
        self.picker.currentIndexChanged.connect(self._show)

        self.curve_no = QtWidgets.QSpinBox()
        self.curve_no.setRange(0, 7)
        self.curve_no.setPrefix("curve ")
        self.curve_no.valueChanged.connect(self._show)
        self.curve_no.setVisible(False)

        self.unlock = QtWidgets.QCheckBox("Let me edit this")
        self.unlock.toggled.connect(self._relock)

        self.revert_btn = QtWidgets.QPushButton("Undo my changes")
        self.revert_btn.clicked.connect(self._revert)
        self.revert_btn.setEnabled(False)

        self.curve = TableEditor()
        self.curve.valuesChanged.connect(self._write_back)

        self.values = QtWidgets.QPlainTextEdit()
        self.values.setReadOnly(True)
        self.values.setMaximumHeight(150)
        self.values.setFont(
            QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        )

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Table"))
        top.addWidget(self.picker, 1)
        top.addWidget(self.curve_no)
        top.addWidget(self.unlock)
        top.addWidget(self.revert_btn)

        self.note = QtWidgets.QLabel("")
        self.note.setStyleSheet("color: #8b93a5;")
        self.note.setWordWrap(True)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addLayout(top)
        lay.addWidget(self.note)
        lay.addWidget(self.curve, 1)
        lay.addWidget(self.values)

    def set_rom(self, prog):
        self.prog = prog
        self._original = {}
        self._show()

    def _current(self):
        return self.picker.currentData()

    def _show(self):
        if self.prog is None:
            self.curve.set_values([])
            self.values.clear()
            return
        name = self._current()
        self._name = name
        is_velocity = name == "velocity"
        self.curve_no.setVisible(is_velocity)

        if is_velocity:
            values = tbl.velocity_curve(self.prog, self.curve_no.value())
            top = 127
        else:
            values = self.prog.table(name)
            top = max(values) or 1

        key = (name, self.curve_no.value() if is_velocity else 0)
        self._original.setdefault(key, list(values))
        self.revert_btn.setEnabled(values != self._original[key])

        locked = name in self.DANGEROUS and not self.unlock.isChecked()
        self.unlock.setEnabled(name in self.DANGEROUS)
        self.unlock.setVisible(name in self.DANGEROUS)
        self.curve.set_values(values, top, readonly=locked)

        if name in self.DANGEROUS:
            self.note.setText(
                "This maps cents to the chip's pitch number. Redrawing it "
                "detunes the whole module, which is almost never what you "
                "want, so tick the box if you really mean it."
            )
        elif is_velocity:
            self.note.setText(
                "Eight curves decide how key velocity becomes level. Each "
                "voice element picks one. Drag to redraw."
            )
        else:
            self.note.setText(tbl.SPECS[name][3] + ". Drag to redraw.")
        self._dump(values)

    def _relock(self):
        self._show()

    def _write_back(self):
        if self.prog is None or self._name is None:
            return
        values = self.curve.values
        if self._name == "velocity":
            whole = self.prog.table("velocity")
            base = self.curve_no.value() * 128
            whole[base : base + 128] = values
            tbl.write(self.prog, "velocity", whole)
        else:
            tbl.write(self.prog, self._name, values)
        self.revert_btn.setEnabled(True)
        self._dump(values)
        self.romChanged.emit()

    def _revert(self):
        key = (self._name, self.curve_no.value() if self._name == "velocity" else 0)
        if key not in self._original:
            return
        self.curve.set_values(
            list(self._original[key]), self.curve.top, self.curve.readonly
        )
        self._write_back()
        self.revert_btn.setEnabled(False)

    def _dump(self, values):
        lines = []
        for i in range(0, len(values), 16):
            chunk = " ".join(f"{v:5d}" for v in values[i : i + 16])
            lines.append(f"{i:5d}  {chunk}")
        self.values.setPlainText("\n".join(lines))
