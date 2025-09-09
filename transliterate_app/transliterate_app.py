# pip install PySide6
# Run: python tp_transcriber.py
# Put one or more CSVs next to this file named like: lang_*.csv

import sys
import csv
from io import StringIO
from pathlib import Path
from collections import OrderedDict

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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

PUNCT = set(";:.,?!")  # trailing-word punctuation treated as standalone tokens


def parse_csv(text):
    rows = list(csv.reader(StringIO(text)))
    header = [h.strip() for h in rows[0]]
    data_rows = [[c.strip() for c in r] for r in rows[1:] if any(c.strip() for c in r)]
    return header, data_rows


def build_index_maps(header, rows):
    forward = {name: {} for name in header}
    for r in rows:
        for i_from, lang_from in enumerate(header):
            src = r[i_from]
            if not src:
                continue
            d = forward[lang_from].setdefault(src, {})
            for i_to, lang_to in enumerate(header):
                d[lang_to] = r[i_to]
    return forward


def space_free_columns(header, rows):
    sf = set()
    for j, name in enumerate(header):
        all_single = True
        for r in rows:
            cell = r[j]
            if cell and len(cell) != 1:
                all_single = False
                break
        if all_single:
            sf.add(name)
    return sf


def load_language_sets():
    sets = OrderedDict()
    files = sorted(Path(".").glob("lang_*.csv"), key=lambda p: p.name.lower())
    if not files:
        raise FileNotFoundError(
            "No language CSVs found. Add files named like 'lang_*.csv' with a header row."
        )
    for f in files:
        text = f.read_text(encoding="utf-8").strip()
        if not text:
            continue
        header = text.splitlines()[0].strip()
        sets[header] = text
    return sets


def split_trailing_punct(token):
    if not token or (token.startswith("[") and token.endswith("]")):
        return [token] if token else []
    i = len(token)
    while i > 0 and token[i - 1] in PUNCT:
        i -= 1
    head, tail = token[:i], token[i:]
    out = []
    if head:
        out.append(head)
    out.extend(list(tail))  # each punct char becomes its own token
    return out


class FocusAwareText(QTextEdit):
    def __init__(self):
        super().__init__()
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
        self.setWindowTitle("Transcriber")
        self.setMinimumSize(1280, 720)
        self.setLayout(QVBoxLayout())

        font = QFont()
        font.setPointSize(18)
        self.language_sets = load_language_sets()

        top = QHBoxLayout()
        self.layout().addLayout(top)
        top.addWidget(QLabel("language set:"))

        self.set_combo = QComboBox()
        for name in self.language_sets.keys():
            self.set_combo.addItem(name)
        top.addWidget(self.set_combo)

        langs_row = QHBoxLayout()
        self.layout().addLayout(langs_row)
        self.left_lang = QComboBox()
        self.right_lang = QComboBox()
        langs_row.addWidget(self.left_lang)
        langs_row.addWidget(self.right_lang)

        edits = QHBoxLayout()
        self.layout().addLayout(edits)
        self.left_edit = FocusAwareText()
        self.right_edit = FocusAwareText()
        self.left_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.right_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        edits.addWidget(self.left_edit)
        edits.addWidget(self.right_edit)

        self.left_edit.setFont(font)
        self.right_edit.setFont(font)
        self.left_lang.setFont(font)
        self.right_lang.setFont(font)
        self.set_combo.setFont(font)

        self.header = []
        self.rows = []
        self.forward = {}
        self.space_free = set()
        self.display_to_real = {}
        self.updating = False

        self.set_combo.currentTextChanged.connect(self._on_change_set)
        self.left_lang.currentTextChanged.connect(self._on_change_left_lang)
        self.right_lang.currentTextChanged.connect(self._on_change_right_lang)
        self.left_edit.textChanged.connect(lambda: self._on_text_changed("left"))
        self.right_edit.textChanged.connect(lambda: self._on_text_changed("right"))
        self.left_edit.focusOutEvent = self._wrap_focus_out(self.left_edit, "left")
        self.right_edit.focusOutEvent = self._wrap_focus_out(self.right_edit, "right")

        # Initialize from the FIRST found CSV (no hardcoding)
        first_set_name = next(iter(self.language_sets.keys()))
        self.set_combo.setCurrentText(first_set_name)
        self._on_change_set(first_set_name)

        # Default left/right languages: use first two columns if present
        if len(self.header) >= 1:
            self.left_lang.setCurrentText(self._label_for(self.header[0]))
        if len(self.header) >= 2:
            self.right_lang.setCurrentText(self._label_for(self.header[1]))

        self.left_edit.setPlainText("mi sona e ni.")
        self._translate_fill("left")

    def _wrap_focus_out(self, widget, side):
        base = widget.focusOutEvent

        def handler(e):
            self._commit_brackets(side)
            base(e)

        return handler

    def _commit_brackets(self, side):
        if self.updating:
            return
        self.updating = True
        try:
            edit = self.left_edit if side == "left" else self.right_edit
            lang = self._real_lang(self.left_lang) if side == "left" else self._real_lang(self.right_lang)
            tokens = self._tokens(edit.toPlainText(), lang)
            committed = []
            for tok in tokens:
                if tok in PUNCT:
                    committed.append(tok)
                elif tok.startswith("[") and tok.endswith("]"):
                    committed.append(tok)
                else:
                    if not self._has_exact_mapping(lang, tok):
                        committed.append(f"[{tok}]")
                    else:
                        committed.append(tok)
            new_text = self._join(committed, lang)
            if new_text != edit.toPlainText():
                cursor_pos = edit.textCursor().position()
                edit.setPlainText(new_text)
                c = edit.textCursor()
                c.setPosition(min(cursor_pos, len(new_text)))
                edit.setTextCursor(c)
            self._translate_fill(side)
        finally:
            self.updating = False

    def _on_text_changed(self, side):
        if self.updating:
            return
        self._translate_fill(src_side=side)

    def _translate_fill(self, src_side):
        self.updating = True
        try:
            src_edit = self.left_edit if src_side == "left" else self.right_edit
            dst_edit = self.right_edit if src_side == "left" else self.left_edit
            src_lang = self._real_lang(self.left_lang) if src_side == "left" else self._real_lang(self.right_lang)
            dst_lang = self._real_lang(self.right_lang) if src_side == "left" else self._real_lang(self.left_lang)

            src_text = src_edit.toPlainText()
            src_tokens = self._tokens(src_text, src_lang)

            src_is_typing = src_edit.hasEditingFocus()
            at_end = src_edit.textCursor().position() == len(src_text)

            dst_tokens = []
            for i, tok in enumerate(src_tokens):
                is_last = i == len(src_tokens) - 1

                if tok in PUNCT:
                    dst_tokens.append(tok)
                    continue
                if tok.startswith("[") and tok.endswith("]"):
                    inside = tok[1:-1]
                    mapped = self._map_exact(src_lang, dst_lang, inside)
                    dst_tokens.append(mapped if mapped is not None else f"[{inside}]")
                    continue

                mapped = self._map_exact(src_lang, dst_lang, tok)
                if mapped is not None:
                    dst_tokens.append(mapped)
                    continue

                if src_is_typing and is_last and at_end:
                    dst_tokens.append(f"[{tok}]")
                else:
                    dst_tokens.append(f"[{tok}]")

            new_dst = self._join(dst_tokens, dst_lang)
            if new_dst != dst_edit.toPlainText():
                cursor = dst_edit.textCursor()
                dst_edit.setPlainText(new_dst)
                if not dst_edit.hasEditingFocus():
                    dst_edit.setTextCursor(cursor)
        finally:
            self.updating = False

    def _on_change_set(self, set_name):
        csv_text = self.language_sets[set_name]
        self.header, self.rows = parse_csv(csv_text)
        self.forward = build_index_maps(self.header, self.rows)
        self.space_free = space_free_columns(self.header, self.rows)

        self.display_to_real = {}
        labels = [self._label_for(h) for h in self.header]
        for disp, real in zip(labels, self.header):
            self.display_to_real[disp] = real

        self.left_lang.blockSignals(True)
        self.right_lang.blockSignals(True)
        self.left_lang.clear()
        self.right_lang.clear()
        for disp in labels:
            self.left_lang.addItem(disp)
            self.right_lang.addItem(disp)
        self.left_lang.blockSignals(False)
        self.right_lang.blockSignals(False)

    def _on_change_left_lang(self, _):
        self._translate_fill("left")

    def _on_change_right_lang(self, _):
        self._translate_fill("left")

    def _label_for(self, real_name):
        return f"{real_name} (space-free)" if real_name in self.space_free else real_name

    def _real_lang(self, combo):
        disp = combo.currentText()
        return self.display_to_real.get(disp, disp)

    def _map_exact(self, src_lang, dst_lang, token):
        if token in PUNCT:
            return token
        entry = self.forward.get(src_lang, {}).get(token)
        if not entry:
            return None
        return entry.get(dst_lang)

    def _has_exact_mapping(self, lang, token):
        if token in PUNCT:
            return True
        return token in self.forward.get(lang, {})

    def _tokens(self, text, lang):
        if lang in self.space_free:
            return self._tokens_space_free(text)
        return self._tokens_ws(text)

    @staticmethod
    def _tokens_ws(text):
        if not text.strip():
            return []
        raw = text.strip().split()
        out = []
        for tok in raw:
            out.extend(split_trailing_punct(tok))
        return out

    @staticmethod
    def _tokens_space_free(text):
        out = []
        i = 0
        n = len(text)
        while i < n:
            c = text[i]
            if c == "[":
                j = text.find("]", i + 1)
                if j == -1:
                    out.append(text[i:])  # incomplete bracket blob
                    break
                out.append(text[i : j + 1])
                i = j + 1
                continue
            if "\u4e00" <= c <= "\u9fff":  # CJK Unified Ideographs
                out.append(c)
                i += 1
                continue
            # collect a run of non-CJK, non-bracket
            j = i
            while j < n:
                cj = text[j]
                if cj == "[" or ("\u4e00" <= cj <= "\u9fff"):
                    break
                j += 1
            out.append(text[i:j])
            i = j
        # drop empty tokens introduced by adjacency
        return [t for t in out if t != ""]

    def _join(self, tokens, lang):
        if lang in self.space_free:
            return "".join(tokens)
        pieces = []
        for idx, tok in enumerate(tokens):
            if tok in PUNCT:
                pieces.append(tok)
                if idx != len(tokens) - 1:
                    pieces.append(" ")
            else:
                if pieces and not pieces[-1].endswith(" "):
                    pieces.append(" ")
                pieces.append(tok)
        return "".join(pieces).strip()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Transcriber()
    w.show()
    sys.exit(app.exec())
