from __future__ import annotations
from enum import Enum, auto
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem

if TYPE_CHECKING:
    from .node import BaseNode
    from .wire import Wire

PORT_R = 7
PORT_COLORS = {"plan": "#a855f7", "value": "#fbbf24", "any": "#64748b"}
_PLAN_COLOR  = QColor("#a855f7")
_VALUE_COLOR = QColor("#fbbf24")   # amber for value/data ports
_HOVER_COLOR = QColor("#e2e8f0")
_BODY_COLOR  = QColor("#1a1f2e")


class PortKind(Enum):
    INPUT  = auto()
    OUTPUT = auto()


class Port(QGraphicsItem):
    def __init__(self, node: BaseNode, name: str, port_type: str, kind: PortKind, index: int):
        super().__init__()
        self.node      = node
        self.name      = name
        self.port_type = port_type
        self.kind      = kind
        self.index     = index
        self.wires: list[Wire] = []
        self._hovered  = False

        self.setAcceptHoverEvents(True)
        self.setZValue(2)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)

    def boundingRect(self) -> QRectF:
        r = PORT_R + 3
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        filled = len(self.wires) > 0
        hover  = self._hovered
        is_val = self.port_type == "value"

        port_color = _VALUE_COLOR if is_val else _PLAN_COLOR
        ring_filled = QColor("#7a5500") if is_val else QColor("#4a1a7a")
        ring = _HOVER_COLOR if hover else (ring_filled if filled else QColor("#2e3a50"))
        fill = port_color if (filled or hover) else _BODY_COLOR

        painter.setPen(QPen(ring, 1.5))
        painter.setBrush(fill)
        if is_val:
            r = PORT_R - 1
            diamond = QPolygonF([
                QPointF(0, -r), QPointF(r, 0), QPointF(0, r), QPointF(-r, 0)
            ])
            painter.drawPolygon(diamond)
        else:
            painter.drawEllipse(QPointF(0, 0), PORT_R, PORT_R)

    def scene_pos(self) -> QPointF:
        return self.mapToScene(QPointF(0, 0))

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def notify_wires(self):
        for w in self.wires:
            w.update_path()

    def on_connection_changed(self):
        self.update()
        self.node.update_widgets()
