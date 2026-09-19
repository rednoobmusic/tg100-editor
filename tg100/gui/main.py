"""Main window."""

import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from .. import __version__, layout
from ..rom import ProgramRom, RomError, SampleRom
from .. import naming, repack, validate
from .banks_tab import BanksTab
from .browse import TablesTab
from .drums_tab import DrumsTab
from .voices_tab import VoicesTab
from .waves_tab import WavesTab

ORG = "rednoobmusic"
APP = "tg100-editor"

DARK = """
QWidget { background: #1b1e25; color: #d5d9e0; }
QTableWidget, QTextEdit, QPlainTextEdit { background: #16181d; }
QHeaderView::section { background: #232730; padding: 4px; border: 0; }
QGroupBox { border: 1px solid #2b303a; margin-top: 8px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; }
QPushButton { background: #2b303a; padding: 5px 12px; border: 0; }
QPushButton:hover { background: #363c49; }
QPushButton:disabled { color: #666c7a; }
QTabBar::tab { background: #232730; padding: 6px 14px; }
QTabBar::tab:selected { background: #2f3542; }
"""


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"TG100 ROM editor {__version__}")
        self.resize(1280, 800)

        self.prog = None
        self.smpl = None
        self.names = None
        self.settings = QtCore.QSettings(ORG, APP)

        self.waves = WavesTab()
        self.waves.romChanged.connect(self._on_changed)
        self.voices = VoicesTab()
        self.drums = DrumsTab()
        self.banks = BanksTab()
        self.tables = TablesTab()
        for tab in (self.voices, self.drums, self.banks):
            tab.romChanged.connect(self._on_changed)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.waves, "Waves")
        self.tabs.addTab(self.voices, "Voices")
        self.tabs.addTab(self.drums, "Drums")
        self.tabs.addTab(self.banks, "Banks")
        self.tabs.addTab(self.tables, "Tables")
        self.setCentralWidget(self.tabs)

        self._build_menu()
        self.status = self.statusBar()
        self._update_status()

    def _build_menu(self):
        bar = self.menuBar()
        f = bar.addMenu("&File")

        act = QtGui.QAction("Open &program ROM...", self)
        act.setShortcut("Ctrl+P")
        act.triggered.connect(self.open_program)
        f.addAction(act)

        act = QtGui.QAction("Open &sample ROM...", self)
        act.setShortcut("Ctrl+O")
        act.triggered.connect(self.open_sample)
        f.addAction(act)

        f.addSeparator()

        self.save_smpl_act = QtGui.QAction("Save sample ROM &as...", self)
        self.save_smpl_act.setShortcut("Ctrl+S")
        self.save_smpl_act.triggered.connect(self.save_sample)
        self.save_smpl_act.setEnabled(False)
        f.addAction(self.save_smpl_act)

        self.save_prog_act = QtGui.QAction("Save p&rogram ROM as...", self)
        self.save_prog_act.triggered.connect(self.save_program)
        self.save_prog_act.setEnabled(False)
        f.addAction(self.save_prog_act)

        f.addSeparator()
        act = QtGui.QAction("&Quit", self)
        act.setShortcut("Ctrl+Q")
        act.triggered.connect(self.close)
        f.addAction(act)

        t = bar.addMenu("&Tools")
        self.validate_act = QtGui.QAction("&Check both ROMs...", self)
        self.validate_act.setShortcut("Ctrl+K")
        self.validate_act.triggered.connect(self.run_validate)
        t.addAction(self.validate_act)

        self.space_act = QtGui.QAction("&Space report...", self)
        self.space_act.triggered.connect(self.show_space)
        self.space_act.setEnabled(False)
        t.addAction(self.space_act)

        self.repack_act = QtGui.QAction("&Repack sample ROM...", self)
        self.repack_act.triggered.connect(self.run_repack)
        self.repack_act.setEnabled(False)
        t.addAction(self.repack_act)
        t.addSeparator()
        self.fix_loops_act = QtGui.QAction("Make known single hits one shots...", self)
        self.fix_loops_act.triggered.connect(self.fix_bad_loops)
        self.fix_loops_act.setEnabled(False)
        t.addAction(self.fix_loops_act)

        h = bar.addMenu("&Help")
        act = QtGui.QAction("&About", self)
        act.triggered.connect(self._about)
        h.addAction(act)

    def _last_dir(self):
        return self.settings.value("last_dir", str(Path.home()))

    def _remember(self, path):
        self.settings.setValue("last_dir", str(Path(path).parent))

    def open_program(self, path=None):
        if not path:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Open program ROM", self._last_dir(), "ROM images (*.bin *.ic4);;All files (*)"
            )
        if not path:
            return
        try:
            self.prog = ProgramRom.load(path)
        except RomError as exc:
            QtWidgets.QMessageBox.warning(self, "Could not load", str(exc))
            return
        self._remember(path)
        self.save_prog_act.setEnabled(True)
        self.names = naming.Names(self.prog)
        for tab in (self.voices, self.drums, self.banks):
            tab.set_rom(self.prog, self.names)
        self.tables.set_rom(self.prog)
        if self.smpl is not None:
            self.waves.set_roms(self.smpl, self.prog, self.names)
        self._update_status()

    def open_sample(self, path=None):
        if not path:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Open sample ROM", self._last_dir(), "ROM images (*.bin *.ic6);;All files (*)"
            )
        if not path:
            return
        try:
            self.smpl = SampleRom.load(path)
        except RomError as exc:
            QtWidgets.QMessageBox.warning(self, "Could not load", str(exc))
            return
        self._remember(path)
        self.save_smpl_act.setEnabled(True)
        self.fix_loops_act.setEnabled(True)
        self.space_act.setEnabled(True)
        self.repack_act.setEnabled(True)
        self.waves.set_roms(self.smpl, self.prog, self.names)
        self._update_status()

    def run_validate(self, quiet=False):
        """Walk every reference between the two ROMs. Returns True if clean."""
        issues = validate.check(self.prog, self.smpl)
        if not issues:
            if not quiet:
                QtWidgets.QMessageBox.information(
                    self, "Check", "No problems found. Every reference between "
                    "the two ROMs resolves.",
                )
            return True

        text = "\n\n".join(str(i) for i in issues[:25])
        if len(issues) > 25:
            text += f"\n\nand {len(issues) - 25} more"
        box = QtWidgets.QMessageBox(self)
        box.setIcon(
            QtWidgets.QMessageBox.Critical if validate.errors(issues)
            else QtWidgets.QMessageBox.Warning
        )
        box.setWindowTitle("Check")
        box.setText(validate.summarise(issues))
        box.setDetailedText(text)
        box.exec()
        return not validate.errors(issues)

    def show_space(self):
        if self.smpl is None:
            return
        b = repack.budget(self.smpl)
        QtWidgets.QMessageBox.information(
            self, "Space",
            f"Wave data area: {b['total']} bytes\n"
            f"In use: {b['used']} bytes across {b['blocks']} blocks "
            f"holding {b['waves']} waves\n\n"
            f"Free right now: {b['free_now']} bytes, but the largest single run "
            f"is only {b['largest_run_now']}\n"
            f"After a repack that becomes one run of {b['free_after_repack']} "
            f"bytes\n\n"
            f"Waves share audio, so shortening one only frees space if nothing "
            f"else points into those bytes. Trimming silence across the whole "
            f"ROM is worth under 3 KB because Yamaha already trimmed it. Real "
            f"room comes from shortening or downsampling a wave you can live "
            f"without, which is worth tens of KB each.",
        )

    def run_repack(self):
        if self.smpl is None:
            return
        b = repack.budget(self.smpl)
        answer = QtWidgets.QMessageBox.question(
            self, "Repack sample ROM",
            f"Slide every wave down so the free space ends up in one run at the "
            f"top.\n\nLargest run now: {b['largest_run_now']} bytes\n"
            f"Largest run after: {b['free_after_repack']} bytes\n\n"
            f"Only addresses change, never sample data, so nothing can sound "
            f"different. Waves that share audio move together and keep sharing."
            f"\n\nGo ahead?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return
        try:
            result = repack.repack(self.smpl)
        except RomError as exc:
            QtWidgets.QMessageBox.warning(self, "Could not repack", str(exc))
            return
        self.waves.reload()
        self.status.showMessage(str(result), 10000)
        self._update_status()
        self.run_validate(quiet=True)

    def fix_bad_loops(self):
        """Turn the waves TG101 treats as single hits into one shots."""
        if self.smpl is None:
            return
        pending = self.smpl.waves_with_known_bad_loops()
        if not pending:
            QtWidgets.QMessageBox.information(
                self, "Nothing to fix",
                "Every wave on the known list is already a one shot.",
            )
            return

        listing = ", ".join(str(w.index) for w in pending[:24])
        if len(pending) > 24:
            listing += f", and {len(pending) - 24} more"
        answer = QtWidgets.QMessageBox.question(
            self,
            "Make single hits one shots",
            f"{len(pending)} waves are single hits whose loop point sits a few "
            f"samples before the end, so the hardware repeats a sliver of near "
            f"silence rather than stopping.\n\nThis sets each one's loop point to "
            f"its end, which is how the format says do not loop. It changes the "
            f"sample ROM, and nothing is written to disk until you save.\n\n"
            f"Waves: {listing}\n\nGo ahead?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return

        changed = self.smpl.fix_known_bad_loops()
        self.waves.reload()
        self.status.showMessage(f"Made {len(changed)} waves one shots", 8000)
        self._update_status()

    def save_sample(self):
        self._save(self.smpl, "Save sample ROM", "tg100smpl.bin")

    def save_program(self):
        self._save(self.prog, "Save program ROM", "tg100prog.bin")

    def _save(self, rom, title, default):
        if rom is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, title, str(Path(self._last_dir()) / default), "ROM images (*.bin)"
        )
        if not path:
            return
        issues = validate.check(self.prog, self.smpl)
        if validate.errors(issues):
            answer = QtWidgets.QMessageBox.question(
                self, "Save anyway?",
                f"The check found {validate.summarise(issues)}. Saving now "
                f"writes a ROM with broken references, which usually means "
                f"something goes silent on the hardware.\n\n"
                f"Run Tools then Check both ROMs to see the detail.\n\n"
                f"Save anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return

        try:
            rom.save(path)
        except (RomError, OSError) as exc:
            QtWidgets.QMessageBox.warning(self, "Could not save", str(exc))
            return
        rom.mark_saved()
        self._remember(path)
        self.status.showMessage(f"Saved {path}", 5000)
        self._update_status()

    def _on_changed(self):
        self._update_status()

    def _update_status(self):
        bits = []
        for name, rom in (("program", self.prog), ("sample", self.smpl)):
            if rom is None:
                bits.append(f"no {name} ROM")
                continue
            tag = "" if rom.is_known_dump else " (unrecognised dump)"
            star = " *modified" if rom.modified else ""
            bits.append(f"{name}: {Path(rom.path).name}{tag}{star}")
        if self.smpl is not None:
            bits.append(f"{self.smpl.free_bytes()} bytes free in sample ROM")
        self.status.showMessage("    ".join(bits))

    def closeEvent(self, event):
        dirty = [
            name
            for name, rom in (("program", self.prog), ("sample", self.smpl))
            if rom is not None and rom.modified
        ]
        if dirty:
            answer = QtWidgets.QMessageBox.question(
                self,
                "Unsaved changes",
                f"The {' and '.join(dirty)} ROM has unsaved changes. Quit anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if answer != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
        event.accept()

    def _about(self):
        QtWidgets.QMessageBox.about(
            self,
            "TG100 ROM editor",
            f"<p><b>TG100 ROM editor {__version__}</b></p>"
            "<p>Reads and writes the Yamaha TG100's program and sample ROMs.</p>"
            "<p>ROM layout worked out from TaleTN's TG101 engine and "
            "vampirefrog's TG100 notes, then checked against the v1.10 dump.</p>"
            "<p>No ROM data ships with this program.</p>",
        )


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    app = QtWidgets.QApplication(argv)
    app.setStyleSheet(DARK)

    win = MainWindow()

    # anything passed on the command line is loaded by size
    for arg in argv[1:]:
        p = Path(arg)
        if not p.is_file():
            continue
        size = p.stat().st_size
        if size == layout.PROG_ROM_SIZE:
            win.open_program(str(p))
        elif size == layout.SMPL_ROM_SIZE:
            win.open_sample(str(p))

    win.show()
    return app.exec()
