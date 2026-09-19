"""Your own names for waves, kept beside the ROM rather than inside it.

The sample ROM has no text in it, so every name the editor shows is worked out
from which voices use a wave. That guess is wrong often enough to be annoying:
41 of the 140 wave numbers are only ever heard as a layer, so nothing in the
ROM says what the recording actually is. If you listen to one and recognise it,
write that down here and it sticks.

Labels live in a small JSON file next to the ROM, called after it, so the ROM
itself stays byte for byte what the hardware expects.
"""

import json
from pathlib import Path

SUFFIX = ".labels.json"
VERSION = 1


class Labels:
    """Custom names keyed by wave index. Missing keys fall back to the guess."""

    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self._names = {}
        self._notes = {}
        self._dirty = False

    @classmethod
    def sidecar_for(cls, rom_path):
        return Path(str(rom_path) + SUFFIX)

    @classmethod
    def load_for(cls, rom_path):
        """Read the sidecar beside a ROM. A missing or broken file is empty."""
        labels = cls(cls.sidecar_for(rom_path))
        try:
            raw = json.loads(labels.path.read_text())
        except (OSError, ValueError):
            return labels
        if not isinstance(raw, dict):
            return labels
        for key, value in (raw.get("names") or {}).items():
            try:
                labels._names[int(key)] = str(value)
            except (TypeError, ValueError):
                continue
        for key, value in (raw.get("notes") or {}).items():
            try:
                labels._notes[int(key)] = str(value)
            except (TypeError, ValueError):
                continue
        return labels

    def name(self, index):
        return self._names.get(index, "")

    def note(self, index):
        return self._notes.get(index, "")

    def set_name(self, index, text):
        text = (text or "").strip()
        if text:
            self._names[index] = text
        else:
            self._names.pop(index, None)
        self._dirty = True

    def set_note(self, index, text):
        text = (text or "").strip()
        if text:
            self._notes[index] = text
        else:
            self._notes.pop(index, None)
        self._dirty = True

    def has(self, index):
        return index in self._names

    def __len__(self):
        return len(self._names)

    @property
    def dirty(self):
        return self._dirty

    def save(self, path=None):
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("no path to save labels to")
        if not self._names and not self._notes:
            # nothing worth keeping, so do not leave an empty file lying around
            try:
                target.unlink()
            except OSError:
                pass
            self._dirty = False
            return None
        payload = {
            "version": VERSION,
            "names": {str(k): v for k, v in sorted(self._names.items())},
            "notes": {str(k): v for k, v in sorted(self._notes.items())},
        }
        target.write_text(json.dumps(payload, indent=2) + "\n")
        self.path = target
        self._dirty = False
        return target
