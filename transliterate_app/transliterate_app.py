# pip install PySide6
# Put one or more CSVs next to this file named like: lang_*.csv

import sys
import csv
from io import StringIO
from pathlib import Path
from collections import OrderedDict

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
    QPushButton,
    QMessageBox,
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

    def has_editing_focus(self):
        return self._has_focus


class Transcriber(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transcriber")
        self.setMinimumSize(1280, 720)
        self.setLayout(QVBoxLayout())

        self.font = QFont()
        self.font.setPointSize(18)
        self.language_sets = load_language_sets()

        # Top bar: language set selector + (+) add button
        top = QHBoxLayout()
        self.layout().addLayout(top)
        self.lang_set_label = QLabel("language set:")
        top.addWidget(self.lang_set_label)
        self.lang_set_label.setFont(self.font)
        self.set_combo = QComboBox()
        self.set_combo.setFont(self.font)
        for name in self.language_sets.keys():
            self.set_combo.addItem(name)
        top.addWidget(self.set_combo)
        self.add_btn = QPushButton("(+)")
        self.add_btn.setFixedWidth(48)
        self.add_btn.setFont(self.font)
        top.addWidget(self.add_btn)

        # Dynamic panes container
        self.panes_row = QHBoxLayout()
        self.layout().addLayout(self.panes_row)

        self.header = []
        self.rows = []
        self.forward = {}
        self.space_free = set()
        self.display_to_real = {}
        self.labels = []
        self.updating = False
        self.panes = []  # list of dicts: {lang_combo, close_btn, edit, layout}

        self.set_combo.currentTextChanged.connect(self._on_change_set)
        self.add_btn.clicked.connect(self._on_add_pane)

        # Initialize from FIRST CSV, then create two panes
        first_set_name = next(iter(self.language_sets.keys()))
        self.set_combo.setCurrentText(first_set_name)
        self._on_change_set(first_set_name)

        # Default: 2 panes
        self._on_add_pane()
        self._on_add_pane()
        # Seed text in first pane
        if self.panes:
            self.panes[0]["edit"].setPlainText("mi sona e ni.")

    # ---- NEW: robust layout clear to avoid half-removed panes ----
    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
                continue
            child_layout = item.layout()
            if child_layout is not None:
                self._clear_layout(child_layout)
                child_layout.deleteLater()

    def _on_add_pane(self):
        if len(self.panes) >= len(self.labels):
            QMessageBox.information(self, "Limit", "No more languages available.")
            return
        # Choose first label not used yet
        used = {p["lang_combo"].currentText() for p in self.panes}
        chosen_label = None
        for lab in self.labels:
            if lab not in used:
                chosen_label = lab
                break
        if chosen_label is None:
            chosen_label = self.labels[0]
        # Build pane widgets
        col = QVBoxLayout()
        head = QHBoxLayout()
        lang_combo = QComboBox()
        for lab in self.labels:
            lang_combo.addItem(lab)
        lang_combo.setCurrentText(chosen_label)
        close_btn = QPushButton("X")
        close_btn.setFixedWidth(28)
        head.addWidget(lang_combo)
        head.addWidget(close_btn)

        edit = FocusAwareText()
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        lang_combo.setFont(self.font)
        close_btn.setFont(self.font)
        edit.setFont(self.font)

        col.addLayout(head)
        col.addWidget(edit)
        pane = {"layout": col, "lang_combo": lang_combo, "close_btn": close_btn, "edit": edit}
        self.panes_row.addLayout(col)
        self.panes.append(pane)

        # Wire signals (bind pane at connect-time to avoid late-binding issues)
        lang_combo.currentTextChanged.connect(lambda _, p=pane: self._on_pane_lang_changed(p))
        close_btn.clicked.connect(lambda _, p=pane: self._close_pane(p))
        edit.textChanged.connect(lambda p=pane: self._on_text_changed(p))
        edit.focusOutEvent = self._wrap_focus_out(edit, pane)

        # Autofill contents from an existing source pane if present
        if len(self.panes) > 1:
            src = self._best_source_pane()
            if src:
                self._translate_from_source(src)

    def _close_pane(self, pane):
        if len(self.panes) <= 1:
            return  # keep at least one
        if pane not in self.panes:
            return  # already closed or stale signal

        layout = pane["layout"]
        # Remove from tracking first to prevent re-entrancy issues
        self.panes.remove(pane)

        # Clean up UI objects safely
        self._clear_layout(layout)
        self.panes_row.removeItem(layout)
        layout.deleteLater()

        # Retranslate remaining panes
        src = self._best_source_pane()
        if src:
            self._translate_from_source(src)

    def _best_source_pane(self):
        for p in self.panes:
            if p["edit"].has_editing_focus():
                return p
        for p in self.panes:
            if p["edit"].toPlainText().strip():
                return p
        return self.panes[0] if self.panes else None

    # -------- Data / languages --------

    def _on_change_set(self, set_name):
        csv_text = self.language_sets[set_name]
        self.header, self.rows = parse_csv(csv_text)
        self.forward = build_index_maps(self.header, self.rows)
        self.space_free = space_free_columns(self.header, self.rows)
        self.display_to_real = {}
        self.labels = [self._label_for(h) for h in self.header]
        for disp, real in zip(self.labels, self.header):
            self.display_to_real[disp] = real

        for p in self.panes:
            current = p["lang_combo"].currentText() if p["lang_combo"].count() else None
            p["lang_combo"].blockSignals(True)
            p["lang_combo"].clear()
            for lab in self.labels:
                p["lang_combo"].addItem(lab)
            if current in self.labels:
                p["lang_combo"].setCurrentText(current)
            else:
                used = {q["lang_combo"].currentText() for q in self.panes if q is not p}
                pick = next((lab for lab in self.labels if lab not in used), self.labels[0])
                p["lang_combo"].setCurrentText(pick)
            p["lang_combo"].blockSignals(False)

        src = self._best_source_pane()
        if src:
            self._translate_from_source(src)

    # -------- Translation flow --------

    def _on_pane_lang_changed(self, src_pane):
        self._translate_from_source(src_pane)

    def _on_text_changed(self, src_pane):
        if self.updating:
            return
        self._translate_from_source(src_pane)

    def _wrap_focus_out(self, widget, pane):
        base = widget.focusOutEvent

        def handler(e):
            self._commit_brackets(pane)
            base(e)

        return handler

    def _commit_brackets(self, pane):
        if self.updating:
            return
        self.updating = True
        try:
            edit = pane["edit"]
            lang = self._real_lang_of_pane(pane)
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
            self._translate_from_source(pane)
        finally:
            self.updating = False

    def _translate_from_source(self, src_pane):
        self.updating = True
        try:
            src_edit = src_pane["edit"]
            src_lang = self._real_lang_of_pane(src_pane)
            src_text = src_edit.toPlainText()
            src_tokens = self._tokens(src_text, src_lang)
            src_is_typing = src_edit.has_editing_focus()
            at_end = src_edit.textCursor().position() == len(src_text)

            for pane in list(self.panes):  # iterate over a snapshot
                if pane is src_pane:
                    continue
                dst_edit = pane["edit"]
                dst_lang = self._real_lang_of_pane(pane)

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
                    if not dst_edit.has_editing_focus():
                        dst_edit.setTextCursor(cursor)
        finally:
            self.updating = False

    # -------- Mapping + tokenization --------

    def _label_for(self, real_name):
        return (
            f"{real_name} (space-free)" if real_name in self.space_free else real_name
        )

    def _real_lang_of_pane(self, pane):
        disp = pane["lang_combo"].currentText()
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
            chunk = text[i:j]
            if chunk:
                out.extend(split_trailing_punct(chunk))
            i = j
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
