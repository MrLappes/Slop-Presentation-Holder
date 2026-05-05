"""QApplication bootstrap for Slop Presentation Holder."""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont


def run():
    app = QApplication(sys.argv)
    app.setApplicationName("Slop Presentation Holder")
    app.setStyle("Fusion")

    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    app.setStyleSheet("""
        QMainWindow { background-color: #1e1e2e; }
        QTabWidget::pane { border: 1px solid #313244; background: #1e1e2e; }
        QTabBar::tab {
            background: #313244; color: #cdd6f4; padding: 8px 20px;
            border: none; border-bottom: 2px solid transparent;
            min-width: 120px;
        }
        QTabBar::tab:selected { background: #1e1e2e; border-bottom: 2px solid #89b4fa; color: #89b4fa; }
        QTabBar::tab:hover { background: #45475a; }
        QToolBar { background: #181825; border: none; spacing: 6px; padding: 4px; }
        QPushButton {
            background: #313244; color: #cdd6f4; border: 1px solid #45475a;
            padding: 6px 16px; border-radius: 4px;
        }
        QPushButton:hover { background: #45475a; }
        QPushButton:pressed { background: #585b70; }
        QPushButton#presentBtn { background: #a6e3a1; color: #1e1e2e; font-weight: bold; font-size: 13px; }
        QPushButton#presentBtn:hover { background: #94e2d5; }
        QLabel { color: #cdd6f4; }
        QPlainTextEdit, QTextEdit {
            background: #313244; color: #cdd6f4; border: 1px solid #45475a;
            border-radius: 4px; padding: 4px; font-family: monospace; font-size: 11px;
        }
        QListWidget {
            background: #313244; color: #cdd6f4; border: 1px solid #45475a;
            border-radius: 4px; outline: none;
        }
        QListWidget::item { padding: 6px; border-bottom: 1px solid #45475a; }
        QListWidget::item:selected { background: #45475a; }
        QComboBox {
            background: #313244; color: #cdd6f4; border: 1px solid #45475a;
            padding: 4px 8px; border-radius: 4px;
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView { background: #313244; color: #cdd6f4; selection-background-color: #45475a; }
        QSlider::groove:horizontal { background: #45475a; height: 6px; border-radius: 3px; }
        QSlider::handle:horizontal {
            background: #89b4fa; width: 14px; margin: -4px 0; border-radius: 7px;
        }
        QTableWidget {
            background: #313244; color: #cdd6f4; border: 1px solid #45475a;
            gridline-color: #45475a;
        }
        QTableWidget::item:selected { background: #45475a; }
        QHeaderView::section { background: #181825; color: #a6adc8; border: none; padding: 6px; }
        QLineEdit {
            background: #313244; color: #cdd6f4; border: 1px solid #45475a;
            padding: 4px 8px; border-radius: 4px;
        }
        QProgressBar {
            background: #313244; border: 1px solid #45475a; border-radius: 4px;
            text-align: center; color: #cdd6f4;
        }
        QProgressBar::chunk { background: #89b4fa; border-radius: 3px; }
        QGroupBox {
            color: #a6adc8; border: 1px solid #45475a; border-radius: 6px;
            margin-top: 8px; padding-top: 16px;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
        QScrollBar:vertical {
            background: #1e1e2e; width: 10px; border: none;
        }
        QScrollBar::handle:vertical { background: #45475a; border-radius: 5px; min-height: 20px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    """)

    from slop.gui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
