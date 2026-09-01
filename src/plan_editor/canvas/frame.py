"""Frame node — visual grouping rectangle behind a set of nodes."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsTextItem

_FRAME_COLORS = [
    ("#1a2035", "#3b5280"),  # blue
    ("#1a2a1a", "#3b6e3b"),  # green
    ("#2a1a0a", "#7a4a10"),  # amber
    ("#2a1a2a", "#6a2a6a"),  # purple
]
_color_index = 0

_LABEL_FONT = QFont("Segoe UI", 9)
_LABEL_FONT.setBold(True)


class FrameNode(QGraphicsItem):
    """A labeled rectangle that sits behind selected nodes."""

    def __init__(self, rect: QRectF, label: str = "Frame"):
        super().__init__()
        global _color_index
        self._bg, self._border = [QColor(c) for c in _FRAME_COLORS[_color_index % len(_FRAME_COLORS)]]
        _color_index += 1

        self.setFlag(QGraphicsItem.ItemIsMovable,    True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(-1)   # behind all nodes

        # position item at rect top-left, keep rect local
        self.setPos(rect.topLeft())
        self._rect = QRectF(0, 0, rect.width(), rect.height())

        # editable label
        self._label = QGraphicsTextItem(label, self)
        self._label.setFont(_LABEL_FONT)
        self._label.setDefaultTextColor(QColor(self._border).lighter(150))
        self._label.setPos(8, 4)
        self._label.setTextInteractionFlags(Qt.TextEditorInteraction)

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-2, -2, 2, 2)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        selected = self.isSelected()
        border   = self._border.lighter(130) if selected else self._border

        painter.setBrush(QBrush(self._bg))
        painter.setPen(QPen(border, 1.5 if selected else 1, Qt.DashLine))
        painter.drawRoundedRect(self._rect, 8, 8)

    def resize_to_nodes(self, nodes: list):
        """Expand rect to snugly contain all given nodes (with padding)."""
        if not nodes:
            return
        pad = 20
        united = nodes[0].mapToScene(nodes[0].boundingRect()).boundingRect()
        for n in nodes[1:]:
            united = united.united(n.mapToScene(n.boundingRect()).boundingRect())
        new_rect = united.adjusted(-pad, -pad - 8, pad, pad)
        self.prepareGeometryChange()
        self.setPos(new_rect.topLeft())
        self._rect = QRectF(0, 0, new_rect.width(), new_rect.height())
        self.update()
