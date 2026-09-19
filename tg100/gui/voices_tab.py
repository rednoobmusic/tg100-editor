"""Editable voice browser.

Every control writes straight into the program ROM. The element 2 panel greys
out in single mode because the hardware ignores it there, but the bytes are
still present and come back if you switch to dual.
"""

from PySide6 import QtCore, QtWidgets

from .. import layout, naming
from ..voices import (
    DUAL,
    PEG_LEVELS,
    PEG_RATES,
    PITCH_LFO_WAVES,
    PITCH_RATE_SCALES,
    SINGLE,
)
from .widgets import BoundCombo, BoundSpin, BoundText, FieldGrid


class ElementPanel(QtWidgets.QGroupBox):
    changed = QtCore.Signal()

    def __init__(self, slot, parent=None):
        super().__init__(f"Element {slot + 1}", parent)
        self.slot = slot
        self.voice = None
        self.names = None

        self.grid = FieldGrid()
        self.grid.changed.connect(self.changed)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self.grid)

        self.sets = QtWidgets.QTableWidget(0, 6)
        self.sets.setHorizontalHeaderLabels(
            ["Set", "Wave", "Name", "Key range", "Root", "Tune"]
        )
        self.sets.verticalHeader().setVisible(False)
        self.sets.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.sets.horizontalHeader().setStretchLastSection(True)
        self.sets.setMaximumHeight(190)
        lay.addWidget(QtWidgets.QLabel("Sample sets for this wave number"))
        lay.addWidget(self.sets)

    def bind(self, voice, names):
        """Rebuild the controls for a voice. Called once per selection."""
        self.voice = voice
        self.names = names

        # rebuilding the grid beats rebinding every closure to a new record
        new = FieldGrid()
        new.changed.connect(self.changed)
        slot = self.slot
        e = voice.element(slot)

        wave_items = [
            (n, f"{n:3d}  {names.wave_no(n)}") for n in range(layout.NUM_WAVE_NOS)
        ]
        self.wave_field = new.add(
            "Wave number",
            BoundCombo(lambda: e.wave_no, self._set_wave, wave_items),
        )
        new.add(
            "Level",
            BoundSpin(lambda: voice.level(slot), lambda v: voice.set_level(slot, v), 0, 127),
        )
        new.add(
            "Detune",
            BoundSpin(
                lambda: voice.detune(slot),
                lambda v: voice.set_detune(slot, v),
                0, 127, naming.detune,
            ),
        )
        new.add(
            "Note shift",
            BoundSpin(
                lambda: voice.note_shift(slot),
                lambda v: voice.set_note_shift(slot, v),
                0, 127, naming.note_shift,
            ),
        )
        new.add(
            "Pan",
            BoundSpin(
                lambda: e.pan, lambda v: setattr(e, "pan", v), 0, 15, naming.pan
            ),
        )
        new.add(
            "EG attack",
            BoundSpin(
                lambda: e.eg_attack_rate,
                lambda v: setattr(e, "eg_attack_rate", v), 0, 127,
            ),
        )
        new.add(
            "EG release",
            BoundSpin(
                lambda: e.eg_release_rate,
                lambda v: setattr(e, "eg_release_rate", v), 0, 127,
            ),
        )
        new.add(
            "Velocity curve",
            BoundSpin(
                lambda: e.velocity_curve,
                lambda v: setattr(e, "velocity_curve", v), 0, 7,
            ),
        )
        new.add(
            "LFO speed",
            BoundSpin(lambda: e.lfo_speed, lambda v: setattr(e, "lfo_speed", v), 0, 7),
        )
        new.add(
            "LFO delay",
            BoundSpin(lambda: e.lfo_delay, lambda v: setattr(e, "lfo_delay", v), 0, 127),
        )
        new.add(
            "LFO pitch depth",
            BoundSpin(
                lambda: e.lfo_pitch_depth,
                lambda v: setattr(e, "lfo_pitch_depth", v), 0, 15,
            ),
        )
        new.add(
            "LFO amp depth",
            BoundSpin(
                lambda: e.lfo_amp_depth,
                lambda v: setattr(e, "lfo_amp_depth", v), 0, 7,
            ),
        )
        new.add(
            "Pitch LFO wave",
            BoundCombo(
                lambda: e.pitch_lfo_wave,
                lambda v: setattr(e, "pitch_lfo_wave", v),
                list(enumerate(PITCH_LFO_WAVES)),
            ),
        )
        new.add(
            "Pitch EG range",
            BoundCombo(
                lambda: e.pitch_eg_range,
                lambda v: setattr(e, "pitch_eg_range", v),
                list(enumerate(naming_ranges())),
            ),
        )
        new.add(
            "Pitch rate scale",
            BoundCombo(
                lambda: voice.pitch_rate_scale(slot),
                lambda v: voice.set_pitch_rate_scale(slot, v),
                list(enumerate(PITCH_RATE_SCALES)),
            ),
        )
        new.add(
            "Rate scale centre",
            BoundSpin(
                lambda: voice.pitch_rate_scale_center(slot),
                lambda v: voice.set_pitch_rate_scale_center(slot, v),
                0, 127, naming.note_name,
            ),
        )
        for j, label in enumerate(PEG_RATES):
            new.add(
                f"Pitch EG {label}",
                BoundSpin(
                    (lambda j=j: e.pitch_eg_rate(j)),
                    (lambda v, j=j: e.set_pitch_eg_rate(j, v)),
                    0, 63,
                ),
            )
        for j, label in enumerate(PEG_LEVELS):
            new.add(
                f"Pitch level {label}",
                BoundSpin(
                    (lambda j=j: e.pitch_eg_level(j)),
                    (lambda v, j=j: e.set_pitch_eg_level(j, v)),
                    0, 127,
                ),
            )
        for j in range(4):
            new.add(
                f"Scale break {j + 1}",
                BoundSpin(
                    (lambda j=j: e.level_scale_breakpoint(j)),
                    (lambda v, j=j: e.set_level_scale_breakpoint(j, v)),
                    0, 127, naming.note_name,
                ),
            )
            new.add(
                f"Scale offset {j + 1}",
                BoundSpin(
                    (lambda j=j: e.level_scale_offset(j)),
                    (lambda v, j=j: e.set_level_scale_offset(j, v)),
                    0, 255,
                ),
            )
        new.stretch()

        old = self.layout().itemAt(0).widget()
        self.layout().replaceWidget(old, new)
        old.deleteLater()
        self.grid = new
        self.grid.refresh()
        self._refresh_sets()

    def _set_wave(self, value):
        self.voice.element(self.slot).wave_no = value
        self._refresh_sets()

    def _refresh_sets(self):
        if self.voice is None or self.names is None:
            return
        prog = self.voice.rom
        wave_no = self.voice.element(self.slot).wave_no
        sets = prog.sample_sets_for(wave_no) if wave_no < layout.NUM_WAVE_NOS else []
        self.sets.setRowCount(len(sets))
        for r, ss in enumerate(sets):
            cells = [
                ss.index,
                ss.wave_index,
                self.names.wave(ss.wave_index),
                naming.note_range(ss.note_low, ss.note_high),
                naming.note_name(ss.root_note),
                naming.fine_tune(ss.fine_tune),
            ]
            for c, text in enumerate(cells):
                self.sets.setItem(r, c, QtWidgets.QTableWidgetItem(str(text)))
        self.sets.resizeColumnsToContents()


def naming_ranges():
    from ..voices import PITCH_EG_RANGES

    return PITCH_EG_RANGES


class VoicesTab(QtWidgets.QWidget):
    romChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prog = None
        self.names = None
        self._voice = None

        self.list = QtWidgets.QTableWidget(0, 4)
        self.list.setHorizontalHeaderLabels(["#", "Name", "Mode", "Waves"])
        self.list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.list.verticalHeader().setVisible(False)
        self.list.horizontalHeader().setStretchLastSection(True)
        self.list.itemSelectionChanged.connect(self._on_select)

        self.common = FieldGrid()
        self.common.changed.connect(self._on_edit)
        common_box = QtWidgets.QGroupBox("Voice")
        cl = QtWidgets.QVBoxLayout(common_box)
        cl.addWidget(self.common)

        self.elements = [ElementPanel(0), ElementPanel(1)]
        for panel in self.elements:
            panel.changed.connect(self._on_edit)

        elems = QtWidgets.QHBoxLayout()
        for panel in self.elements:
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(panel)
            elems.addWidget(scroll)

        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(common_box)
        rv.addLayout(elems, 1)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.addWidget(self.list)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([360, 920])

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(split)

    def set_rom(self, prog, names=None):
        self.prog = prog
        self.names = names
        self.list.setRowCount(0)
        if prog is None:
            return
        self.names = names or naming.Names(prog)
        self._reload_list()
        if self.list.rowCount():
            self.list.selectRow(0)

    def _reload_list(self):
        voices = self.prog.voices()
        self.list.setRowCount(len(voices))
        for r, v in enumerate(voices):
            self._fill_row(r, v)
        self.list.resizeColumnsToContents()

    def _fill_row(self, row, v):
        waves = self.names.wave_no(v.element(0).wave_no)
        if v.mode == DUAL:
            waves += " + " + self.names.wave_no(v.element(1).wave_no)
        for c, text in enumerate([v.index, v.name, v.mode_name, waves]):
            item = self.list.item(row, c)
            if item is None:
                item = QtWidgets.QTableWidgetItem()
                self.list.setItem(row, c, item)
            item.setText(str(text))

    def _on_select(self):
        if self.prog is None or self.list.currentRow() < 0:
            return
        self._voice = self.prog.voice(self.list.currentRow())
        self._bind()

    def _bind(self):
        v = self._voice
        new = FieldGrid()
        new.changed.connect(self._on_edit)
        new.add("Name", BoundText(lambda: v.name, self._set_name, 8))
        new.add(
            "Mode",
            BoundCombo(
                lambda: v.mode,
                self._set_mode,
                [(SINGLE, "single"), (DUAL, "dual, both elements")],
            ),
        )
        new.add(
            "Portamento time",
            BoundSpin(
                lambda: v.portamento_time,
                lambda x: setattr(v, "portamento_time", x), 0, 127,
            ),
        )
        new.add(
            "Mod wheel to pitch",
            BoundSpin(
                lambda: v.mod_lfo_pitch_depth,
                lambda x: setattr(v, "mod_lfo_pitch_depth", x), 0, 15,
            ),
        )
        new.add(
            "Aftertouch to pitch",
            BoundSpin(
                lambda: v.aftertouch_lfo_pitch_depth,
                lambda x: setattr(v, "aftertouch_lfo_pitch_depth", x), 0, 15,
            ),
        )
        new.stretch()

        old = self.common
        self.common.parent().layout().replaceWidget(old, new)
        old.deleteLater()
        self.common = new
        self.common.refresh()

        for panel in self.elements:
            panel.bind(v, self.names)
        self._update_enabled()

    def _set_name(self, text):
        """Voice names are ASCII only, so say so instead of dropping the edit."""
        try:
            self._voice.name = text
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Name not allowed", str(exc))
            self.common.refresh()

    def _set_mode(self, value):
        self._voice.mode = value
        self._update_enabled()

    def _update_enabled(self):
        dual = self._voice is not None and self._voice.mode == DUAL
        self.elements[1].setEnabled(dual)
        self.elements[1].setTitle(
            "Element 2" if dual else "Element 2 (silent in single mode)"
        )

    def _on_edit(self):
        if self._voice is None:
            return
        row = self.list.currentRow()
        if row >= 0:
            self._fill_row(row, self._voice)
        self.romChanged.emit()
