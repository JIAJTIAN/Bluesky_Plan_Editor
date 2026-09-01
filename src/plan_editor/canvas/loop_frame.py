"""Zip-loop frame — resizable container whose enclosed nodes form the loop body."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsProxyWidget, QHBoxLayout,
    QLineEdit, QPushButton, QWidget,
)

from .port import Port, PortKind

# ── geometry ──────────────────────────────────────────────────────────────────
PORT_R      = 7
HEADER_H    = 32
PORT_ROW_H  = 36
BTN_ROW_H   = 24
PAD         = 12
MIN_W       = 500
MIN_H       = 300

# ── colours ───────────────────────────────────────────────────────────────────
_BG        = QColor("#091a09")
_BORDER    = QColor("#4ade80")
_HDR_BG    = QColor("#0f3a0f")
_TITLE_CLR = QColor("#4ade80")
_LABEL_CLR = QColor("#94a3b8")
_VALUE_CLR = QColor("#fbbf24")
_PLAN_CLR  = QColor("#a855f7")

# ── fonts ─────────────────────────────────────────────────────────────────────
_TITLE_FONT = QFont("Segoe UI", 9)
_TITLE_FONT.setBold(True)
_LABEL_FONT = QFont("Segoe UI", 8)

# ── styles ────────────────────────────────────────────────────────────────────
_BTN_STYLE = (
    "QPushButton { background:#1e2535; color:#64748b; border:1px solid #2e3a50;"
    " font-size:11px; font-weight:bold; border-radius:3px; padding:0; }"
    "QPushButton:hover { background:#2e3a50; color:#94a3b8; }"
    "QPushButton:pressed { background:#0f1117; }"
)


class LoopFrame(QGraphicsItem):
    """Zip-loop frame container.

    Header: ○ in — out ○ plan flow ports.
    Left edge: expandable ◇ list N amber ports.
    Each list port auto-creates a LoopVarNode inside the frame.
    The variable name lives only on the LoopVarNode (var_name param) — edit it there.
    """

    def __init__(self, pos: QPointF = QPointF(0, 0)):
        super().__init__()
        self._w = float(MIN_W)
        self._h = float(MIN_H)

        self._list_ports:  list[Port]                = []
        self._var_nodes:   list                      = []   # BaseNode | None
        self._var_proxies: list[QGraphicsProxyWidget] = []
        self._body_ports:  list[Port]                = []

        # Flow ports on the header
        self._in_port  = Port(self, "in",  "plan", PortKind.INPUT,  0)
        self._out_port = Port(self, "out", "plan", PortKind.OUTPUT, 0)
        for p in (self._in_port, self._out_port):
            p.setParentItem(self)
        self._in_port.setPos(0,        HEADER_H / 2)
        self._out_port.setPos(self._w, HEADER_H / 2)

        self.setFlag(QGraphicsItem.ItemIsMovable,            True)
        self.setFlag(QGraphicsItem.ItemIsSelectable,         True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setZValue(-1)
        self.setPos(pos)

        self._build_buttons()

    # called by scene immediately after addItem so self.scene() is valid
    def init_after_add(self):
        self._add_list()
        self._add_body()

    # Port interface: called by Port.on_connection_changed
    def update_widgets(self):
        pass

    # ── port accessors ────────────────────────────────────────────────────────
    @property
    def input_ports(self) -> list[Port]:
        return [self._in_port] + self._list_ports

    @property
    def output_ports(self) -> list[Port]:
        return [self._out_port] + self._body_ports

    # ── var name (read from var node) ─────────────────────────────────────────
    def var_name(self, idx: int) -> str:
        vn = self._var_nodes[idx] if idx < len(self._var_nodes) else None
        if vn is not None:
            return str(vn.params.get("var_name", f"_v{idx}")).strip() or f"_v{idx}"
        # fall back to the frame's var field text
        if idx < len(self._var_proxies):
            txt = self._var_proxies[idx].widget().text().strip()
            if txt:
                return txt
        return f"_v{idx}"

    # ── expandable list ports ─────────────────────────────────────────────────
    def _port_y(self, i: int) -> float:
        return HEADER_H + PAD + i * PORT_ROW_H + PORT_ROW_H / 2

    def _add_list(self):
        i = len(self._list_ports)

        port = Port(self, f"list {i + 1}", "value", PortKind.INPUT, i + 1)
        port.setParentItem(self)
        port.setPos(0, self._port_y(i))
        self._list_ports.append(port)

        # var: QLineEdit for this list slot
        fld = QLineEdit()
        fld.setPlaceholderText(f"_v{i}")
        fld.setText(f"_v{i}")
        fld.setFixedSize(90, 20)
        fld.setStyleSheet(
            "QLineEdit { background:#0f1117; color:#fbbf24; border:1px solid #374151;"
            " border-radius:3px; padding:1px 4px; font-size:11px; }"
            "QLineEdit:focus { border-color:#fbbf24; }"
        )
        proxy = QGraphicsProxyWidget(self)
        proxy.setWidget(fld)
        proxy.setZValue(3)
        y = self._port_y(i)
        proxy.setPos(PORT_R + 68, y - 10)
        self._var_proxies.append(proxy)

        # connect after appending so index is stable
        fld.editingFinished.connect(lambda idx=i: self._on_var_changed(idx))

        if self.scene() is not None:
            self._spawn_var_node(i)
        else:
            self._var_nodes.append(None)

        self._update_geometry()

    def _on_var_changed(self, idx: int):
        if idx >= len(self._var_proxies):
            return
        fld = self._var_proxies[idx].widget()
        name = fld.text().strip() or f"_v{idx}"
        vn = self._var_nodes[idx] if idx < len(self._var_nodes) else None
        if vn is not None:
            vn.params["var_name"] = name
            vn.update()

    def _spawn_var_node(self, idx: int):
        from plan_editor.canvas.node import BaseNode
        from plan_editor.registry.builtin_plans import BUILTIN_BY_ID
        schema = BUILTIN_BY_ID.get("loop_var")
        if schema is None:
            self._var_nodes.append(None)
            return
        # read name from frame's var field
        if idx < len(self._var_proxies):
            name = self._var_proxies[idx].widget().text().strip() or f"_v{idx}"
        else:
            name = f"_v{idx}"
        scene_pos = self.mapToScene(QPointF(self._w - 230, self._port_y(idx) - 14))
        vnode = BaseNode(schema, scene_pos)
        vnode.params["var_name"] = name
        self.scene().addItem(vnode)
        self._var_nodes.append(vnode)

    def _remove_list(self):
        if len(self._list_ports) <= 1:
            return

        port = self._list_ports.pop()
        for w in list(port.wires):
            w.remove()
        port.setParentItem(None)
        if port.scene():
            port.scene().removeItem(port)

        proxy = self._var_proxies.pop()
        proxy.setParentItem(None)
        if proxy.scene():
            proxy.scene().removeItem(proxy)

        vn = self._var_nodes.pop()
        if vn is not None and vn.scene():
            for p in vn.input_ports + vn.output_ports:
                for w in list(p.wires):
                    w.remove()
            vn.scene().removeItem(vn)

        self._update_geometry()

    def _add_body(self):
        i = len(self._body_ports)
        port = Port(self, f"func {i + 1}", "plan", PortKind.OUTPUT, i + 1)
        port.setParentItem(self)
        port.setPos(self._w, self._port_y(i))
        self._body_ports.append(port)
        self._update_geometry()

    def _remove_body(self):
        if len(self._body_ports) <= 1:
            return
        port = self._body_ports.pop()
        for w in list(port.wires):
            w.remove()
        port.setParentItem(None)
        if port.scene():
            port.scene().removeItem(port)
        self._update_geometry()

    def _update_geometry(self):
        n      = max(len(self._list_ports), len(self._body_ports), 1)
        needed = HEADER_H + PAD + n * PORT_ROW_H + BTN_ROW_H + PAD * 2
        self._h = max(float(MIN_H), float(needed))
        self._out_port.setPos(self._w, HEADER_H / 2)
        for i, proxy in enumerate(self._var_proxies):
            y = self._port_y(i)
            proxy.setPos(PORT_R + 68, y - 10)
        for i, bp in enumerate(self._body_ports):
            bp.setPos(self._w, self._port_y(i))
        self._reposition_buttons()
        self.prepareGeometryChange()
        self.update()

    # ── expand buttons ────────────────────────────────────────────────────────
    def _build_buttons(self):
        ctr = QWidget()
        ctr.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(ctr)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        for label, fn in (
            ("+list", self._add_list), ("−list", self._remove_list),
            ("+func", self._add_body), ("−func", self._remove_body),
        ):
            btn = QPushButton(label)
            btn.setFixedHeight(BTN_ROW_H - 4)
            btn.setStyleSheet(_BTN_STYLE)
            btn.clicked.connect(fn)
            lay.addWidget(btn)
        ctr.setFixedSize(168, BTN_ROW_H)
        self._btn_proxy = QGraphicsProxyWidget(self)
        self._btn_proxy.setWidget(ctr)
        self._btn_proxy.setZValue(3)
        self._reposition_buttons()

    def _reposition_buttons(self):
        n = len(self._list_ports)
        y = HEADER_H + PAD + n * PORT_ROW_H + 4
        self._btn_proxy.setPos(12, y)


    # ── Qt overrides ──────────────────────────────────────────────────────────
    def boundingRect(self) -> QRectF:
        return QRectF(-PORT_R, -PORT_R,
                      self._w + PORT_R * 2, self._h + PORT_R * 2)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self._w, self._h)
        hdr  = QRectF(0, 0, self._w, HEADER_H)
        sel  = self.isSelected()
        border = _BORDER.lighter(130) if sel else _BORDER

        # Body fill + dashed border
        painter.setBrush(QBrush(_BG))
        painter.setPen(QPen(border, 1.5, Qt.DashLine))
        painter.drawRoundedRect(rect, 8, 8)

        # Header fill
        painter.setBrush(QBrush(_HDR_BG))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(hdr, 8, 8)
        painter.drawRect(QRectF(0, HEADER_H / 2, self._w, HEADER_H / 2))

        # Header border (redraw over fill)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border, 1.5, Qt.DashLine))
        painter.drawRoundedRect(rect, 8, 8)

        # Title
        painter.setFont(_TITLE_FONT)
        painter.setPen(_TITLE_CLR)
        painter.drawText(
            QRectF(PORT_R + 30, 0, self._w / 2, HEADER_H),
            Qt.AlignVCenter | Qt.AlignLeft,
            "zip loop",
        )

        # Flow port labels
        painter.setFont(_LABEL_FONT)
        painter.setPen(_LABEL_CLR)
        painter.drawText(QRectF(PORT_R + 12, 0, 24, HEADER_H), Qt.AlignVCenter, "in")
        painter.drawText(QRectF(self._w - 36, 0, 28, HEADER_H),
                         Qt.AlignVCenter | Qt.AlignRight, "out")

        # Plan port dots in header
        for cx in (PORT_R + 6, self._w - PORT_R - 6):
            painter.setBrush(_PLAN_CLR)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cx, HEADER_H / 2), 4, 4)

        # List port rows — amber diamond + "list N" label + "var:" label
        painter.setFont(_LABEL_FONT)
        for i, port in enumerate(self._list_ports):
            y  = port.pos().y()
            cx = PORT_R + 6
            r  = 4
            painter.setBrush(_VALUE_CLR)
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygonF([
                QPointF(cx, y - r), QPointF(cx + r, y),
                QPointF(cx, y + r), QPointF(cx - r, y),
            ]))
            painter.setPen(_LABEL_CLR)
            painter.drawText(
                QRectF(PORT_R + 16, y - PORT_ROW_H / 2, 48, PORT_ROW_H),
                Qt.AlignVCenter, f"list {i + 1}",
            )
            painter.drawText(
                QRectF(PORT_R + 50, y - PORT_ROW_H / 2, 20, PORT_ROW_H),
                Qt.AlignVCenter | Qt.AlignRight, "var:",
            )

        # Body port rows — purple diamond + "func N →" label on right side
        for i, port in enumerate(self._body_ports):
            y  = port.pos().y()
            cx = self._w - PORT_R - 6
            r  = 5
            painter.setBrush(_PLAN_CLR)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(cx, y), r - 1, r - 1)
            painter.setPen(_LABEL_CLR)
            painter.drawText(
                QRectF(self._w - 80, y - PORT_ROW_H / 2, 62, PORT_ROW_H),
                Qt.AlignVCenter | Qt.AlignRight, f"func {i + 1} →",
            )

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for p in self.input_ports + self.output_ports:
                p.notify_wires()
        return super().itemChange(change, value)


