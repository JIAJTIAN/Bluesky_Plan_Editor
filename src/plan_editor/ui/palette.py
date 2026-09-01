from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget,
)

from plan_editor.registry.builtin_plans import BUILTIN_NODES
from plan_editor.registry.schema import NodeSchema
from plan_editor.ui.category_style import color, icon


class NodePalette(QWidget):
    node_double_clicked = Signal(NodeSchema)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(190)
        self.setStyleSheet("background: #0d1117; border-right: 1px solid #1e2535;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QLabel("Node Library")
        header.setStyleSheet(
            "color: #64748b; font-size: 10px; text-transform: uppercase; letter-spacing: 2px;"
        )
        layout.addWidget(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setStyleSheet(
            "background:#141922; border:1px solid #1e2535; border-radius:4px;"
            "color:#e2e8f0; padding:4px 6px; font-size:11px;"
        )
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background: transparent; border: none; }"
            "QListWidget::item { color: #94a3b8; font-size: 11px; padding: 4px 6px; border-radius: 4px; }"
            "QListWidget::item:hover { background: #1e2535; color: #e2e8f0; }"
            "QListWidget::item:selected { background: #1e3a5f; color: #7dd3fc; }"
        )
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        self._schemas: list[NodeSchema] = [s for s in BUILTIN_NODES if not s.hidden]
        self._populate(self._schemas)

    def _populate(self, schemas: list[NodeSchema]):
        self._list.clear()
        for schema in schemas:
            item = QListWidgetItem(f"{icon(schema.category)}  {schema.title}")
            item.setData(Qt.UserRole, schema)
            item.setForeground(QColor(color(schema.category)))
            self._list.addItem(item)

    def _filter(self, text: str):
        filtered = [s for s in self._schemas if text.lower() in s.title.lower()]
        self._populate(filtered)

    def _on_double_click(self, item: QListWidgetItem):
        schema = item.data(Qt.UserRole)
        if schema:
            self.node_double_clicked.emit(schema)
