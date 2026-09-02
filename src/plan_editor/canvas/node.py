from __future__ import annotations

import re

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QFrame, QGraphicsItem, QGraphicsProxyWidget, QHBoxLayout,
    QLineEdit, QListWidget, QPushButton, QFileDialog, QVBoxLayout, QWidget,
)

from .port import Port, PortKind
from plan_editor.registry.schema import NodeSchema, PortSpec  # noqa: F401

# ── geometry ──────────────────────────────────────────────────────────────────
NODE_WIDTH   = 220
NODE_HEADER  = 28
PORT_ROW_H   = 24
PARAM_ROW_H  = 22
BUTTON_ROW_H = 20   # height of the +/- expand row
NODE_PAD     = 8
PORT_R       = 7

PARAM_LABEL_W = 68
PARAM_FIELD_X = PARAM_LABEL_W + 6
PARAM_FIELD_W = NODE_WIDTH - PARAM_FIELD_X - 10
PARAM_FIELD_H = 18

# ── inline-pair layout (mv / mvr) ─────────────────────────────────────────────
_INLINE_IDX_W = 18                                         # "1→" prefix width
_INLINE_GAP   = 3
_INLINE_FW    = (NODE_WIDTH - _INLINE_IDX_W - _INLINE_GAP * 3 - 10) // 2  # ≈ 91

# ── colours ───────────────────────────────────────────────────────────────────
NODE_BG         = QColor("#1a1f2e")
NODE_BORDER     = QColor("#2e3a50")
NODE_BORDER_SEL = QColor("#7dd3fc")
PLAN_COLOR      = QColor("#a855f7")
VALUE_COLOR     = QColor("#fbbf24")   # amber — for value/data ports
LABEL_COLOR     = QColor("#94a3b8")
HEADER_COLORS   = {
    "scan":    (QColor("#0f1f3a"), QColor("#7dd3fc")),
    "motion":  (QColor("#291e00"), QColor("#fbbf24")),
    "flow":    (QColor("#2a0f0f"), QColor("#f87171")),
    "loop":    (QColor("#0a2a0a"), QColor("#4ade80")),
    "acquire": (QColor("#0a2222"), QColor("#2dd4bf")),
    "run":     (QColor("#2a1400"), QColor("#fb923c")),
    "control": (QColor("#18181f"), QColor("#94a3b8")),
    "custom":  (QColor("#1a0f2e"), QColor("#c084fc")),
    "output":  (QColor("#1a0f2e"), QColor("#c084fc")),
    "device":  (QColor("#0a2a1a"), QColor("#34d399")),
}

# ── fonts ─────────────────────────────────────────────────────────────────────
_TITLE_FONT = QFont("Segoe UI", 9)
_TITLE_FONT.setBold(True)
_LABEL_FONT = QFont("Segoe UI", 8)

# ── field stylesheet ──────────────────────────────────────────────────────────
_FIELD_STYLE = (
    "background:#0f1117; border:1px solid #334155; border-radius:3px;"
    "color:#e2e8f0; font-size:11px; font-family:'Segoe UI'; padding:0 4px;"
    "selection-background-color:#1e3a5f;"
)
_BTN_STYLE = (
    "QPushButton { background:#1e2535; color:#64748b; border:1px solid #2e3a50;"
    " font-size:11px; font-weight:bold; border-radius:3px; padding:0; }"
    "QPushButton:hover { background:#2e3a50; color:#94a3b8; }"
    "QPushButton:pressed { background:#0f1117; }"
)



class _DevicePopup(QFrame):
    """Floating searchable device list — positioned at cursor, always on-screen."""

    def __init__(self, choices: list[str], parent_field: "QLineEdit"):
        super().__init__(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._choices = choices
        self._field   = parent_field
        self.setStyleSheet(
            "QFrame { background:#1e2535; border:1px solid #334155; border-radius:4px; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setStyleSheet(
            "QLineEdit { background:#0f1117; border:1px solid #334155; border-radius:3px;"
            " color:#e2e8f0; font-size:11px; padding:2px 6px; }"
        )
        self._search.textChanged.connect(self._filter)
        self._search.installEventFilter(self)
        lay.addWidget(self._search)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget { background:#0f1117; border:none; color:#e2e8f0; font-size:11px; }"
            "QListWidget::item { padding:2px 6px; }"
            "QListWidget::item:selected { background:#1e3a5f; color:#e2e8f0; }"
            "QListWidget::item:hover { background:#2e3a50; }"
        )
        self._list.setFixedHeight(160)
        self._list.itemClicked.connect(self._pick)
        lay.addWidget(self._list)

        self._populate(choices)
        self.setFixedWidth(180)

    def _populate(self, items: list[str]):
        self._list.clear()
        for it in items:
            self._list.addItem(it)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _filter(self, text: str):
        q = text.lower()
        self._populate([c for c in self._choices if q in c.lower()])

    def _pick(self, item):
        self._field.setText(item.text())
        self._field.editingFinished.emit()
        self.close()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._search and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                cur = self._list.currentItem()
                if cur:
                    self._pick(cur)
                return True
            if key == Qt.Key.Key_Escape:
                self.close()
                return True
            if key == Qt.Key.Key_Down:
                row = min(self._list.currentRow() + 1, self._list.count() - 1)
                self._list.setCurrentRow(row)
                return True
            if key == Qt.Key.Key_Up:
                row = max(self._list.currentRow() - 1, 0)
                self._list.setCurrentRow(row)
                return True
        return super().eventFilter(obj, event)

    def show_at_cursor(self):
        pos = QCursor.pos()
        self.move(pos.x() + 2, pos.y() + 4)
        self.show()
        self._search.clear()
        self._search.setFocus()


class _DeviceLineEdit(QLineEdit):
    """QLineEdit that opens a floating searchable device list on click."""

    def __init__(self, choices: list[str], value: str = ""):
        super().__init__(value)
        self._choices = choices
        self._popup: "_DevicePopup | None" = None

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._popup = _DevicePopup(self._choices, self)
        self._popup.show_at_cursor()


class BaseNode(QGraphicsItem):
    def __init__(self, schema: NodeSchema, scene_pos: QPointF = QPointF(0, 0)):
        super().__init__()
        self.schema = schema
        self.params: dict = dict(schema.params)
        self.input_ports:  list[Port] = []
        self.output_ports: list[Port] = []
        self._param_fields:   dict[str, QLineEdit]              = {}
        self._param_proxies:  dict[str, QGraphicsProxyWidget]   = {}
        self._expand_proxy:   QGraphicsProxyWidget | None       = None

        # For param_pairs nodes: how many pairs are currently shown.
        # Count only params whose key matches {pair_key}_{digit} — ignores fixed params.
        if schema.param_pairs:
            pair_keys = set(schema.param_pairs)
            n_pair_params = sum(
                1 for k in schema.params
                if "_" in k and k.rsplit("_", 1)[1].isdigit()
                   and k.rsplit("_", 1)[0] in pair_keys
            )
            self._num_pairs: int = max(1, n_pair_params // max(1, len(schema.param_pairs)))
        else:
            self._num_pairs: int = 0

        self.collapsed: bool = False
        self.muted:     bool = False

        self.setFlag(QGraphicsItem.ItemIsMovable,            True)
        self.setFlag(QGraphicsItem.ItemIsSelectable,         True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setPos(scene_pos)
        self.setZValue(0)

        self._build()

    # ── expandability ─────────────────────────────────────────────────────────
    def _is_expandable(self) -> bool:
        return bool(self.schema.param_pairs) or self.schema.expandable_ports

    def _add_item(self):
        if self.schema.param_pairs:
            self._add_pair()
        elif self.schema.expandable_ports:
            self._add_port()

    def _remove_item(self):
        if self.schema.param_pairs:
            self._remove_pair()
        elif self.schema.expandable_ports:
            self._remove_port()

    def _add_pair(self):
        i = self._num_pairs
        for key in self.schema.param_pairs:
            template_key = f"{key}_0"
            default = self.schema.params.get(template_key, "")
            self.params[f"{key}_{i}"] = default
        self._num_pairs += 1
        if self.schema.expand_output_ports:
            self._append_output_port(i)
        self._rebuild()

    def _remove_pair(self):
        if self._num_pairs <= 1:
            return
        i = self._num_pairs - 1
        for key in self.schema.param_pairs:
            self.params.pop(f"{key}_{i}", None)
        self._num_pairs -= 1
        if self.schema.expand_output_ports:
            self._pop_output_port()
        self._rebuild()

    def _append_output_port(self, col_idx: int):
        p = Port(self, f"col {col_idx + 1}", "value", PortKind.OUTPUT, col_idx)
        p.setParentItem(self)
        p.setPos(NODE_WIDTH, self._port_y(col_idx))
        self.output_ports.append(p)
        self.prepareGeometryChange()
        self.update()

    def _pop_output_port(self):
        if not self.output_ports:
            return
        port = self.output_ports.pop()
        for w in list(port.wires):
            w.remove()
        port.setParentItem(None)
        if port.scene():
            port.scene().removeItem(port)
        self.prepareGeometryChange()
        self.update()

    def _add_port(self):
        ptype = self.schema.expand_port_type
        n_same = sum(1 for p in self.input_ports if p.port_type == ptype)
        if self.schema.expand_port_name:
            name = self.schema.expand_port_name
        elif ptype == "value":
            # count only the expandable slots (subtract fixed schema value ports)
            n_schema_fixed = sum(1 for s in self.schema.inputs if s.port_type == ptype)
            name = f"arg {n_same - n_schema_fixed}"
        else:
            name = f"plan {n_same + 1}"
        i = len(self.input_ports)
        p = Port(self, name, ptype, PortKind.INPUT, i)
        p.setParentItem(self)
        p.setPos(0, self._port_y(i))
        self.input_ports.append(p)
        self.prepareGeometryChange()
        self._reposition_expand_button()
        self.update()

    def _remove_port(self):
        if len(self.input_ports) <= self.schema.min_ports:
            return
        port = self.input_ports.pop()
        for w in list(port.wires):
            w.remove()
            if self.scene() and hasattr(self.scene(), 'graph_changed'):
                self.scene().graph_changed.emit()
        port.setParentItem(None)
        if port.scene():
            port.scene().removeItem(port)
        self.prepareGeometryChange()
        self._reposition_expand_button()
        self.update()

    def _rebuild(self):
        """Rebuild all param proxy widgets (called after adding/removing pairs)."""
        # Remove existing param proxies (keep expand button separate)
        for proxy in list(self._proxies()):
            if proxy is self._expand_proxy:
                continue
            proxy.setParentItem(None)
            if proxy.scene():
                proxy.scene().removeItem(proxy)
        self._param_fields.clear()
        self._param_proxies.clear()

        # Reposition output ports to match current pair count
        if self.schema.expand_output_ports:
            for i, p in enumerate(self.output_ports):
                p.setPos(NODE_WIDTH, self._port_y(i))
                p.name = f"col {i + 1}"
                p.index = i
                p.notify_wires()

        self.prepareGeometryChange()
        self._build_param_widgets()
        self._reposition_expand_button()
        self.update()

    def _reposition_expand_button(self):
        if self._expand_proxy:
            y = self._expand_button_y()
            self._expand_proxy.setPos(8, y)

    def _expand_button_y(self) -> float:
        return self._total_height() - NODE_PAD - BUTTON_ROW_H

    # ── collapse / mute ───────────────────────────────────────────────────────
    def toggle_collapsed(self):
        self.collapsed = not self.collapsed
        self.prepareGeometryChange()
        for p in self._proxies():
            p.setVisible(not self.collapsed)
        self.update()

    def toggle_muted(self):
        self.muted = not self.muted
        self.update()

    def _proxies(self):
        return [c for c in self.childItems() if isinstance(c, QGraphicsProxyWidget)]

    # ── layout ────────────────────────────────────────────────────────────────
    def _port_rows(self) -> int:
        return max(len(self.input_ports), len(self.output_ports))

    def _fixed_params(self) -> list[str]:
        """Param keys that are NOT part of the expandable pairs (global/fixed rows)."""
        if not self.schema.param_pairs:
            return list(self.params.keys())
        pair_keys = set(self.schema.param_pairs)
        return [k for k in self.params
                if not ("_" in k and k.rsplit("_", 1)[1].isdigit()
                        and k.rsplit("_", 1)[0] in pair_keys)]

    def _param_row_count(self) -> int:
        if self.schema.inline_pairs:
            return self._num_pairs + len(self._fixed_params())
        if self.schema.param_pairs:
            return self._num_pairs * len(self.schema.param_pairs) + len(self._fixed_params())
        return len(self.params)

    def _total_height(self) -> float:
        if self.collapsed:
            return NODE_HEADER + NODE_PAD
        port_section  = self._port_rows() * PORT_ROW_H if self._port_rows() else 0
        param_section = self._param_row_count() * PARAM_ROW_H
        separator     = 6 if (port_section and param_section) else 0
        expand_row    = (BUTTON_ROW_H + 4) if self._is_expandable() else 0
        return NODE_HEADER + port_section + separator + param_section + expand_row + NODE_PAD

    def boundingRect(self) -> QRectF:
        return QRectF(-PORT_R, 0, NODE_WIDTH + PORT_R * 2, self._total_height())

    def _port_y(self, index: int) -> float:
        return NODE_HEADER + index * PORT_ROW_H + PORT_ROW_H / 2

    def _param_top(self) -> float:
        port_section = self._port_rows() * PORT_ROW_H if self._port_rows() else 0
        has_params   = bool(self.schema.param_pairs) or bool(self.params)
        separator    = 6 if (port_section and has_params) else 0
        return NODE_HEADER + port_section + separator

    # ── build ─────────────────────────────────────────────────────────────────
    def _build(self):
        for i, spec in enumerate(self.schema.inputs):
            p = Port(self, spec.name, spec.port_type, PortKind.INPUT, i)
            p.setParentItem(self)
            p.setPos(0, self._port_y(i))
            self.input_ports.append(p)

        # Add optional wireable value ports for each name in value_inputs
        for name in self.schema.value_inputs:
            i = len(self.input_ports)
            p = Port(self, name, "value", PortKind.INPUT, i)
            p.setParentItem(self)
            p.setPos(0, self._port_y(i))
            self.input_ports.append(p)

        if self.schema.expand_output_ports:
            # One output port per initial param_pair row
            for i in range(self._num_pairs):
                p = Port(self, f"col {i + 1}", "value", PortKind.OUTPUT, i)
                p.setParentItem(self)
                p.setPos(NODE_WIDTH, self._port_y(i))
                self.output_ports.append(p)
        else:
            for i, spec in enumerate(self.schema.outputs):
                p = Port(self, spec.name, spec.port_type, PortKind.OUTPUT, i)
                p.setParentItem(self)
                p.setPos(NODE_WIDTH, self._port_y(i))
                self.output_ports.append(p)

        self._build_param_widgets()

        if self._is_expandable():
            self._build_expand_button()

    def _build_param_widgets(self):
        param_top = self._param_top()

        if self.schema.inline_pairs:
            # One row per pair: [idx→] [motor___] [pos/delta___]
            keys = self.schema.param_pairs
            for i in range(self._num_pairs):
                k0 = f"{keys[0]}_{i}"
                k1 = f"{keys[1]}_{i}"
                x0 = _INLINE_IDX_W + _INLINE_GAP
                x1 = x0 + _INLINE_FW + _INLINE_GAP
                self._make_field(k0, str(self.params.get(k0, "")), param_top, i, x=x0, w=_INLINE_FW)
                self._make_field(k1, str(self.params.get(k1, "")), param_top, i, x=x1, w=_INLINE_FW)
            for fi, key in enumerate(self._fixed_params()):
                self._make_field(key, str(self.params.get(key, "")), param_top, self._num_pairs + fi)

        elif self.schema.param_pairs:
            keys = self.schema.param_pairs
            row = 0
            for i in range(self._num_pairs):
                for key in keys:
                    param_key = f"{key}_{i}"
                    val = self.params.get(param_key, "")
                    self._make_field(param_key, str(val), param_top, row)
                    row += 1
            for key in self._fixed_params():
                val = self.params.get(key, "")
                self._make_field(key, str(val), param_top, row)
                row += 1
        else:
            for row, key in enumerate(self.params):
                val = self.params.get(key, "")
                self._make_field(key, str(val), param_top, row)

    def _make_field(self, key: str, value: str, param_top: float, row: int,
                    x: float | None = None, w: float | None = None):
        y = param_top + row * PARAM_ROW_H + (PARAM_ROW_H - PARAM_FIELD_H) / 2
        fx = x if x is not None else PARAM_FIELD_X
        fw = w if w is not None else PARAM_FIELD_W
        base_key = re.sub(r'_\d+$', '', key)
        choices = self.schema.param_choices.get(key) or self.schema.param_choices.get(base_key)
        widget = _DeviceLineEdit(list(choices), value) if choices else QLineEdit(value)
        widget.setStyleSheet(_FIELD_STYLE)
        widget.setFixedHeight(PARAM_FIELD_H)
        widget.setPlaceholderText(key.split("_")[0])
        widget.editingFinished.connect(self._make_commit(key, widget))
        proxy = QGraphicsProxyWidget(self)
        proxy.setWidget(widget)
        proxy.setPos(fx, y)
        proxy.resize(fw, PARAM_FIELD_H)
        proxy.setZValue(3)
        self._param_fields[key]  = widget
        self._param_proxies[key] = proxy
        self._update_field_visibility(key, proxy)

    def _port_for_param(self, key: str):
        """Return the wired value port that controls this param, if any."""
        base = re.sub(r'_\d+$', '', key)
        for p in self.input_ports:
            if p.port_type == "value" and (p.name == base or p.name.startswith(base)):
                return p
        return None

    def _update_field_visibility(self, key: str, proxy: "QGraphicsProxyWidget"):
        port = self._port_for_param(key)
        if port is not None:
            proxy.setVisible(not bool(port.wires))

    def _refresh_field_visibility(self):
        for key, proxy in self._param_proxies.items():
            self._update_field_visibility(key, proxy)

    def _build_expand_button(self):
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        btn_add = QPushButton("+")
        btn_add.setFixedHeight(BUTTON_ROW_H - 2)
        btn_add.setStyleSheet(_BTN_STYLE)
        btn_add.clicked.connect(self._add_item)
        layout.addWidget(btn_add)

        btn_rem = QPushButton("−")
        btn_rem.setFixedHeight(BUTTON_ROW_H - 2)
        btn_rem.setStyleSheet(_BTN_STYLE)
        btn_rem.clicked.connect(self._remove_item)
        layout.addWidget(btn_rem)

        if self.schema.supports_csv:
            btn_csv = QPushButton("CSV")
            btn_csv.setFixedHeight(BUTTON_ROW_H - 2)
            btn_csv.setStyleSheet(_BTN_STYLE)
            btn_csv.clicked.connect(self._import_csv)
            layout.addWidget(btn_csv)

        container.setFixedSize(NODE_WIDTH - 16, BUTTON_ROW_H)

        self._expand_proxy = QGraphicsProxyWidget(self)
        self._expand_proxy.setWidget(container)
        self._expand_proxy.setPos(8, self._expand_button_y())
        self._expand_proxy.setZValue(3)

    def _import_csv(self):
        """Read a CSV file and populate param_pairs rows from its columns."""
        import csv as _csv
        path, _ = QFileDialog.getOpenFileName(
            None, "Import CSV", "", "CSV files (*.csv *.tsv *.txt)")
        if not path:
            return
        try:
            with open(path, newline="") as f:
                sample = f.read(2048); f.seek(0)
                try:
                    dialect = _csv.Sniffer().sniff(sample)
                except _csv.Error:
                    dialect = _csv.excel

                if self.schema.expand_output_ports:
                    # Auto-detect header and skip it if present
                    has_hdr = False
                    try:
                        has_hdr = _csv.Sniffer().has_header(sample)
                    except _csv.Error:
                        pass
                    raw_rows = list(_csv.reader(f, dialect=dialect))
                    rows = raw_rows[1:] if has_hdr and raw_rows else raw_rows
                else:
                    reader = _csv.DictReader(f, dialect=dialect)
                    rows = list(reader)
        except Exception:
            return
        if not rows:
            return

        pair_keys = self.schema.param_pairs

        if self.schema.expand_output_ports:
            # Transpose: rows of values → list of columns
            n_cols = max(len(r) for r in rows)
            columns: list[list] = [[] for _ in range(n_cols)]
            for row in rows:
                for ci in range(n_cols):
                    raw = row[ci].strip() if ci < len(row) else ""
                    try:
                        columns[ci].append(float(raw) if "." in raw else int(raw))
                    except (ValueError, AttributeError):
                        columns[ci].append(raw)

            # Clear existing pair params
            for k in [k for k in self.params
                      if "_" in k and k.rsplit("_", 1)[1].isdigit()
                      and k.rsplit("_", 1)[0] in set(pair_keys)]:
                del self.params[k]

            # Adjust output port count
            while len(self.output_ports) > 1:
                self._pop_output_port()
            self._num_pairs = 0

            for ci, col in enumerate(columns):
                col_str = ", ".join(str(v) for v in col)
                self.params[f"values_{ci}"] = col_str
                self._num_pairs += 1
                if ci > 0:
                    self._append_output_port(ci)
        else:
            # Header-based mode: map CSV column names to pair keys
            col_map: dict[str, str] = {}
            csv_cols = list(rows[0].keys())
            for pk in pair_keys:
                for col in csv_cols:
                    if pk.lower() in col.lower():
                        col_map[pk] = col
                        break

            for k in [k for k in self.params
                      if "_" in k and k.rsplit("_", 1)[1].isdigit()
                      and k.rsplit("_", 1)[0] in set(pair_keys)]:
                del self.params[k]
            self._num_pairs = 0
            for i, row in enumerate(rows):
                for pk in pair_keys:
                    col = col_map.get(pk)
                    val = row.get(col, "") if col else ""
                    try:
                        val = float(val) if val and pk in ("start", "stop") else val
                    except ValueError:
                        pass
                    self.params[f"{pk}_{i}"] = val
                self._num_pairs += 1

        self._rebuild()
        if self.scene() and hasattr(self.scene(), "graph_changed"):
            self.scene().graph_changed.emit()

    def _make_commit(self, key: str, field: QLineEdit):
        def _commit():
            raw = field.text()
            try:
                val = float(raw) if ("." in raw or "e" in raw.lower()) else int(raw)
            except ValueError:
                val = raw
            self.params[key] = val
        return _commit


    # ── called by Wire on connect / disconnect ────────────────────────────────
    def update_widgets(self):
        self._refresh_field_visibility()
        self.update()

    # ── paint ─────────────────────────────────────────────────────────────────
    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        cat  = self.schema.category
        h    = self._total_height()
        body = QRectF(0, 0, NODE_WIDTH, h)
        hdr  = QRectF(0, 0, NODE_WIDTH, NODE_HEADER)
        hdr_bg, title_color = HEADER_COLORS.get(cat, (QColor("#1a1f2e"), QColor("#e2e8f0")))

        selected = self.isSelected()
        if self.muted:
            border, bw, pen_style = QColor("#475569"), 1.0, Qt.DashLine
        else:
            border    = NODE_BORDER_SEL if selected else NODE_BORDER
            bw        = 2.0             if selected else 1.0
            pen_style = Qt.SolidLine

        painter.setPen(Qt.NoPen)
        painter.setBrush(NODE_BG)
        painter.drawRoundedRect(body, 6, 6)
        painter.setBrush(hdr_bg)
        painter.drawRoundedRect(hdr, 6, 6)
        painter.drawRect(QRectF(0, NODE_HEADER / 2, NODE_WIDTH, NODE_HEADER / 2))

        pen = QPen(border, bw)
        pen.setStyle(pen_style)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        painter.drawRoundedRect(body, 6, 6)

        if self.muted:
            painter.setFont(_LABEL_FONT)
            painter.setPen(QColor("#ef4444"))
            painter.drawText(QRectF(NODE_WIDTH - 18, 0, 14, NODE_HEADER),
                             Qt.AlignVCenter | Qt.AlignRight, "M")

        arrow = "▸" if self.collapsed else "▾"
        painter.setFont(_LABEL_FONT)
        painter.setPen(QColor("#475569"))
        painter.drawText(QRectF(NODE_WIDTH - 18, 0, 14, NODE_HEADER),
                         Qt.AlignVCenter | Qt.AlignRight,
                         arrow if not self.muted else "")

        painter.setFont(_TITLE_FONT)
        painter.setPen(title_color if not self.muted else QColor("#475569"))
        _title = (str(self.params.get(self.schema.title_param, self.schema.title)).strip()
                  if self.schema.title_param else self.schema.title) or self.schema.title
        painter.drawText(
            QRectF(PORT_R + 6, 0, NODE_WIDTH - PORT_R * 2 - 24, NODE_HEADER),
            Qt.AlignVCenter | Qt.AlignLeft,
            _title,
        )

        if self.collapsed:
            return

        # separator
        if self._port_rows() and self._param_row_count():
            sep_y = self._param_top() - 3
            painter.setPen(QPen(QColor("#1e2535"), 1))
            painter.drawLine(QPointF(8, sep_y), QPointF(NODE_WIDTH - 8, sep_y))

        # input port labels (use live input_ports list to support dynamic ports)
        painter.setFont(_LABEL_FONT)
        for port in self.input_ports:
            y = port.pos().y()
            is_val = port.port_type == "value"
            dot_color = VALUE_COLOR if is_val else PLAN_COLOR
            painter.setBrush(dot_color)
            painter.setPen(Qt.NoPen)
            cx = PORT_R + 6
            if is_val:
                r = 4
                from PySide6.QtGui import QPolygonF
                painter.drawPolygon(QPolygonF([
                    QPointF(cx, y - r), QPointF(cx + r, y),
                    QPointF(cx, y + r), QPointF(cx - r, y),
                ]))
            else:
                painter.drawEllipse(QPointF(cx, y), 4, 4)
            painter.setPen(LABEL_COLOR)
            painter.drawText(
                QRectF(PORT_R + 16, y - PORT_ROW_H / 2, NODE_WIDTH / 2, PORT_ROW_H),
                Qt.AlignVCenter | Qt.AlignLeft,
                port.name,
            )

        for port in self.output_ports:
            y = port.pos().y()
            is_val = port.port_type == "value"
            dot_color = VALUE_COLOR if is_val else PLAN_COLOR
            painter.setBrush(dot_color)
            painter.setPen(Qt.NoPen)
            cx = NODE_WIDTH - PORT_R - 6
            if is_val:
                r = 4
                from PySide6.QtGui import QPolygonF
                painter.drawPolygon(QPolygonF([
                    QPointF(cx, y - r), QPointF(cx + r, y),
                    QPointF(cx, y + r), QPointF(cx - r, y),
                ]))
            else:
                painter.drawEllipse(QPointF(cx, y), 4, 4)
            painter.setPen(LABEL_COLOR)
            painter.drawText(
                QRectF(NODE_WIDTH / 2, y - PORT_ROW_H / 2, NODE_WIDTH / 2 - PORT_R - 10, PORT_ROW_H),
                Qt.AlignVCenter | Qt.AlignRight,
                port.name,
            )

        # param labels
        param_top = self._param_top()
        painter.setFont(_LABEL_FONT)

        if self.schema.inline_pairs:
            # One row per pair — draw "i→" index prefix only
            for i in range(self._num_pairs):
                y = param_top + i * PARAM_ROW_H
                painter.setPen(QColor("#64748b"))
                painter.drawText(
                    QRectF(4, y, _INLINE_IDX_W, PARAM_ROW_H),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    f"{i + 1}→",
                )
            fixed = self._fixed_params()
            if fixed:
                sep_y = param_top + self._num_pairs * PARAM_ROW_H - 2
                painter.setPen(QPen(QColor("#1e2535"), 1, Qt.DotLine))
                painter.drawLine(QPointF(8, sep_y), QPointF(NODE_WIDTH - 8, sep_y))
                painter.setPen(QColor("#64748b"))
                for fi, key in enumerate(fixed):
                    y = param_top + (self._num_pairs + fi) * PARAM_ROW_H
                    painter.drawText(
                        QRectF(8, y, PARAM_LABEL_W - 4, PARAM_ROW_H),
                        Qt.AlignVCenter | Qt.AlignLeft,
                        key + ":",
                    )

        elif self.schema.param_pairs:
            keys = self.schema.param_pairs
            n_keys = len(keys)
            for i in range(self._num_pairs):
                if i > 0:
                    div_y = param_top + i * n_keys * PARAM_ROW_H - 2
                    painter.setPen(QPen(QColor("#1e2535"), 1, Qt.DotLine))
                    painter.drawLine(QPointF(8, div_y), QPointF(NODE_WIDTH - 8, div_y))
                for j, key in enumerate(keys):
                    row = i * n_keys + j
                    y = param_top + row * PARAM_ROW_H
                    painter.setPen(QColor("#64748b"))
                    painter.drawText(
                        QRectF(8, y, PARAM_LABEL_W - 4, PARAM_ROW_H),
                        Qt.AlignVCenter | Qt.AlignLeft,
                        f"{key} {i + 1}:",
                    )
            fixed = self._fixed_params()
            if fixed:
                pair_rows = self._num_pairs * n_keys
                sep_y = param_top + pair_rows * PARAM_ROW_H - 2
                painter.setPen(QPen(QColor("#1e2535"), 1, Qt.DotLine))
                painter.drawLine(QPointF(8, sep_y), QPointF(NODE_WIDTH - 8, sep_y))
                painter.setPen(QColor("#64748b"))
                for fi, key in enumerate(fixed):
                    y = param_top + (pair_rows + fi) * PARAM_ROW_H
                    painter.drawText(
                        QRectF(8, y, PARAM_LABEL_W - 4, PARAM_ROW_H),
                        Qt.AlignVCenter | Qt.AlignLeft,
                        key + ":",
                    )
        else:
            painter.setPen(QColor("#64748b"))
            for row, key in enumerate(self.params):
                y = param_top + row * PARAM_ROW_H
                painter.drawText(
                    QRectF(8, y, PARAM_LABEL_W - 4, PARAM_ROW_H),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    key + ":",
                )

    # ── wire propagation ──────────────────────────────────────────────────────
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            for p in self.input_ports + self.output_ports:
                p.notify_wires()
        return super().itemChange(change, value)
