"""Shift+A floating node-search popup."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QFrame, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout,
)

from plan_editor.registry.builtin_plans import BUILTIN_NODES
from plan_editor.registry.schema import NodeSchema
from plan_editor.ui.category_style import color, icon


class NodeSearchPopup(QFrame):
    """Floating Shift+A search popup — parent must be the NodeView widget."""

    node_chosen = Signal(NodeSchema)

    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setStyleSheet(
            "QFrame { background:#141922; border:1px solid #334155; border-radius:6px; }"
        )
        self.setWindowFlags(Qt.Popup)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        lbl = QLabel("Add Node")
        lbl.setStyleSheet("color:#64748b; font-size:10px; letter-spacing:1.5px;")
        layout.addWidget(lbl)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setStyleSheet(
            "background:#0f1117; border:1px solid #334155; border-radius:4px;"
            "color:#e2e8f0; font-size:12px; padding:4px 8px;"
        )
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setFixedHeight(240)
        self._list.setStyleSheet(
            "QListWidget{background:transparent;border:none;outline:none;}"
            "QListWidget::item{color:#94a3b8;font-size:11px;padding:4px 6px;border-radius:4px;}"
            "QListWidget::item:hover{background:#1e2535;color:#e2e8f0;}"
            "QListWidget::item:selected{background:#1e3a5f;color:#7dd3fc;}"
        )
        self._list.itemActivated.connect(self._on_activate)
        layout.addWidget(self._list)

        # exclude hidden nodes (e.g. loop_var — auto-created by zip loop frame)
        self._schemas: list[NodeSchema] = [s for s in BUILTIN_NODES if not s.hidden]
        self._populate(self._schemas)

    def showEvent(self, event):
        super().showEvent(event)
        self._search.clear()
        self._search.setFocus()

    # ── list management ───────────────────────────────────────────────────────
    def _populate(self, schemas: list[NodeSchema]):
        self._list.clear()
        for s in schemas:
            item = QListWidgetItem(f"{icon(s.category)}  {s.title}")
            item.setData(Qt.UserRole, s)
            item.setForeground(QColor(color(s.category)))
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _filter(self, text: str):
        q = text.lower()
        self._populate([
            s for s in self._schemas
            if q in s.title.lower() or q in s.category.lower()
        ])

    # ── keyboard navigation ───────────────────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key_Escape:
            self.close()
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            self._confirm()
        elif key == Qt.Key_Down:
            self._list.setCurrentRow(min(self._list.currentRow() + 1, self._list.count() - 1))
        elif key == Qt.Key_Up:
            self._list.setCurrentRow(max(self._list.currentRow() - 1, 0))
        else:
            super().keyPressEvent(event)

    def _on_activate(self, _item: QListWidgetItem):
        self._confirm()

    def _confirm(self):
        item = self._list.currentItem()
        if item:
            schema = item.data(Qt.UserRole)
            if schema:
                self.node_chosen.emit(schema)
        self.close()
