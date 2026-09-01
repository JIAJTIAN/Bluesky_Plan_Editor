from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from plan_editor.canvas.node import BaseNode


class PropertiesPanel(QWidget):
    param_changed = Signal(str, object)  # (param_name, value)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(210)
        self.setStyleSheet("background: #0d1117; border-left: 1px solid #1e2535;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        self._header = QLabel("Properties")
        self._header.setStyleSheet("color: #64748b; font-size: 10px; letter-spacing: 2px;")
        outer.addWidget(self._header)

        self._desc = QLabel("")
        self._desc.setWordWrap(True)
        self._desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._desc.setStyleSheet(
            "color: #475569; font-size: 10px; font-style: italic;"
            "background: #111827; border: 1px solid #1e2535; border-radius: 4px;"
            "padding: 5px 7px; margin-bottom: 2px;"
        )
        self._desc.setVisible(False)
        outer.addWidget(self._desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        outer.addWidget(scroll)

        self._inner = QWidget()
        self._form = QFormLayout(self._inner)
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setSpacing(6)
        scroll.setWidget(self._inner)

        self._node: BaseNode | None = None
        self._editors: dict[str, QLineEdit] = {}

    def show_node(self, node: BaseNode | None):
        self._node = node
        self._editors.clear()
        while self._form.rowCount():
            self._form.removeRow(0)

        if node is None:
            self._header.setText("Properties")
            self._desc.setVisible(False)
            return

        self._header.setText(f"Properties — {node.schema.title}")

        desc = getattr(node.schema, "desc", "")
        if desc:
            self._desc.setText(desc)
            self._desc.setVisible(True)
        else:
            self._desc.setVisible(False)

        label_style = "color: #64748b; font-size: 11px;"
        edit_style = (
            "background: #141922; border: 1px solid #1e2535; border-radius: 4px;"
            "color: #7dd3fc; font-size: 11px; padding: 2px 6px;"
        )

        for key, val in node.params.items():
            lbl = QLabel(key)
            lbl.setStyleSheet(label_style)
            ed = QLineEdit(str(val))
            ed.setStyleSheet(edit_style)
            ed.editingFinished.connect(self._make_commit(key, ed))
            self._form.addRow(lbl, ed)
            self._editors[key] = ed

    def _make_commit(self, key: str, editor: QLineEdit):
        def commit():
            if self._node is None:
                return
            raw = editor.text()
            try:
                val = float(raw) if ("." in raw or "e" in raw.lower()) else int(raw)
            except ValueError:
                val = raw
            self._node.params[key] = val
            self.param_changed.emit(key, val)
        return commit
