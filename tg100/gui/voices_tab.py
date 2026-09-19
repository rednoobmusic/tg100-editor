"""Editable voice browser.

Every control writes straight into the program ROM. The element 2 panel greys
out in single mode because the hardware ignores it there, but the bytes are
still present and come back if you switch to dual.
"""

from PySide6 import QtCore, QtWidgets

from .. import layout, naming, sysex
from ..voices import (
    DUAL,
    PITCH_EG_RANGES,
    PEG_LEVELS,
    PEG_RATES,
    PITCH_LFO_WAVES,
    PITCH_RATE_SCALES,
    SINGLE,
)
from .curves import LevelScaleEditor, PitchEGEditor
from .widgets import BoundCombo, BoundSlider, BoundSpin, BoundText, FieldGrid


class ElementPanel(QtWidgets.QGroupBox):
    changed = QtCore.Signal()

    def __init__(self, slot, parent=None):
        super().__init__(f"Element {slot + 1}", parent)
        self.slot = slot
        self.voice = None
        self.names = None

        self.grids = []
        self.peg_view = PitchEGEditor()
        self.scale_view = LevelScaleEditor()

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self.scroll)

        self.sets = QtWidgets.QTableWidget(0, 6)
        self.sets.setHorizontalHeaderLabels(
            ["Set", "Wave", "Name", "Key range", "Root", "Tune"]
        )
        self.sets.verticalHeader().setVisible(False)
        self.sets.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.sets.horizontalHeader().setStretchLastSection(True)
        self.sets.setMaximumHeight(170)

    def bind(self, voice, names):
        """Rebuild the controls for a voice. Called once per selection."""
        self.voice = voice
        self.names = names
        slot = self.slot
        e = voice.element(slot)

        body = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        self.grids = []

        def section(title):
            box = QtWidgets.QGroupBox(title)
            lay = QtWidgets.QVBoxLayout(box)
            lay.setContentsMargins(8, 6, 8, 8)
            grid = FieldGrid()
            grid.changed.connect(self.changed)
            lay.addWidget(grid)
            self.grids.append(grid)
            outer.addWidget(box)
            return grid, lay

        wave_items = [
            (n, f"{n:3d}  {names.wave_no(n)}") for n in range(layout.NUM_WAVE_NOS)
        ]

        sound, _ = section("Sound")
        self.wave_field = sound.add(
            "Wave", BoundCombo(lambda: e.wave_no, self._set_wave, wave_items)
        )
        sound.add("Level", BoundSlider(
            lambda: voice.level(slot), lambda v: voice.set_level(slot, v), 0, 127))
        sound.add("Pan", BoundSlider(
            lambda: e.pan, lambda v: setattr(e, "pan", v), 0, 15, naming.pan))
        sound.add("Velocity curve", BoundSpin(
            lambda: e.velocity_curve,
            lambda v: setattr(e, "velocity_curve", v), 0, 7))
        sound.add("Amp attack", BoundSlider(
            lambda: e.eg_attack_rate,
            lambda v: setattr(e, "eg_attack_rate", v), 0, 127))
        sound.add("Amp release", BoundSlider(
            lambda: e.eg_release_rate,
            lambda v: setattr(e, "eg_release_rate", v), 0, 127))
        sound.stretch()

        tune, _ = section("Tuning")
        tune.add("Detune", BoundSlider(
            lambda: voice.detune(slot), lambda v: voice.set_detune(slot, v),
            0, 127, naming.detune))
        tune.add("Note shift", BoundSlider(
            lambda: voice.note_shift(slot),
            lambda v: voice.set_note_shift(slot, v), 0, 127, naming.note_shift))
        tune.add("Rate scale", BoundCombo(
            lambda: voice.pitch_rate_scale(slot),
            lambda v: voice.set_pitch_rate_scale(slot, v),
            list(enumerate(PITCH_RATE_SCALES))))
        tune.add("Rate scale centre", BoundSpin(
            lambda: voice.pitch_rate_scale_center(slot),
            lambda v: voice.set_pitch_rate_scale_center(slot, v),
            0, 127, naming.note_name))
        tune.stretch()

        lfo, _ = section("LFO")
        lfo.add("Speed", BoundSlider(
            lambda: e.lfo_speed, lambda v: setattr(e, "lfo_speed", v), 0, 7))
        lfo.add("Delay", BoundSlider(
            lambda: e.lfo_delay, lambda v: setattr(e, "lfo_delay", v), 0, 127))
        lfo.add("To pitch", BoundSlider(
            lambda: e.lfo_pitch_depth,
            lambda v: setattr(e, "lfo_pitch_depth", v), 0, 15))
        lfo.add("To level", BoundSlider(
            lambda: e.lfo_amp_depth,
            lambda v: setattr(e, "lfo_amp_depth", v), 0, 7))
        lfo.add("Pitch wave", BoundCombo(
            lambda: e.pitch_lfo_wave,
            lambda v: setattr(e, "pitch_lfo_wave", v),
            list(enumerate(PITCH_LFO_WAVES))))
        lfo.stretch()

        peg, peg_layout = section("Pitch envelope")
        self.peg_view = PitchEGEditor()
        self.peg_view.levelChanged.connect(self._peg_level)
        self.peg_view.rateChanged.connect(self._peg_rate)
        peg_layout.insertWidget(0, self.peg_view)
        peg.add("Range", BoundCombo(
            lambda: e.pitch_eg_range,
            lambda v: setattr(e, "pitch_eg_range", v),
            list(enumerate(PITCH_EG_RANGES))))
        peg.add("Rate scale", BoundSpin(
            lambda: e.pitch_eg_rate_scale,
            lambda v: setattr(e, "pitch_eg_rate_scale", v), 0, 7))
        for j, label in enumerate(PEG_RATES):
            peg.add(f"{label} rate".capitalize(), BoundSpin(
                (lambda j=j: e.pitch_eg_rate(j)),
                (lambda v, j=j: e.set_pitch_eg_rate(j, v)), 0, 63))
        for j, label in enumerate(PEG_LEVELS):
            peg.add(f"{label} level".capitalize(), BoundSpin(
                (lambda j=j: e.pitch_eg_level(j)),
                (lambda v, j=j: e.set_pitch_eg_level(j, v)), 0, 127))
        peg.stretch()

        scale, scale_layout = section("Level scaling")
        self.scale_view = LevelScaleEditor()
        self.scale_view.pointChanged.connect(self._scale_point)
        scale_layout.insertWidget(0, self.scale_view)
        for j in range(4):
            scale.add(f"Break {j + 1}", BoundSpin(
                (lambda j=j: e.level_scale_breakpoint(j)),
                (lambda v, j=j: e.set_level_scale_breakpoint(j, v)),
                0, 127, naming.note_name))
            scale.add(f"Offset {j + 1}", BoundSpin(
                (lambda j=j: e.level_scale_offset(j)),
                (lambda v, j=j: e.set_level_scale_offset(j, v)), 0, 255))
        scale.stretch()

        outer.addWidget(QtWidgets.QLabel("Sample sets for this wave"))
        outer.addWidget(self.sets)
        outer.addStretch(1)

        old = self.scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self.scroll.setWidget(body)

        for grid in self.grids:
            grid.changed.connect(self._redraw)
            grid.refresh()
        self._redraw()
        self._refresh_sets()

    def _peg_level(self, index, value):
        if self.voice is None:
            return
        self.voice.element(self.slot).set_pitch_eg_level(index, value)
        self._resync()

    def _peg_rate(self, index, value):
        if self.voice is None:
            return
        self.voice.element(self.slot).set_pitch_eg_rate(index, value)
        self._resync()

    def _scale_point(self, index, note, value):
        if self.voice is None:
            return
        e = self.voice.element(self.slot)
        e.set_level_scale_breakpoint(index, note)
        e.set_level_scale_offset(index, value)
        self._resync()

    def _resync(self):
        """A drag changed the ROM, so pull the numbers back into line."""
        for grid in self.grids:
            grid.refresh()
        self.changed.emit()

    def _redraw(self):
        """Keep the two plots in step with the numbers beside them."""
        if self.voice is None:
            return
        e = self.voice.element(self.slot)
        self.peg_view.set_envelope(
            [e.pitch_eg_level(i) for i in range(len(PEG_LEVELS))],
            [e.pitch_eg_rate(i) for i in range(len(PEG_RATES))],
            PITCH_EG_RANGES[e.pitch_eg_range],
        )
        self.scale_view.set_points(
            [e.level_scale_breakpoint(i) for i in range(4)],
            [e.level_scale_offset(i) for i in range(4)],
        )

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


class VoicesTab(QtWidgets.QWidget):
    romChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prog = None
        self.names = None
        self._voice = None

        self.list = QtWidgets.QTableWidget(0, 6)
        self.list.setHorizontalHeaderLabels(
            ["#", "Name", "Family", "Mode", "Waves", "Reachable at"]
        )
        self.list.setTextElideMode(QtCore.Qt.ElideRight)
        self.list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.list.verticalHeader().setVisible(False)
        self.list.setWordWrap(False)
        self.list.setSortingEnabled(True)
        self.list.itemSelectionChanged.connect(self._on_select)

        self.filter = QtWidgets.QLineEdit()
        self.filter.setPlaceholderText(
            "Filter by name, family, or the wave it uses"
        )
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._apply_filter)

        self.count_label = QtWidgets.QLabel("")
        self.count_label.setStyleSheet("color: #8b93a5;")

        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(self.filter)
        lv.addWidget(self.count_label)
        lv.addWidget(self.list)

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
            elems.addWidget(panel)

        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.addWidget(common_box)
        rv.addLayout(elems, 1)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([520, 980])

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
        self.list.setSortingEnabled(False)
        self.list.setRowCount(len(voices))
        for r, v in enumerate(voices):
            self._fill_row(r, v)
        self.list.setSortingEnabled(True)
        self.list.sortItems(0, QtCore.Qt.AscendingOrder)
        self.list.resizeColumnsToContents()
        self.list.horizontalHeader().setStretchLastSection(True)
        self._apply_filter(self.filter.text())

    def _waves_for(self, v):
        waves = self.names.wave_no(v.element(0).wave_no)
        if v.mode == DUAL:
            waves += " + " + self.names.wave_no(v.element(1).wave_no)
        return waves

    def _fill_row(self, row, v):
        cells = [
            v.index,
            v.name,
            self.names.voice_family(v.index),
            v.mode_name,
            self._waves_for(v),
            self.names.voice_usage(v.index),
        ]
        for c, text in enumerate(cells):
            item = self.list.item(row, c)
            if item is None:
                item = QtWidgets.QTableWidgetItem()
                self.list.setItem(row, c, item)
            if c == 0:
                item.setData(QtCore.Qt.DisplayRole, int(text))
                item.setTextAlignment(
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
                )
            else:
                item.setText(str(text))
            item.setData(QtCore.Qt.UserRole, v.index)
        if self.names.voice_family(v.index) == "unreachable":
            for c in range(self.list.columnCount()):
                self.list.item(row, c).setForeground(QtGui.QColor("#6b7280"))

    def _apply_filter(self, text):
        text = (text or "").strip().lower()
        shown = 0
        for r in range(self.list.rowCount()):
            if not text:
                visible = True
            else:
                haystack = " ".join(
                    (self.list.item(r, c).text() or "").lower()
                    for c in (1, 2, 4, 5)
                )
                visible = text in haystack
            self.list.setRowHidden(r, not visible)
            shown += visible
        total = self.list.rowCount()
        self.count_label.setText(
            f"{total} voices" if shown == total else f"{shown} of {total} voices"
        )

    def _row_for_voice(self, index):
        for r in range(self.list.rowCount()):
            item = self.list.item(r, 0)
            if item is not None and item.data(QtCore.Qt.UserRole) == index:
                return r
        return -1

    def _on_select(self):
        items = self.list.selectedItems()
        if self.prog is None or not items:
            return
        index = items[0].data(QtCore.Qt.UserRole)
        if index is None:
            return
        self._voice = self.prog.voice(index)
        self._bind()

    def _bind(self):
        v = self._voice
        new = FieldGrid()
        new.changed.connect(self._on_edit)
        new.add("Name", BoundText(lambda: v.name, self._set_name, 8))
        send = QtWidgets.QPushButton("Send to hardware as .syx...")
        send.setToolTip(
            "Write this voice as a sysex file. Play it into a real TG100 over "
            "MIDI and it lands in one of the 64 internal voice slots, so you "
            "can hear an edit without burning anything."
        )
        send.clicked.connect(self._export_sysex)
        new.add_widget("Audition", send)
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

    def _export_sysex(self):
        """One sysex message that writes this voice into the device's RAM."""
        v = self._voice
        if v is None:
            return
        slot, ok = QtWidgets.QInputDialog.getInt(
            self, "Internal voice slot",
            "The TG100 holds 64 voices in RAM. Which one should this overwrite?",
            0, 0, sysex.NUM_VOICES - 1,
        )
        if not ok:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save sysex", f"{v.name.strip() or 'voice'}.syx",
            "Sysex files (*.syx)",
        )
        if not path:
            return
        address = sysex.MULTI_BASE + sysex.VOICES_OFS + slot * layout.VOICE_SIZE
        message = sysex.encode(address, v.raw())
        try:
            with open(path, "wb") as fp:
                fp.write(message)
        except OSError as exc:
            QtWidgets.QMessageBox.warning(self, "Could not save", str(exc))
            return
        QtWidgets.QMessageBox.information(
            self, "Saved",
            f"Wrote {len(message)} bytes.\n\nSending this to a TG100 puts "
            f"{v.name.strip()!r} in internal voice {slot}. Select that voice on "
            f"the module to hear it.",
        )

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
        row = self._row_for_voice(self._voice.index)
        if row >= 0:
            sorting = self.list.isSortingEnabled()
            self.list.setSortingEnabled(False)
            self._fill_row(row, self._voice)
            self.list.setSortingEnabled(sorting)
        self.romChanged.emit()
