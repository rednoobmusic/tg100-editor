"""Editable drum kits and the sounds they point at.

Kits share drum sounds, so changing a sound's tuning or level changes it in
every kit that uses it. The count in the last column says how many kits that
is, which is your warning before you touch it.
"""

from PySide6 import QtCore, QtWidgets

from .. import layout, naming
from .widgets import BoundCombo, BoundSpin, FieldGrid


class DrumsTab(QtWidgets.QWidget):
    romChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prog = None
        self.names = None
        self._sound = None

        self.kit = QtWidgets.QComboBox()
        self.kit.currentIndexChanged.connect(self._reload)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Note", "Name", "Sound", "Wave", "Sample", "Shared by"]
        )
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setWordWrap(False)
        self.table.itemSelectionChanged.connect(self._on_select)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Kit"))
        top.addWidget(self.kit)
        top.addStretch(1)

        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addLayout(top)
        lv.addWidget(self.table)

        self.editor = QtWidgets.QGroupBox("Drum sound")
        self.editor_layout = QtWidgets.QVBoxLayout(self.editor)
        self.fields = FieldGrid()
        self.editor_layout.addWidget(self.fields)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(self.editor)
        split.setStretchFactor(0, 1)
        split.setSizes([820, 420])

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(split)

    def set_rom(self, prog, names=None):
        self.prog = prog
        self.names = names
        self.kit.blockSignals(True)
        self.kit.clear()
        if prog is not None:
            self.names = names or naming.Names(prog)
            for i, name in enumerate(prog.drum_kit_names()):
                self.kit.addItem(f"{i}  {name}", i)
        self.kit.blockSignals(False)
        self._reload()

    def _sound_usage(self):
        """How many kits reference each drum sound."""
        counts = {}
        for kit in self.prog.drum_kits():
            for note in kit.mapped_notes():
                idx = kit.sound_index(note)
                counts[idx] = counts.get(idx, 0) + 1
        return counts

    def _reload(self):
        self.table.setRowCount(0)
        if self.prog is None or self.kit.currentIndex() < 0:
            return
        kit = self.prog.drum_kit(self.kit.currentData())
        counts = self._sound_usage()
        notes = kit.mapped_notes()
        self.table.setRowCount(len(notes))
        for r, note in enumerate(notes):
            idx = kit.sound_index(note)
            ds = self.prog.drum_sound(idx)
            shared = counts.get(idx, 1)
            cells = [
                f"{note}  {naming.note_name(note)}",
                naming.percussion_name(note),
                idx,
                ds.wave_index,
                self.names.wave(ds.wave_index) if self.names else "",
                "only here" if shared <= 1 else f"{shared} kits",
            ]
            for c, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(str(text))
                item.setData(QtCore.Qt.UserRole, idx)
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        if self.table.rowCount():
            self.table.selectRow(0)

    def _on_select(self):
        items = self.table.selectedItems()
        if not items or self.prog is None:
            return
        self._sound = self.prog.drum_sound(items[0].data(QtCore.Qt.UserRole))
        self._bind()

    def _bind(self):
        ds = self._sound
        new = FieldGrid()
        new.changed.connect(self._on_edit)

        wave_items = [(i, f"{i:3d}  {self.names.wave(i)}") for i in range(layout.NUM_WAVES)]
        wave_items.append((layout.DRUM_SOUND_OFF, "511  none"))
        new.add(
            "Wave",
            BoundCombo(
                lambda: ds.wave_index, lambda v: setattr(ds, "wave_index", v), wave_items
            ),
        )
        new.add(
            "Pitch coarse",
            BoundSpin(
                lambda: ds.pitch_coarse,
                lambda v: setattr(ds, "pitch_coarse", v),
                -64, 63,
                naming.semitones,
            ),
        )
        new.add(
            "Pitch fine",
            BoundSpin(
                lambda: ds.pitch_fine, lambda v: setattr(ds, "pitch_fine", v), 0, 127
            ),
        )
        new.add(
            "Attenuation",
            BoundSpin(
                lambda: ds.attenuation,
                lambda v: setattr(ds, "attenuation", v),
                0, 127, naming.attenuation,
            ),
        )
        new.add(
            "Pan",
            BoundSpin(
                lambda: ds.pan, lambda v: setattr(ds, "pan", v), 0, 15, naming.pan
            ),
        )
        new.add(
            "Reverb depth",
            BoundSpin(
                lambda: ds.reverb_depth, lambda v: setattr(ds, "reverb_depth", v), 0, 15
            ),
        )
        new.stretch()

        self.editor_layout.replaceWidget(self.fields, new)
        self.fields.deleteLater()
        self.fields = new
        self.fields.refresh()
        self.editor.setTitle(f"Drum sound {ds.index}")

    def _on_edit(self):
        self._reload_current_row()
        self.romChanged.emit()

    def _reload_current_row(self):
        row = self.table.currentRow()
        if row < 0 or self._sound is None:
            return
        ds = self._sound
        self.table.item(row, 3).setText(str(ds.wave_index))
        if self.names:
            self.table.item(row, 4).setText(self.names.wave(ds.wave_index))
