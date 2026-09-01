"""Main application window for plan-editor."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QToolBar,
)

from plan_editor.canvas.node import BaseNode
from plan_editor.canvas.scene import NodeScene
from plan_editor.canvas.view import NodeView
from plan_editor.codegen import build_queue_items, generate_plan_code
from plan_editor.registry.schema import NodeSchema
from plan_editor.ui import examples
from plan_editor.ui.palette import NodePalette
from plan_editor.ui.properties import PropertiesPanel
from plan_editor.ui.search_popup import NodeSearchPopup

_TOOLBAR_STYLE = (
    "QToolBar { background: #0d1117; border-bottom: 1px solid #1e2535; spacing: 4px; padding: 2px 6px; }"
    "QLabel   { color: #64748b; font-size: 11px; }"
    "QLineEdit { background: #141922; color: #94a3b8; border: 1px solid #1e2535;"
    "            border-radius: 3px; font-size: 11px; padding: 2px 6px; }"
    "QPushButton { background: #1e3a5f; color: #7dd3fc; border: 1px solid #2a4a6f;"
    "              border-radius: 3px; font-size: 11px; padding: 3px 10px; }"
    "QPushButton:hover { background: #1a4f8a; }"
    "QPushButton#run_btn { background: #14532d; color: #86efac; border-color: #166534; }"
    "QPushButton#run_btn:hover { background: #166534; }"
)

_APP_NAME = "Plan Editor"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(_APP_NAME)
        self.resize(1400, 860)
        self.setStyleSheet("background: #0f1117; color: #e2e8f0;")
        self._current_file: str | None = None

        # ── scene + view ──────────────────────────────────────────────────────
        self._scene = NodeScene(self)
        self._view  = NodeView(self._scene)
        self.setCentralWidget(self._view)

        # ── palette dock ──────────────────────────────────────────────────────
        self._palette = NodePalette()
        self._palette.node_double_clicked.connect(self._add_node_center)
        palette_dock = QDockWidget("Node Library", self)
        palette_dock.setWidget(self._palette)
        palette_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        palette_dock.setStyleSheet("QDockWidget { color: #94a3b8; font-size: 11px; }")
        self.addDockWidget(Qt.LeftDockWidgetArea, palette_dock)

        # ── properties dock ───────────────────────────────────────────────────
        self._props = PropertiesPanel()
        props_dock = QDockWidget("Properties", self)
        props_dock.setWidget(self._props)
        props_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        props_dock.setStyleSheet("QDockWidget { color: #94a3b8; font-size: 11px; }")
        self.addDockWidget(Qt.RightDockWidgetArea, props_dock)

        # ── code-preview dock ─────────────────────────────────────────────────
        self._code_view = QTextEdit()
        self._code_view.setReadOnly(True)
        self._code_view.setStyleSheet(
            "background: #0d1117; color: #94a3b8;"
            "font-family: 'Cascadia Code', Consolas, monospace;"
            "font-size: 11px; border: none;"
        )
        code_dock = QDockWidget("Generated Plan", self)
        code_dock.setWidget(self._code_view)
        code_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        code_dock.setStyleSheet("QDockWidget { color: #94a3b8; font-size: 11px; }")
        self.addDockWidget(Qt.BottomDockWidgetArea, code_dock)
        code_dock.setFixedHeight(160)

        # ── status bar ────────────────────────────────────────────────────────
        sb = QStatusBar()
        sb.setStyleSheet(
            "background: #0d1117; color: #64748b; font-size: 11px; border-top: 1px solid #1e2535;"
        )
        self._re_label = QLabel("● RunEngine: IDLE")
        self._re_label.setStyleSheet("color: #64748b; margin: 0 8px;")
        sb.addPermanentWidget(self._re_label)
        self.setStatusBar(sb)
        sb.showMessage(
            "Double-click a node to add · Middle-drag to pan · Scroll to zoom · Shift+A to search"
        )

        self._build_toolbar()
        self._build_menu()

        # ── signals ───────────────────────────────────────────────────────────
        self._scene.selection_changed_node.connect(self._props.show_node)
        self._scene.graph_changed.connect(self._update_code_preview)
        self._view.request_add_node.connect(self._show_search_popup)

    # ── toolbar ───────────────────────────────────────────────────────────────
    def _build_toolbar(self):
        tb = QToolBar("Run", self)
        tb.setMovable(False)
        tb.setStyleSheet(_TOOLBAR_STYLE)
        self.addToolBar(Qt.TopToolBarArea, tb)

        tb.addWidget(QLabel("QS URL:"))
        self._qs_url = QLineEdit("http://localhost:60610")
        self._qs_url.setFixedWidth(200)
        self._qs_url.setToolTip("Bluesky Queue Server base URL")
        tb.addWidget(self._qs_url)
        tb.addSeparator()

        run_btn = QPushButton("▶  Submit to Queue Server")
        run_btn.setObjectName("run_btn")
        run_btn.setToolTip("Submit plan to bluesky-queueserver")
        run_btn.clicked.connect(self._run_plan)
        tb.addWidget(run_btn)

        copy_btn = QPushButton("⎘  Copy Code")
        copy_btn.setToolTip("Copy generated Python code to clipboard")
        copy_btn.clicked.connect(self._copy_code)
        tb.addWidget(copy_btn)

    # ── menu ──────────────────────────────────────────────────────────────────
    def _build_menu(self):
        mb = self.menuBar()
        mb.setStyleSheet(
            "QMenuBar { background: #0d1117; color: #94a3b8; font-size: 12px;"
            "           border-bottom: 1px solid #1e2535; }"
            "QMenuBar::item:selected { background: #1e2535; color: #e2e8f0; }"
            "QMenu { background: #141922; color: #94a3b8; border: 1px solid #1e2535; }"
            "QMenu::item:selected { background: #1e2535; color: #e2e8f0; }"
        )

        file_m = mb.addMenu("File")
        file_m.addAction(QAction("New",      self, shortcut=QKeySequence.New,  triggered=self._new_canvas))
        file_m.addAction(QAction("Open…",    self, shortcut=QKeySequence.Open, triggered=self._open_file))
        file_m.addAction(QAction("Save",     self, shortcut=QKeySequence.Save, triggered=self._save_file))
        file_m.addAction(QAction("Save As…", self, shortcut=QKeySequence("Ctrl+Shift+S"),
                                 triggered=self._save_file_as))
        file_m.addSeparator()
        file_m.addAction(QAction("Quit", self, shortcut=QKeySequence.Quit, triggered=self.close))

        edit_m = mb.addMenu("Edit")
        edit_m.addAction(QAction("Delete Selected", self, shortcut=QKeySequence.Delete,
                                 triggered=self._delete_selected))

        ex_m = mb.addMenu("Examples")
        ex_m.addAction(QAction("Simplified Energy Scan", self,
                               triggered=self._load_example_simple))
        ex_m.addAction(QAction("Complete Energy Scan (nested loops)", self,
                               triggered=self._load_example_full))

        run_m = mb.addMenu("Run")
        run_m.addAction(QAction("▶  Submit to Queue Server", self, triggered=self._run_plan))
        run_m.addAction(QAction("⎘  Copy Code",              self, triggered=self._copy_code))

    # ── search popup ──────────────────────────────────────────────────────────
    def _show_search_popup(self, scene_pos: QPointF):
        popup = NodeSearchPopup(self._view)
        view_pos = self._view.mapFromScene(scene_pos)
        popup.move(self._view.mapToGlobal(view_pos))
        popup.node_chosen.connect(lambda s: self._scene.add_node(s, scene_pos))
        popup.show()
        popup.activateWindow()
        popup.setFocus()

    def _add_node_center(self, schema: NodeSchema):
        center = self._view.mapToScene(self._view.viewport().rect().center())
        offset = len(self._scene.items()) * 10
        self._scene.add_node(schema, QPointF(center.x() + offset, center.y() + offset))

    # ── file I/O ──────────────────────────────────────────────────────────────
    def _new_canvas(self):
        if self._scene.items():
            r = QMessageBox.question(self, "New canvas",
                                     "Discard current canvas and start fresh?",
                                     QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                return
        self._scene._restore({"nodes": {}, "frames": {}, "wires": []})
        self._current_file = None
        self.setWindowTitle(_APP_NAME)

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open plan", "", "Plan Editor (*.plan.json);;JSON (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            self._scene.load_from_file(path)
            self._current_file = path
            self.setWindowTitle(f"{_APP_NAME} — {path}")
            self.statusBar().showMessage(f"Opened {path}", 4000)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def _save_file(self):
        if not self._current_file:
            self._save_file_as()
            return
        try:
            self._scene.save_to_file(self._current_file)
            self.statusBar().showMessage(f"Saved {self._current_file}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save plan", "", "Plan Editor (*.plan.json);;JSON (*.json);;All files (*)"
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".plan.json"
        try:
            self._scene.save_to_file(path)
            self._current_file = path
            self.setWindowTitle(f"{_APP_NAME} — {path}")
            self.statusBar().showMessage(f"Saved {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def _delete_selected(self):
        from plan_editor.canvas.loop_frame import LoopFrame
        sc = self._scene
        for item in list(sc.selectedItems()):
            if isinstance(item, LoopFrame):
                for p in item.input_ports + item.output_ports:
                    for w in list(p.wires):
                        w.remove()
                for vn in item._var_nodes:
                    if vn is not None and vn.scene():
                        for p in vn.input_ports + vn.output_ports:
                            for w in list(p.wires):
                                w.remove()
                        sc.removeItem(vn)
                sc.removeItem(item)
            elif isinstance(item, BaseNode):
                for p in item.input_ports + item.output_ports:
                    for w in list(p.wires):
                        w.remove()
                sc.removeItem(item)
        self._update_code_preview()

    # ── code preview ──────────────────────────────────────────────────────────
    def _update_code_preview(self):
        self._code_view.setPlainText(generate_plan_code(self._scene))

    def _copy_code(self):
        QApplication.clipboard().setText(generate_plan_code(self._scene))
        self.statusBar().showMessage("Plan code copied to clipboard.", 3000)

    # ── example loaders ───────────────────────────────────────────────────────
    def _confirm_replace(self, title: str) -> bool:
        if not self._scene.items():
            return True
        r = QMessageBox.question(self, "Load Example",
                                 "Replace current canvas with the example?",
                                 QMessageBox.Yes | QMessageBox.No)
        return r == QMessageBox.Yes

    def _load_example_simple(self):
        if not self._confirm_replace("Simplified Energy Scan"):
            return
        self._scene._restore({"nodes": {}, "frames": {}, "wires": []})
        self._current_file = None
        self.setWindowTitle(f"{_APP_NAME} — Simplified Energy Scan")
        examples.energy_scan_simple(self._scene, self._view)

    def _load_example_full(self):
        if not self._confirm_replace("Complete Energy Scan"):
            return
        self._scene._restore({"nodes": {}, "frames": {}, "wires": []})
        self._current_file = None
        self.setWindowTitle(f"{_APP_NAME} — Complete Energy Scan")
        examples.energy_scan_full(self._scene, self._view)

    # ── queue-server submission ───────────────────────────────────────────────
    def _run_plan(self):
        base_url = self._qs_url.text().rstrip("/")
        try:
            items = build_queue_items(self._scene)
        except Exception as exc:
            QMessageBox.critical(self, "Code generation error", str(exc))
            return
        if items:
            self._submit_items(base_url, items)
        else:
            self._submit_script(base_url, generate_plan_code(self._scene))

    def _submit_items(self, base_url: str, items: list[dict]):
        url    = f"{base_url}/api/queue/item/add"
        errors = []
        for item in items:
            payload = json.dumps({"item": item}).encode()
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status not in (200, 201):
                        errors.append(f"HTTP {resp.status} for {item['name']}")
            except urllib.error.URLError as exc:
                errors.append(str(exc.reason))
                break
        if errors:
            QMessageBox.warning(self, "Queue Server Error",
                                "Failed to submit some items:\n" + "\n".join(errors))
        else:
            self._re_label.setText("● RunEngine: QUEUED")
            self._re_label.setStyleSheet("color: #86efac; margin: 0 8px;")
            self.statusBar().showMessage(f"Submitted {len(items)} plan item(s).", 5000)

    def _submit_script(self, base_url: str, code: str):
        url     = f"{base_url}/api/script/upload"
        payload = json.dumps({"script": code}).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201):
                    self._re_label.setText("● RunEngine: SCRIPT UPLOADED")
                    self._re_label.setStyleSheet("color: #fbbf24; margin: 0 8px;")
                    self.statusBar().showMessage(
                        "Script uploaded. Add 'my_plan' to queue via QS client.", 6000)
                else:
                    raise urllib.error.URLError(f"HTTP {resp.status}")
        except urllib.error.URLError as exc:
            QMessageBox.warning(
                self, "Queue Server Unreachable",
                f"Could not reach {url}:\n{exc}\n\n"
                "Use '⎘ Copy Code' to copy the plan and run it manually.",
            )
