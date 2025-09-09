# pip install PySide6
# Run: python tp_transcriber.py

import sys
import csv
from io import StringIO

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QTextEdit,
    QSizePolicy,
)

# "sitelen kanpun" demo lexicon (toki pona, 漢字, english).
# Note: community conventions differ; this is a minimal working sample.
CSV_DATA = """
toki pona,漢字,english
mi,我,I
sina,你,you
ona,他,they
ni,這,this
e,額,(object marker)
sona,知,know
pali,工,work/do
toki,言,speak
pona,善,good
jan,人,person
moku,食,eat/food
tomo,宅,house
suli,大,big
lili,小,small
wawa,力,power
suno,日,sun
telo,水,water
"""
# The dropdown "language set" (future-proofing for multiple sets)
LANGUAGE_SETS = {
    "toki pona, 漢字": CSV_DATA.strip(),
}


def parse_csv(text):
    rows = list(csv.reader(StringIO(text)))
    header = [h.strip() for h in rows[0]]
    data_rows = [[c.strip() for c in r] for r in rows[1:] if any(c.strip() for c in r)]
    return header, data_rows


def build_column_indexes(header):
    return {name: i for i, name in enumerate(header)}


def build_index_maps(header, rows):
    """
    Returns per-language forward maps and reverse index:
      forward[lang] = {word_in_lang: {lang2: word_in_lang2, ...}}
    """
    forward = {name: {} for name in header}
    for r in rows:
        for i_from, lang_from in enumerate(header):
            src = r[i_from]
            if not src:
                continue
            d = forward[lang_from].setdefault(src, {})
            for i_to, lang_to in enumerate(header):
                if i_to == i_from:
                    continue
                d[lang_to] = r[i_to]
    return forward


class FocusAwareText(QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._has_focus = False

    def focusInEvent(self, e):
        self._has_focus = True
        super().focusInEvent(e)

    def focusOutEvent(self, e):
        self._has_focus = False
        super().focusOutEvent(e)

    def hasEditingFocus(self):
        return self._has_focus


class Transcriber(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transcriber: toki pona ↔ 漢字 (demo)")
        self.setMinimumSize(820, 520)

        self.setLayout(QVBoxLayout())

        # Language set selector
        top = QHBoxLayout()
        self.layout().addLayout(top)
        top.addWidget(QLabel("language set:"))

        self.set_combo = QComboBox()
        for k in LANGUAGE_SETS:
            self.set_combo.addItem(k)
        top.addWidget(self.set_combo)

        # Per-side language selectors
        langs_row = QHBoxLayout()
        self.layout().addLayout(langs_row)

        self.left_lang = QComboBox()
        self.right_lang = QComboBox()
        langs_row.addWidget(self.left_lang)
        langs_row.addWidget(self.right_lang)

        # Editors
        edits = QHBoxLayout()
        self.layout().addLayout(edits)

        self.left_edit = FocusAwareText()
        self.right_edit = FocusAwareText()
        self.left_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.right_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        edits.addWidget(self.left_edit)
        edits.addWidget(self.right_edit)

        # State
        self.header = []
        self.rows = []
        self.forward = {}
        self.updating = False  # reentrancy guard

        # Wire signals
        self.set_combo.currentTextChanged.connect(self._on_change_set)
        self.left_lang.currentTextChanged.connect(self._on_change_left_lang)
        self.right_lang.currentTextChanged.connect(self._on_change_right_lang)
        self.left_edit.textChanged.connect(lambda: self._on_text_changed(side="left"))
        self.right_edit.textChanged.connect(lambda: self._on_text_changed(side="right"))
        self.left_edit.focusOutEvent = self._wrap_focus_out(self.left_edit, "left")
        self.right_edit.focusOutEvent = self._wrap_focus_out(self.right_edit, "right")

        # Initialize
        self._on_change_set(self.set_combo.currentText())
        # Defaults as in prompt
        if "toki pona" in self.header and "漢字" in self.header:
            self.left_lang.setCurrentText("toki pona")
            self.right_lang.setCurrentText("漢字")

        self.left_edit.setPlainText("mi sona e ni")
        # Trigger initial fill on right
        self._translate_fill(src_side="left")

    # --- Focus-out "commit" handling -------------------------------------

    def _wrap_focus_out(self, widget, side):
        base = widget.focusOutEvent

        def handler(e):
            # Commit bracketed unknowns: mirror brackets onto the editing side too
            self._commit_brackets(side)
            base(e)

        return handler

    def _commit_brackets(self, side):
        if self.updating:
            return
        self.updating = True
        try:
            edit = self.left_edit if side == "left" else self.right_edit
            text = edit.toPlainText()
            tokens = self._simple_tokens(text)
            committed = []
            for tok in tokens:
                if tok.startswith("[") and tok.endswith("]"):
                    committed.append(tok)  # already bracketed
                else:
                    # If tok is unmapped in this language, bracket it
                    lang = self.left_lang.currentText() if side == "left" else self.right_lang.currentText()
                    if not self._has_exact_mapping(lang, tok):
                        committed.append(f"[{tok}]")
                    else:
                        committed.append(tok)
            new_text = self._join_tokens(committed)
            if new_text != text:
                cursor_pos = edit.textCursor().position()
                edit.setPlainText(new_text)
                c = edit.textCursor()
                c.setPosition(min(cursor_pos, len(new_text)))
                edit.setTextCursor(c)

            # Reflect commit to the other side
            self._translate_fill(src_side=side)
        finally:
            self.updating = False

    # --- Core translation logic ------------------------------------------

    def _on_text_changed(self, side):
        if self.updating:
            return
        self._translate_fill(src_side=side)

    def _translate_fill(self, src_side):
        self.updating = True
        try:
            src_edit = self.left_edit if src_side == "left" else self.right_edit
            dst_edit = self.right_edit if src_side == "left" else self.left_edit
            src_lang = self.left_lang.currentText() if src_side == "left" else self.right_lang.currentText()
            dst_lang = self.right_lang.currentText() if src_side == "left" else self.left_lang.currentText()

            src_text = src_edit.toPlainText()
            src_tokens = self._simple_tokens(src_text)

            # Determine "typing" status to decide transient brackets.
            src_is_typing = src_edit.hasEditingFocus()
            at_end = src_edit.textCursor().position() == len(src_text)
            has_trailing_space = src_text.endswith(" ")

            dst_tokens = []
            for i, tok in enumerate(src_tokens):
                raw = tok.strip()
                is_last = i == len(src_tokens) - 1

                # Preserve already-bracketed placeholders symmetrically
                if raw.startswith("[") and raw.endswith("]"):
                    inside = raw[1:-1]
                    mapped = self._map_exact(src_lang, dst_lang, inside)
                    if mapped is None:
                        dst_tokens.append(f"[{inside}]")
                    else:
                        dst_tokens.append(mapped)
                    continue

                mapped = self._map_exact(src_lang, dst_lang, raw)
                if mapped is not None:
                    dst_tokens.append(mapped)
                    continue

                # Unknown token. If currently typing the last token with no trailing space,
                # show transient bracket on destination only if it could become a known word by completion,
                # otherwise still show bracket to mirror unknown.
                if src_is_typing and is_last and at_end and not has_trailing_space:
                    if self._has_prefix_candidate(src_lang, raw):
                        dst_tokens.append(f"[{raw}]")
                    else:
                        dst_tokens.append(f"[{raw}]")
                else:
                    # Not actively typing this token → keep bracket on destination
                    dst_tokens.append(f"[{raw}]")

            new_dst = self._join_tokens(dst_tokens)
            if new_dst != dst_edit.toPlainText():
                cursor = dst_edit.textCursor()
                dst_edit.setPlainText(new_dst)
                # Try not to steal user caret when they are the source
                if not dst_edit.hasEditingFocus():
                    dst_edit.setTextCursor(cursor)
        finally:
            self.updating = False

    def _on_change_set(self, set_name):
        csv_text = LANGUAGE_SETS[set_name]
        self.header, self.rows = parse_csv(csv_text)
        self.forward = build_index_maps(self.header, self.rows)

        # Refresh language dropdowns
        self.left_lang.blockSignals(True)
        self.right_lang.blockSignals(True)
        self.left_lang.clear()
        self.right_lang.clear()
        for name in self.header:
            self.left_lang.addItem(name)
            self.right_lang.addItem(name)
        self.left_lang.blockSignals(False)
        self.right_lang.blockSignals(False)

    def _on_change_left_lang(self, _):
        # Refill right from left text using new left language
        self._translate_fill(src_side="left")

    def _on_change_right_lang(self, _):
        # Refill right using the new right language
        self._translate_fill(src_side="left")

    # --- Mapping helpers --------------------------------------------------

    def _map_exact(self, src_lang, dst_lang, token):
        d = self.forward.get(src_lang, {})
        entry = d.get(token)
        if not entry:
            return None
        return entry.get(dst_lang)

    def _has_exact_mapping(self, lang, token):
        return token in self.forward.get(lang, {})

    def _has_prefix_candidate(self, lang, prefix):
        # True if any lexeme in `lang` starts with this prefix
        # Used to decide whether a bracket might disappear once typing finishes.
        d = self.forward.get(lang, {})
        for k in d.keys():
            if k.startswith(prefix):
                return True
        return False

    # --- Tokenization -----------------------------------------------------

    @staticmethod
    def _simple_tokens(text):
        # Split on whitespace but keep single spaces between tokens on join.
        # Normalize any sequence of whitespace to single spaces for stability.
        parts = text.strip().split()
        return parts

    @staticmethod
    def _join_tokens(tokens):
        return " ".join(tokens)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Transcriber()
    w.show()
    sys.exit(app.exec())
