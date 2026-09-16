"""Editable program change maps.

Each bank is 128 program numbers pointing at a voice. The GM column is there so
you can see at a glance where Yamaha's voice does not match what General MIDI
asks for at that program number.
"""

from PySide6 import QtCore, QtWidgets

from .. import layout, naming


class BanksTab(QtWidgets.QWidget):
    romChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prog = None
        self.names = None
        self._bank = None
        self._loading = False

        self.bank = QtWidgets.QComboBox()
        self.bank.currentIndexChanged.connect(self._reload)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Program", "General MIDI name", "Voice", "Assigned voice", "Waves"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setWordWrap(False)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Bank"))
        top.addWidget(self.bank)
        top.addStretch(1)
        self.hint = QtWidgets.QLabel(
            "Pick a different voice in the Assigned voice column to remap a program."
        )
        self.hint.setStyleSheet("color: #8b93a5;")
        top.addWidget(self.hint)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addLayout(top)
        lay.addWidget(self.table)

    def set_rom(self, prog, names=None):
        self.prog = prog
        self.names = names
        self.bank.blockSignals(True)
        self.bank.clear()
        if prog is not None:
            self.names = names or naming.Names(prog)
            self.bank.addItem("Internal", -1)
            for i, b in enumerate(prog.banks()):
                self.bank.addItem(b.name, i)
        self.bank.blockSignals(False)
        self._reload()

    def _voice_items(self):
        items = [(i, f"{i:3d}  {n}") for i, n in enumerate(self.prog.voice_names())]
        items.append((layout.VOICE_OFF, "255  off"))
        return items

    def _reload(self):
        self.table.setRowCount(0)
        if self.prog is None or self.bank.currentIndex() < 0:
            return
        self._loading = True
        try:
            self._bank = self.prog.bank(self.bank.currentData())
            items = self._voice_items()
            self.table.setRowCount(128)
            for p in range(128):
                idx = self._bank.voice_index(p)
                self.table.setItem(p, 0, QtWidgets.QTableWidgetItem(str(p)))
                self.table.setItem(
                    p, 1, QtWidgets.QTableWidgetItem(naming.gm_program(p))
                )
                self.table.setItem(p, 2, QtWidgets.QTableWidgetItem(str(idx)))

                combo = QtWidgets.QComboBox()
                for value, label in items:
                    combo.addItem(label, value)
                pos = combo.findData(idx)
                if pos < 0:
                    combo.addItem(f"{idx}  unknown", idx)
                    pos = combo.count() - 1
                combo.setCurrentIndex(pos)
                combo.currentIndexChanged.connect(
                    lambda _, prog_no=p, c=combo: self._on_change(prog_no, c)
                )
                self.table.setCellWidget(p, 3, combo)
                self.table.setItem(p, 4, QtWidgets.QTableWidgetItem(self._waves(idx)))
            self.table.resizeColumnsToContents()
        finally:
            self._loading = False

    def _waves(self, idx):
        if idx >= layout.NUM_VOICES or self.names is None:
            return ""
        v = self.prog.voice(idx)
        out = self.names.wave_no(v.element(0).wave_no)
        if v.mode:
            out += " + " + self.names.wave_no(v.element(1).wave_no)
        return out

    def _on_change(self, program, combo):
        if self._loading or self._bank is None:
            return
        idx = combo.currentData()
        self._bank.set_voice_index(program, idx)
        self.table.item(program, 2).setText(str(idx))
        self.table.item(program, 4).setText(self._waves(idx))
        self.romChanged.emit()
