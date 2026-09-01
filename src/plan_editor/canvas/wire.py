from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsPathItem

from .port import PORT_COLORS

if TYPE_CHECKING:
    from .port import Port

WIRE_WIDTH = 2.5


class Wire(QGraphicsPathItem):
    """Bezier connection between an output port and an input port."""

    def __init__(self, src: Port, dst: Port | None = None):
        super().__init__()
        self.src = src
        self.dst = dst
        self._drag_pos: QPointF | None = None

        color = QColor("#fbbf24" if src.port_type == "value" else "#a855f7")
        pen = QPen(color, WIRE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)
        self.setOpacity(0.85)
        self.setZValue(1)
        # make wire easier to click — wider invisible shape
        self.setFlag(self.GraphicsItemFlag.ItemIsSelectable, True)
        self.update_path()

    def set_drag_pos(self, pos: QPointF):
        self._drag_pos = pos
        self.update_path()

    def update_path(self):
        p1 = self.src.scene_pos()
        p2 = self.dst.scene_pos() if self.dst else (self._drag_pos or p1)
        dx = max(abs(p2.x() - p1.x()) * 0.5, 60)
        path = QPainterPath(p1)
        path.cubicTo(
            QPointF(p1.x() + dx, p1.y()),
            QPointF(p2.x() - dx, p2.y()),
            p2,
        )
        self.setPath(path)

    def shape(self):
        # widen the clickable area to ±8px around the wire
        from PySide6.QtGui import QPainterPathStroker
        stroker = QPainterPathStroker()
        stroker.setWidth(16)
        return stroker.createStroke(self.path())

    def finalize(self, dst: Port):
        self.dst = dst
        self.src.wires.append(self)
        self.dst.wires.append(self)
        self._drag_pos = None
        self.update_path()
        self.src.on_connection_changed()
        self.dst.on_connection_changed()

    def remove(self):
        src, dst = self.src, self.dst
        if src and self in src.wires:
            src.wires.remove(self)
        if dst and self in dst.wires:
            dst.wires.remove(self)
        if self.scene():
            self.scene().removeItem(self)
        if src:
            src.on_connection_changed()
        if dst:
            dst.on_connection_changed()
