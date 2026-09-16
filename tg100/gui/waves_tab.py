"""The wave table tab: browse, preview, audition, export and replace waves."""

from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from .. import codec, naming
from ..rom import RomError
from ..waves import NATIVE_SAMPLE_RATE
from . import audio
from .waveform import WaveformView

# label, attribute on WaveHeader, maximum
HEADER_FIELDS = (
    ("LFO speed", "lfo_speed", 7),
    ("Vibrato depth", "vibrato_depth", 7),
    ("Tremolo depth", "tremolo_depth", 7),
    ("EG attack", "eg_attack_rate", 15),
    ("EG decay 1", "eg_decay1_rate", 15),
    ("EG decay 2", "eg_decay2_rate", 15),
    ("EG decay level", "eg_decay_level", 15),
    ("EG release", "eg_release_rate", 15),
    ("EG rate scale", "eg_rate_scale", 15),
)


class WavesTab(QtWidgets.QWidget):
    romChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rom = None
        self.prog = None
        self.names = None
        self._wave = None
        self._loading = False
        self._player = audio.Player(self)
        self._build()

    def _build(self):
        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Name", "Length", "Loop", "Uses"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(QtCore.Qt.ElideRight)
        self.table.itemSelectionChanged.connect(self._on_select)

        left = QtWidgets.QWidget()
        lv = QtWidgets.QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        self.show_empty = QtWidgets.QCheckBox("Show unused slots")
        self.show_empty.toggled.connect(self.reload)
        lv.addWidget(self.show_empty)
        lv.addWidget(self.table)
        split.addWidget(left)

        right = QtWidgets.QWidget()
        rv = QtWidgets.QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)

        self.view = WaveformView()
        self.view.positionClicked.connect(self._on_click_position)
        self.view.loopDragged.connect(self._on_loop_dragged)
        rv.addWidget(self.view, 1)

        self.info = QtWidgets.QLabel("Load a sample ROM to begin.")
        self.info.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.info.setWordWrap(True)
        rv.addWidget(self.info)

        # transient messages live on their own line, so they never wipe out the
        # wave description or, worse, an overlap warning
        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("color: #8b93a5;")
        rv.addWidget(self.status)

        rv.addLayout(self._build_transport())
        rv.addWidget(self._build_editor())

        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([560, 840])

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.addWidget(split)

    def _build_transport(self):
        row = QtWidgets.QHBoxLayout()

        self.play_btn = QtWidgets.QPushButton("Play")
        self.play_btn.clicked.connect(self._play)
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.clicked.connect(self._player.stop)
        row.addWidget(self.play_btn)
        row.addWidget(self.stop_btn)

        row.addSpacing(12)
        row.addWidget(QtWidgets.QLabel("Pitch"))
        self.pitch = QtWidgets.QSpinBox()
        self.pitch.setRange(-36, 36)
        self.pitch.setSuffix(" st")
        row.addWidget(self.pitch)

        self.loop_playback = QtWidgets.QCheckBox("Play loop")
        self.loop_playback.setChecked(True)
        row.addWidget(self.loop_playback)

        row.addStretch(1)

        zoom = QtWidgets.QPushButton("Fit")
        zoom.clicked.connect(self.view.reset_zoom)
        row.addWidget(zoom)

        self.export_btn = QtWidgets.QPushButton("Export WAV")
        self.export_btn.clicked.connect(self._export)
        row.addWidget(self.export_btn)

        self.import_btn = QtWidgets.QPushButton("Replace from WAV")
        self.import_btn.clicked.connect(self._import)
        row.addWidget(self.import_btn)

        return row

    def _build_editor(self):
        box = QtWidgets.QGroupBox("Wave header")
        grid = QtWidgets.QGridLayout(box)
        self.spins = {}

        self.loop_spin = QtWidgets.QSpinBox()
        self.loop_spin.setRange(0, 0xFFFF)
        self.loop_spin.valueChanged.connect(self._on_loop_spin)
        grid.addWidget(QtWidgets.QLabel("Loop point"), 0, 0)
        grid.addWidget(self.loop_spin, 0, 1)

        for i, (label, attr, top) in enumerate(HEADER_FIELDS, start=1):
            spin = QtWidgets.QSpinBox()
            spin.setRange(0, top)
            spin.valueChanged.connect(
                lambda value, a=attr: self._on_field(a, value)
            )
            self.spins[attr] = spin
            col = ((i) // 5) * 2
            row = (i) % 5
            grid.addWidget(QtWidgets.QLabel(label), row, col)
            grid.addWidget(spin, row, col + 1)

        grid.setColumnStretch(5, 1)
        return box

    def set_roms(self, sample_rom, program_rom=None, names=None):
        self.rom = sample_rom
        self.prog = program_rom
        self.names = names
        if program_rom is not None and names is None:
            self.names = naming.Names(program_rom)
        self.reload()

    def reload(self):
        self.table.setRowCount(0)
        if self.rom is None:
            return

        waves = self.rom.waves()
        if not self.show_empty.isChecked():
            waves = [w for w in waves if not w.is_empty]

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(waves))
        for r, w in enumerate(waves):
            empty = w.is_empty
            used = self.names.users_of(w.index) if self.names else []
            summary = "" if empty else (str(len(used)) if used else "-")
            cells = [
                str(w.index),
                "" if empty else (self.names.wave(w.index) if self.names else ""),
                "" if empty else str(w.length),
                "" if empty else (str(w.loop) if w.loops else "one shot"),
                summary,
            ]
            for c, text in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(text)
                item.setData(QtCore.Qt.UserRole, w.index)
                if c == 1 and used:
                    item.setToolTip("\n".join(used))
                if c in (0, 2):
                    item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                if empty:
                    item.setForeground(QtGui.QColor("#6b7280"))
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        if self.table.rowCount():
            self.table.selectRow(0)

    def _selected_index(self):
        items = self.table.selectedItems()
        if not items:
            return None
        return items[0].data(QtCore.Qt.UserRole)

    def _on_select(self):
        self.status.clear()
        idx = self._selected_index()
        if idx is None or self.rom is None:
            return
        self._wave = self.rom.wave(idx)
        self._refresh_wave()

    def _refresh_wave(self):
        w = self._wave
        if w is None:
            return
        self._loading = True
        try:
            if w.is_empty:
                self.view.clear()
                self.info.setText(f"Wave {w.index} is an unused slot.")
                for spin in self.spins.values():
                    spin.setEnabled(False)
                self.loop_spin.setEnabled(False)
                return

            for spin in self.spins.values():
                spin.setEnabled(True)
            self.loop_spin.setEnabled(True)

            samples = w.samples()
            self.view.set_wave(samples, w.loop, w.loops)
            self.loop_spin.setMaximum(max(0, w.length))
            self.loop_spin.setValue(w.loop)
            for attr, spin in self.spins.items():
                spin.setValue(getattr(w, attr))

            shared = self.rom.shares_data_with(w.index)
            swallowed = self.rom.contains_waves(w.index)
            secs = w.length / NATIVE_SAMPLE_RATE
            stored = (w.raw()[5] << 8) | w.raw()[6]
            text = (
                f"Wave {w.index}    {w.format_name}    start 0x{w.start:06X}    "
                f"{w.length} samples ({secs:.3f} s at {NATIVE_SAMPLE_RATE:.0f} Hz)    "
                f"{w.byte_length} bytes    peak {int(abs(samples).max()) if len(samples) else 0}"
            )
            if swallowed:
                text += (
                    f"\nThis wave runs straight across {len(swallowed)} whole other waves "
                    f"({', '.join(str(i) for i in swallowed[:8])}"
                    f"{', ...' if len(swallowed) > 8 else ''}), so what you hear after the "
                    f"first sound is unrelated material. The ROM stores its length as "
                    f"0x{stored:04X}, which decodes to {w.length}. That is what is in the ROM, "
                    f"not a decoding error, so treat this wave as suspect rather than as a "
                    f"sound you can edit safely."
                )
            elif shared:
                text += (
                    f"\nShares ROM data with wave(s) {', '.join(str(i) for i in shared[:10])}"
                    f"{', ...' if len(shared) > 10 else ''}, editing affects them too."
                )
            self.info.setText(text)
        finally:
            self._loading = False

    def _on_field(self, attr, value):
        if self._loading or self._wave is None:
            return
        setattr(self._wave, attr, value)
        self.romChanged.emit()

    def _on_loop_spin(self, value):
        if self._loading or self._wave is None:
            return
        self._wave.loop = value
        self.view.set_wave(self._wave.samples(), self._wave.loop, self._wave.loops)
        self.romChanged.emit()

    def _on_loop_dragged(self, pos):
        if self._wave is None or self._wave.is_empty:
            return
        self.loop_spin.setValue(int(pos))

    def _on_click_position(self, pos):
        self.view.set_cursor(pos)

    def _play(self):
        if self._wave is None or self._wave.is_empty:
            return
        if not self._player.available:
            QtWidgets.QMessageBox.information(
                self, "No audio", "QtMultimedia is not available in this Qt build."
            )
            return
        buf = audio.render(
            self._wave.samples(),
            loop=self._wave.loop,
            loops=self._wave.loops and self.loop_playback.isChecked(),
            semitones=self.pitch.value(),
            seconds=2.0,
        )
        self._player.play(buf)

    def _export(self):
        if self._wave is None or self._wave.is_empty:
            return
        name = f"tg100_wave_{self._wave.index:03d}.wav"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export wave", name, "WAV files (*.wav)"
        )
        if not path:
            return
        codec.write_wav(path, self._wave.samples(), NATIVE_SAMPLE_RATE)
        self.status.setText(f"Exported wave {self._wave.index} to {path}")

    def _import(self):
        if self._wave is None or self._wave.is_empty or self.rom is None:
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Replace wave from WAV", "", "WAV files (*.wav)"
        )
        if not path:
            return

        try:
            samples, rate = codec.read_wav(path)
        except (OSError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, "Could not read WAV", str(exc))
            return

        w = self._wave
        shared = self.rom.shares_data_with(w.index)
        if shared and not self._confirm_shared(w.index, shared):
            return

        need = codec.packed_size(len(samples))
        have = w.byte_length
        if need > have:
            samples = self._resolve_overflow(samples, need, have, Path(path).name)
            if samples is None:
                return

        try:
            w.write_samples(samples, relocate=True)
        except (RomError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, "Could not write wave", str(exc))
            return

        if abs(rate - NATIVE_SAMPLE_RATE) > 1.0:
            self.status.setText(
                f"Imported {Path(path).name}. Note it was {rate} Hz and the wave "
                f"table runs at {NATIVE_SAMPLE_RATE:.0f} Hz, so it will play back "
                f"{'sharp' if rate < NATIVE_SAMPLE_RATE else 'flat'}."
            )
        self.reload()
        self._select_index(w.index)
        self.romChanged.emit()

    def _resolve_overflow(self, samples, need, have, filename):
        free = self.rom.free_bytes()
        largest = max((b - a for a, b in self.rom.free_regions()), default=0)
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Question)
        box.setWindowTitle("Wave does not fit")
        box.setText(
            f"{filename} needs {need} bytes but this slot holds {have}.\n\n"
            f"The sample ROM has {free} bytes free in total and the largest "
            f"single gap is {largest} bytes."
        )
        box.setInformativeText(
            "The factory ROM is packed almost solid, so moving a wave somewhere "
            "else usually needs another wave shortened first."
        )
        trunc = box.addButton("Truncate to fit", QtWidgets.QMessageBox.AcceptRole)
        move = box.addButton("Move it elsewhere", QtWidgets.QMessageBox.ActionRole)
        box.addButton(QtWidgets.QMessageBox.Cancel)
        move.setEnabled(largest >= need)
        box.exec()

        clicked = box.clickedButton()
        if clicked is trunc:
            fits = (have * 2) // 3
            return samples[:fits]
        if clicked is move:
            return samples
        return None

    def _confirm_shared(self, index, shared):
        answer = QtWidgets.QMessageBox.question(
            self,
            "Wave data is shared",
            f"Wave {index} overlaps wave(s) {shared} in the ROM. Replacing it "
            f"will change how those sound too.\n\nGo ahead?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        return answer == QtWidgets.QMessageBox.Yes

    def _select_index(self, index):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is not None and item.data(QtCore.Qt.UserRole) == index:
                self.table.selectRow(r)
                return
