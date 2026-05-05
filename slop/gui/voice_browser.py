"""Voice Library tab: browse, filter, and download Piper voice models."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QLineEdit, QComboBox, QPushButton, QProgressBar,
    QHeaderView, QMessageBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


class DownloadThread(QThread):
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, registry, key, local_name=None):
        super().__init__()
        self._registry = registry
        self._key = key
        self._local_name = local_name

    def run(self):
        try:
            path = self._registry.download_model(
                self._key,
                local_name=self._local_name,
                progress_callback=lambda dl, total: self.progress.emit(dl, total),
            )
            self.finished_ok.emit(str(path))
        except Exception as e:
            self.error.emit(str(e))


class VoiceBrowser(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registry = None
        self._available = []
        self._download_thread = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        lbl = QLabel("Voice Library")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        layout.addWidget(lbl)

        # Filters
        filter_row = QHBoxLayout()

        filter_row.addWidget(QLabel("Language:"))
        self._lang_filter = QComboBox()
        self._lang_filter.setEditable(True)
        self._lang_filter.setMinimumWidth(120)
        self._lang_filter.addItem("")
        self._lang_filter.addItems(["de", "en", "es", "fr", "it", "nl", "pl", "pt", "ru", "uk", "zh"])
        self._lang_filter.currentTextChanged.connect(self._apply_filters)
        filter_row.addWidget(self._lang_filter)

        filter_row.addWidget(QLabel("Quality:"))
        self._quality_filter = QComboBox()
        self._quality_filter.addItems(["", "high", "medium", "low", "x_low"])
        self._quality_filter.currentTextChanged.connect(self._apply_filters)
        filter_row.addWidget(self._quality_filter)

        filter_row.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by name...")
        self._search.textChanged.connect(self._apply_filters)
        filter_row.addWidget(self._search, 1)

        self._refresh_btn = QPushButton("Refresh Catalog")
        self._refresh_btn.clicked.connect(self._load_catalog)
        filter_row.addWidget(self._refresh_btn)

        layout.addLayout(filter_row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["Language", "Name", "Quality", "Speakers", "Size", ""])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        # Progress
        self._progress_row = QWidget()
        prog_layout = QHBoxLayout(self._progress_row)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_label = QLabel("")
        prog_layout.addWidget(self._progress_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(20)
        prog_layout.addWidget(self._progress_bar, 1)
        self._progress_row.setVisible(False)
        layout.addWidget(self._progress_row)

        # Installed count
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

    def showEvent(self, event):
        super().showEvent(event)
        if self._registry is None:
            from slop.voices.model_registry import VoiceModelRegistry
            self._registry = VoiceModelRegistry()
            self._update_installed_count()

    def _load_catalog(self):
        if not self._registry:
            from slop.voices.model_registry import VoiceModelRegistry
            self._registry = VoiceModelRegistry()

        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Loading...")

        try:
            self._registry.fetch_catalog(force=True)
            self._apply_filters()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load catalog: {e}")
        finally:
            self._refresh_btn.setEnabled(True)
            self._refresh_btn.setText("Refresh Catalog")

    def _apply_filters(self):
        if not self._registry:
            return

        lang = self._lang_filter.currentText().strip()
        quality = self._quality_filter.currentText().strip()
        search = self._search.text().strip()

        self._available = self._registry.list_available(lang, quality, search)
        self._populate_table()

    def _populate_table(self):
        self._table.setRowCount(len(self._available))
        for row, voice in enumerate(self._available):
            self._table.setItem(row, 0, QTableWidgetItem(voice.get("language", "")))
            self._table.setItem(row, 1, QTableWidgetItem(voice.get("name", voice.get("key", ""))))
            self._table.setItem(row, 2, QTableWidgetItem(voice.get("quality", "")))
            self._table.setItem(row, 3, QTableWidgetItem(str(voice.get("num_speakers", 1))))
            size = voice.get("size_mb", 0)
            self._table.setItem(row, 4, QTableWidgetItem(f"{size:.0f} MB" if size else "?"))

            btn = QPushButton("Installed" if voice.get("installed") else "Download")
            btn.setEnabled(not voice.get("installed", False))
            btn.setProperty("voice_key", voice["key"])
            btn.clicked.connect(self._on_download_clicked)
            self._table.setCellWidget(row, 5, btn)

        self._update_installed_count()

    def _on_download_clicked(self):
        btn = self.sender()
        if not btn:
            return
        key = btn.property("voice_key")
        if not key or self._download_thread is not None:
            return

        btn.setEnabled(False)
        btn.setText("Downloading...")

        self._progress_row.setVisible(True)
        self._progress_label.setText(f"Downloading {key}...")
        self._progress_bar.setValue(0)

        self._download_thread = DownloadThread(self._registry, key)
        self._download_thread.progress.connect(self._on_download_progress)
        self._download_thread.finished_ok.connect(self._on_download_done)
        self._download_thread.error.connect(self._on_download_error)
        self._download_thread.start()

    def _on_download_progress(self, downloaded, total):
        if total > 0:
            pct = int(downloaded * 100 / total)
            self._progress_bar.setValue(pct)
            self._progress_label.setText(f"Downloading... {downloaded // (1024*1024)} / {total // (1024*1024)} MB")

    def _on_download_done(self, path):
        self._download_thread = None
        self._progress_row.setVisible(False)
        self._apply_filters()
        self._update_installed_count()

    def _on_download_error(self, msg):
        self._download_thread = None
        self._progress_row.setVisible(False)
        QMessageBox.warning(self, "Download Error", msg)
        self._apply_filters()

    def _update_installed_count(self):
        if not self._registry:
            return
        installed = self._registry.list_installed()
        self._status_label.setText(f"{len(installed)} voice model(s) installed")
