"""Voice Library tab: browse, download, rename, and delete Piper voice models."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QLineEdit, QComboBox, QPushButton, QProgressBar,
    QHeaderView, QMessageBox, QSplitter, QGroupBox, QInputDialog,
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
    models_changed = pyqtSignal()
    model_renamed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registry = None
        self._project = None
        self._available = []
        self._download_thread = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        lbl = QLabel("Voice Library")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        layout.addWidget(lbl)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Top panel: Installed Models ──────────────────────────
        installed_group = QGroupBox("Installed Models")
        installed_layout = QVBoxLayout(installed_group)

        self._installed_table = QTableWidget()
        self._installed_table.setColumnCount(7)
        self._installed_table.setHorizontalHeaderLabels(
            ["Name", "Language", "Quality", "Speakers", "Size", "", ""]
        )
        self._installed_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._installed_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._installed_table.verticalHeader().setVisible(False)
        self._installed_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        installed_layout.addWidget(self._installed_table)

        self._installed_status = QLabel("")
        installed_layout.addWidget(self._installed_status)

        splitter.addWidget(installed_group)

        # ── Bottom panel: Download Catalog ───────────────────────
        catalog_group = QGroupBox("Download Catalog")
        catalog_layout = QVBoxLayout(catalog_group)

        filter_row = QHBoxLayout()

        filter_row.addWidget(QLabel("Language:"))
        self._lang_filter = QComboBox()
        self._lang_filter.setEditable(True)
        self._lang_filter.setMinimumWidth(120)
        self._lang_filter.addItem("")
        self._lang_filter.addItems([
            "de", "en", "es", "fr", "it", "nl", "pl", "pt", "ru", "uk", "zh",
            "ar", "cs", "da", "el", "fi", "hu", "is", "ja", "ka", "ko",
            "nb", "ro", "sk", "sr", "sv", "sw", "tr", "vi",
        ])
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

        catalog_layout.addLayout(filter_row)

        self._catalog_table = QTableWidget()
        self._catalog_table.setColumnCount(7)
        self._catalog_table.setHorizontalHeaderLabels(
            ["Source", "Language", "Name", "Quality", "Speakers", "Size", ""]
        )
        self._catalog_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self._catalog_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._catalog_table.verticalHeader().setVisible(False)
        self._catalog_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        catalog_layout.addWidget(self._catalog_table)

        self._progress_row = QWidget()
        prog_layout = QHBoxLayout(self._progress_row)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        self._progress_label = QLabel("")
        prog_layout.addWidget(self._progress_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedHeight(20)
        prog_layout.addWidget(self._progress_bar, 1)
        self._progress_row.setVisible(False)
        catalog_layout.addWidget(self._progress_row)

        splitter.addWidget(catalog_group)

        splitter.setSizes([300, 400])
        layout.addWidget(splitter)

    def set_project(self, project):
        self._project = project

    def showEvent(self, event):
        super().showEvent(event)
        if self._registry is None:
            from slop.voices.model_registry import VoiceModelRegistry
            self._registry = VoiceModelRegistry()
        self._populate_installed_table()

    # ── Installed Models Panel ───────────────────────────────────

    def _populate_installed_table(self):
        if not self._registry:
            return
        installed = self._registry.list_installed()
        self._installed_table.setRowCount(len(installed))

        for row, model in enumerate(installed):
            self._installed_table.setItem(row, 0, QTableWidgetItem(model["name"]))
            self._installed_table.setItem(row, 1, QTableWidgetItem(model["language"]))
            self._installed_table.setItem(row, 2, QTableWidgetItem(model["quality"]))
            self._installed_table.setItem(row, 3, QTableWidgetItem(str(model["num_speakers"])))
            self._installed_table.setItem(
                row, 4, QTableWidgetItem(f"{model['size_mb']:.0f} MB")
            )

            rename_btn = QPushButton("Rename")
            rename_btn.setProperty("model_name", model["name"])
            rename_btn.clicked.connect(self._on_rename_clicked)
            self._installed_table.setCellWidget(row, 5, rename_btn)

            del_btn = QPushButton("Delete")
            del_btn.setProperty("model_name", model["name"])
            del_btn.clicked.connect(self._on_delete_clicked)
            del_btn.setStyleSheet("color: #f38ba8;")
            self._installed_table.setCellWidget(row, 6, del_btn)

        self._installed_status.setText(f"{len(installed)} voice model(s) installed")

    def _on_rename_clicked(self):
        btn = self.sender()
        if not btn:
            return
        old_name = btn.property("model_name")
        if not old_name:
            return

        new_name, ok = QInputDialog.getText(
            self, "Rename Voice Model",
            f"New name for '{old_name}':",
            text=old_name,
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return

        try:
            old_path, new_path = self._registry.rename_model(old_name, new_name.strip())
            self._populate_installed_table()
            self._apply_filters()
            self.model_renamed.emit(str(old_path), str(new_path))
            self.models_changed.emit()
        except (ValueError, FileNotFoundError, FileExistsError) as e:
            QMessageBox.warning(self, "Rename Failed", str(e))

    def _on_delete_clicked(self):
        btn = self.sender()
        if not btn:
            return
        model_name = btn.property("model_name")
        if not model_name:
            return

        in_use = []
        if self._project:
            for name, cfg in self._project.presenters.items():
                if Path(cfg.voice_model).stem == model_name:
                    in_use.append(name)

        msg = f"Delete voice model '{model_name}'?\nThis cannot be undone."
        if in_use:
            msg += f"\n\nThis model is used by: {', '.join(in_use)}\nTheir voice setting will be cleared."

        reply = QMessageBox.question(
            self, "Delete Voice Model", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if in_use and self._project:
                for name in in_use:
                    self._project.presenters[name].voice_model = ""

            self._registry.delete_model(model_name)
            self._populate_installed_table()
            self._apply_filters()
            self.models_changed.emit()
        except Exception as e:
            QMessageBox.warning(self, "Delete Failed", str(e))

    # ── Download Catalog Panel ───────────────────────────────────

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
        self._populate_catalog_table()

    def _populate_catalog_table(self):
        self._catalog_table.setRowCount(len(self._available))
        for row, voice in enumerate(self._available):
            self._catalog_table.setItem(row, 0, QTableWidgetItem(voice.get("source", "")))
            self._catalog_table.setItem(
                row, 1, QTableWidgetItem(voice.get("language", ""))
            )
            self._catalog_table.setItem(
                row, 2, QTableWidgetItem(voice.get("name", voice.get("key", "")))
            )
            self._catalog_table.setItem(
                row, 3, QTableWidgetItem(voice.get("quality", ""))
            )
            size = voice.get("size_mb", 0)
            self._catalog_table.setItem(
                row, 4, QTableWidgetItem(str(voice.get("num_speakers", 1)))
            )
            self._catalog_table.setItem(
                row, 5, QTableWidgetItem(f"{size:.0f} MB" if size else "?")
            )

            btn = QPushButton("Installed" if voice.get("installed") else "Download")
            btn.setEnabled(not voice.get("installed", False))
            btn.setProperty("voice_key", voice["key"])
            btn.clicked.connect(self._on_download_clicked)
            self._catalog_table.setCellWidget(row, 6, btn)

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
            mb_dl = downloaded // (1024 * 1024)
            mb_tot = total // (1024 * 1024)
            self._progress_label.setText(f"Downloading... {mb_dl} / {mb_tot} MB")

    def _on_download_done(self, path):
        self._download_thread = None
        self._progress_row.setVisible(False)
        self._populate_installed_table()
        self._apply_filters()
        self.models_changed.emit()

    def _on_download_error(self, msg):
        self._download_thread = None
        self._progress_row.setVisible(False)
        QMessageBox.warning(self, "Download Error", msg)
        self._apply_filters()
