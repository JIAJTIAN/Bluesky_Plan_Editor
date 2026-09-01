import sys

from PySide6.QtWidgets import QApplication

from plan_editor.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Bluesky Plan Editor")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
