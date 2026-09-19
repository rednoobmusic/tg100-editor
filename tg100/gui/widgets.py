"""Small widgets that read and write a ROM record directly.

Each one owns a getter and a setter rather than a copy of the value, so there
is no separate model to keep in sync and no apply button. Changing a spin box
changes the ROM byte, which is what you want in a ROM editor.
"""

from PySide6 import QtCore, QtWidgets


class Bound(QtCore.QObject):
    """Base for a widget bound to one value in the ROM."""

    changed = QtCore.Signal()

    def __init__(self, getter, setter, parent=None):
        super().__init__(parent)
        self._get = getter
        self._set = setter
        self._loading = False

    def refresh(self):
        self._loading = True
        try:
            self._apply(self._get())
        finally:
            self._loading = False

    def _apply(self, value):
        raise NotImplementedError

    def _store(self, value):
        if self._loading:
            return
        self._set(value)
        self.changed.emit()


class BoundSpin(Bound):
    def __init__(self, getter, setter, lo, hi, describe=None, parent=None):
        super().__init__(getter, setter, parent)
        self.widget = QtWidgets.QSpinBox()
        self.widget.setRange(lo, hi)
        self.widget.setKeyboardTracking(False)
        self.widget.valueChanged.connect(self._store)
        self.describe = describe
        self.hint = QtWidgets.QLabel()
        self.hint.setStyleSheet("color: #8b93a5;")
        self.changed.connect(self._update_hint)

    def _apply(self, value):
        self.widget.setValue(int(value))
        self._update_hint()

    def _update_hint(self):
        if self.describe is not None:
            self.hint.setText(self.describe(self.widget.value()))

    def setEnabled(self, on):
        self.widget.setEnabled(on)
        self.hint.setEnabled(on)


class BoundSlider(Bound):
    """A slider with its value beside it, for anything continuous.

    Synth parameters are felt as positions on a range, not as numbers, so the
    slider is the control and the number is the readout. The spin box is still
    there for when you want to type an exact value.
    """

    def __init__(self, getter, setter, lo, hi, describe=None, parent=None):
        super().__init__(getter, setter, parent)
        self.widget = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(self.widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setMinimumWidth(90)
        self.slider.valueChanged.connect(self._from_slider)

        self.spin = QtWidgets.QSpinBox()
        self.spin.setRange(lo, hi)
        self.spin.setKeyboardTracking(False)
        self.spin.setMaximumWidth(64)
        self.spin.valueChanged.connect(self._from_spin)

        row.addWidget(self.slider, 1)
        row.addWidget(self.spin)

        self.describe = describe
        self.hint = QtWidgets.QLabel()
        self.hint.setStyleSheet("color: #8b93a5;")
        self.changed.connect(self._update_hint)

    def _from_slider(self, value):
        if self.spin.value() != value:
            self.spin.blockSignals(True)
            self.spin.setValue(value)
            self.spin.blockSignals(False)
        self._store(value)
        self._update_hint()

    def _from_spin(self, value):
        if self.slider.value() != value:
            self.slider.setValue(value)
        else:
            self._store(value)
            self._update_hint()

    def _apply(self, value):
        value = int(value)
        for w in (self.slider, self.spin):
            w.blockSignals(True)
            w.setValue(value)
            w.blockSignals(False)
        self._update_hint()

    def _update_hint(self):
        if self.describe is not None:
            self.hint.setText(self.describe(self.slider.value()))

    def setEnabled(self, on):
        self.widget.setEnabled(on)
        self.hint.setEnabled(on)


class BoundCombo(Bound):
    def __init__(self, getter, setter, items, parent=None):
        """items is a sequence of (value, label) pairs."""
        super().__init__(getter, setter, parent)
        self.widget = QtWidgets.QComboBox()
        for value, label in items:
            self.widget.addItem(label, value)
        self.widget.currentIndexChanged.connect(self._on_index)

    def _on_index(self, _):
        self._store(self.widget.currentData())

    def _apply(self, value):
        idx = self.widget.findData(int(value))
        self.widget.setCurrentIndex(idx if idx >= 0 else 0)

    def setEnabled(self, on):
        self.widget.setEnabled(on)


class BoundText(Bound):
    def __init__(self, getter, setter, max_len, parent=None):
        super().__init__(getter, setter, parent)
        self.widget = QtWidgets.QLineEdit()
        self.widget.setMaxLength(max_len)
        self.widget.editingFinished.connect(self._on_done)

    def _on_done(self):
        self._store(self.widget.text())

    def _apply(self, value):
        self.widget.setText(str(value))

    def setEnabled(self, on):
        self.widget.setEnabled(on)


class FieldGrid(QtWidgets.QWidget):
    """A two column grid of labelled bound widgets."""

    changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = QtWidgets.QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setVerticalSpacing(4)
        self.fields = []
        self._row = 0

    def add(self, label, bound, hint=True):
        self.grid.addWidget(QtWidgets.QLabel(label), self._row, 0)
        self.grid.addWidget(bound.widget, self._row, 1)
        if hint and isinstance(bound, (BoundSpin, BoundSlider)) and bound.describe is not None:
            self.grid.addWidget(bound.hint, self._row, 2)
        bound.changed.connect(self.changed)
        self.fields.append(bound)
        self._row += 1
        return bound

    def add_widget(self, label, widget):
        self.grid.addWidget(QtWidgets.QLabel(label), self._row, 0)
        self.grid.addWidget(widget, self._row, 1, 1, 2)
        self._row += 1
        return widget

    def stretch(self):
        self.grid.setColumnStretch(2, 1)
        self.grid.setRowStretch(self._row, 1)

    def refresh(self):
        for f in self.fields:
            f.refresh()

    def set_enabled(self, on):
        for f in self.fields:
            f.setEnabled(on)
