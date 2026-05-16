"""Presenter Manager tab: CRUD for presenters with voice, color, GIF settings."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QComboBox, QPushButton, QGroupBox,
    QSplitter, QMessageBox, QInputDialog, QFormLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QIcon
from pathlib import Path

from slop.gui.widgets import ColorPickerButton, LabeledSlider, GifPreviewWidget
from slop.project import PresenterConfig


class PresenterManager(QWidget):
    presenters_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._current_name = None
        self._updating = False
        self._player = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: presenter list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("Presenters")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(lbl)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selected)
        left_layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("+ Add")
        self._add_btn.clicked.connect(self._on_add)
        btn_row.addWidget(self._add_btn)
        self._del_btn = QPushButton("Delete")
        self._del_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._del_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left)

        # Right: editor
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self._editor_stack = QWidget()
        editor_layout = QVBoxLayout(self._editor_stack)

        # Name + title
        identity = QGroupBox("Identity")
        id_layout = QFormLayout(identity)
        self._name_edit = QLineEdit()
        self._name_edit.editingFinished.connect(self._on_name_changed)
        id_layout.addRow("Name:", self._name_edit)
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("e.g. Der Ernste")
        self._title_edit.textChanged.connect(self._on_field_changed)
        id_layout.addRow("Title:", self._title_edit)
        editor_layout.addWidget(identity)

        # Voice settings
        voice_group = QGroupBox("Voice")
        voice_layout = QFormLayout(voice_group)

        self._voice_combo = QComboBox()
        self._voice_combo.currentTextChanged.connect(self._on_field_changed)
        voice_layout.addRow("Model:", self._voice_combo)

        self._speaker_combo = QComboBox()
        self._speaker_combo.currentTextChanged.connect(self._on_field_changed)
        self._speaker_label = QLabel("Speaker:")
        voice_layout.addRow(self._speaker_label, self._speaker_combo)

        self._length_slider = LabeledSlider("Speed", 0.5, 2.0, 1.0, 0.01)
        self._length_slider.value_changed.connect(lambda v: self._on_field_changed())
        voice_layout.addRow(self._length_slider)

        self._noise_slider = LabeledSlider("Expression", 0.0, 1.0, 0.667, 0.01)
        self._noise_slider.value_changed.connect(lambda v: self._on_field_changed())
        voice_layout.addRow(self._noise_slider)

        self._noise_w_slider = LabeledSlider("Duration Var", 0.0, 1.0, 0.8, 0.01)
        self._noise_w_slider.value_changed.connect(lambda v: self._on_field_changed())
        voice_layout.addRow(self._noise_w_slider)

        preview_row = QHBoxLayout()
        self._preview_voice_btn = QPushButton("Preview Voice")
        self._preview_voice_btn.clicked.connect(self._on_preview_voice)
        preview_row.addWidget(self._preview_voice_btn)
        preview_row.addStretch()
        voice_layout.addRow(preview_row)

        editor_layout.addWidget(voice_group)

        # Appearance
        appear_group = QGroupBox("Appearance")
        appear_layout = QFormLayout(appear_group)

        color_row = QHBoxLayout()
        self._color_btn = ColorPickerButton()
        self._color_btn.color_changed.connect(lambda c: self._on_field_changed())
        color_row.addWidget(self._color_btn)
        color_row.addStretch()
        appear_layout.addRow("Color:", color_row)

        self._gif_mode_combo = QComboBox()
        self._gif_mode_combo.addItems(["tint", "solid", "none"])
        self._gif_mode_combo.currentTextChanged.connect(self._on_field_changed)
        appear_layout.addRow("Avatar Mode:", self._gif_mode_combo)

        self._gif_preview = GifPreviewWidget()
        appear_layout.addRow(self._gif_preview)

        editor_layout.addWidget(appear_group)
        editor_layout.addStretch()

        right_layout.addWidget(self._editor_stack)
        self._editor_stack.setEnabled(False)

        splitter.addWidget(right)
        splitter.setSizes([200, 500])
        layout.addWidget(splitter)

    def load_project(self, project):
        self._project = project
        self._refresh_list()
        self._refresh_voice_models()

    def _refresh_list(self):
        self._updating = True
        self._list.clear()
        if not self._project:
            return
        for name, cfg in self._project.presenters.items():
            item = QListWidgetItem(name)
            r, g, b = cfg.color
            pm = QPixmap(16, 16)
            pm.fill(QColor(r, g, b))
            item.setIcon(QIcon(pm))
            self._list.addItem(item)
        self._updating = False
        if self._list.count() > 0:
            self._list.setCurrentRow(0)
        else:
            self._editor_stack.setEnabled(False)

    def _refresh_voice_models(self):
        self._voice_combo.blockSignals(True)
        self._voice_combo.clear()
        try:
            from slop.voices.model_registry import VoiceModelRegistry
            registry = VoiceModelRegistry()
            for m in registry.list_installed():
                self._voice_combo.addItem(m["name"], m["path"])
        except Exception:
            pass
        self._voice_combo.blockSignals(False)

    def _select_voice_model(self, model_path: str) -> None:
        if not model_path:
            return

        candidate = Path(model_path)
        if self._project and not candidate.is_absolute():
            candidate = self._project.base_dir / candidate

        candidate_str = str(candidate)
        candidate_name = candidate.stem

        for i in range(self._voice_combo.count()):
            item_path = self._voice_combo.itemData(i)
            item_name = self._voice_combo.itemText(i)
            if item_path == candidate_str or item_name == candidate_name:
                self._voice_combo.setCurrentIndex(i)
                return

        suffix = "current" if candidate.exists() else "missing"
        self._voice_combo.addItem(f"{candidate_name} ({suffix})", candidate_str)
        self._voice_combo.setCurrentIndex(self._voice_combo.count() - 1)

    def _on_selected(self, row):
        if row < 0 or not self._project or self._updating:
            return
        names = list(self._project.presenters.keys())
        if row >= len(names):
            return
        name = names[row]
        self._current_name = name
        cfg = self._project.presenters[name]
        self._editor_stack.setEnabled(True)
        self._updating = True

        self._name_edit.setText(name)
        self._title_edit.setText(cfg.title)

        # Voice model
        self._select_voice_model(cfg.voice_model)

        self._update_speaker_ids()
        if cfg.speaker_id is not None:
            for i in range(self._speaker_combo.count()):
                if self._speaker_combo.itemData(i) == cfg.speaker_id:
                    self._speaker_combo.setCurrentIndex(i)
                    break

        self._length_slider.value = cfg.length_scale
        self._noise_slider.value = cfg.noise_scale
        self._noise_w_slider.value = cfg.noise_w_scale

        self._color_btn.color = cfg.color
        idx = self._gif_mode_combo.findText(cfg.gif_mode)
        if idx >= 0:
            self._gif_mode_combo.setCurrentIndex(idx)

        # GIF preview
        if self._project.resolved_gif_path and self._project.resolved_gif_path.exists():
            self._gif_preview.load_gif(
                str(self._project.resolved_gif_path),
                tint_color=cfg.color if cfg.gif_mode == "tint" else None,
                target_color=self._project.gif.target_color,
                tolerance=self._project.gif.tolerance,
            )

        self._updating = False

    def _update_speaker_ids(self):
        self._speaker_combo.blockSignals(True)
        self._speaker_combo.clear()
        self._speaker_combo.addItem("Default", None)

        voice_path = self._voice_combo.currentData()
        if voice_path:
            try:
                from slop.voices.model_registry import VoiceModelRegistry
                registry = VoiceModelRegistry()
                info = registry.get_installed_model(Path(str(voice_path)).stem)
                if info and info.get("speaker_id_map"):
                    for speaker_name, sid in info["speaker_id_map"].items():
                        self._speaker_combo.addItem(speaker_name, sid)
            except Exception:
                pass

        has_speakers = self._speaker_combo.count() > 1
        self._speaker_combo.setVisible(has_speakers)
        self._speaker_label.setVisible(has_speakers)
        self._speaker_combo.blockSignals(False)

    def _on_name_changed(self):
        if self._updating or not self._current_name or not self._project:
            return
        new_name = self._name_edit.text().strip()
        if not new_name or new_name == self._current_name:
            return
        if new_name in self._project.presenters:
            QMessageBox.warning(self, "Duplicate", f"Presenter '{new_name}' already exists.")
            self._name_edit.setText(self._current_name)
            return

        cfg = self._project.presenters.pop(self._current_name)
        cfg.name = new_name
        self._project.presenters[new_name] = cfg

        for slide in self._project.slides:
            if slide.presenter == self._current_name:
                slide.presenter = new_name

        self._current_name = new_name
        row = self._list.currentRow()
        self._list.item(row).setText(new_name)
        self.presenters_changed.emit()

    def _on_field_changed(self, *_):
        if self._updating or not self._current_name or not self._project:
            return
        cfg = self._project.presenters.get(self._current_name)
        if not cfg:
            return

        cfg.title = self._title_edit.text()

        voice_path = self._voice_combo.currentData()
        if voice_path:
            try:
                rel = Path(str(voice_path)).relative_to(self._project.base_dir)
                cfg.voice_model = str(rel)
            except ValueError:
                cfg.voice_model = str(voice_path)

        speaker_data = self._speaker_combo.currentData()
        cfg.speaker_id = speaker_data

        cfg.length_scale = self._length_slider.value
        cfg.noise_scale = self._noise_slider.value
        cfg.noise_w_scale = self._noise_w_slider.value
        cfg.color = self._color_btn.color
        cfg.gif_mode = self._gif_mode_combo.currentText()

        # Update list icon color
        row = self._list.currentRow()
        if row >= 0:
            r, g, b = cfg.color
            pm = QPixmap(16, 16)
            pm.fill(QColor(r, g, b))
            self._list.item(row).setIcon(QIcon(pm))

        self.presenters_changed.emit()

    def _on_add(self):
        if not self._project:
            return
        name, ok = QInputDialog.getText(self, "Add Presenter", "Presenter name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if name in self._project.presenters:
            QMessageBox.warning(self, "Duplicate", f"'{name}' already exists.")
            return

        self._project.presenters[name] = PresenterConfig(name=name)
        self._refresh_list()
        self._list.setCurrentRow(self._list.count() - 1)
        self.presenters_changed.emit()

    def _on_delete(self):
        if not self._current_name or not self._project:
            return
        reply = QMessageBox.question(
            self, "Delete Presenter",
            f"Delete presenter '{self._current_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        del self._project.presenters[self._current_name]
        for slide in self._project.slides:
            if slide.presenter == self._current_name:
                slide.presenter = ""

        self._current_name = None
        self._refresh_list()
        self.presenters_changed.emit()

    def _on_preview_voice(self):
        if not self._current_name or not self._project:
            return

        if self._player and self._player.is_playing():
            self._player.stop()
            self._preview_voice_btn.setText("Preview Voice")
            return

        cfg = self._project.presenters.get(self._current_name)
        if not cfg or not cfg.voice_model:
            QMessageBox.information(self, "Preview", "No voice model selected.")
            return

        try:
            from slop.engine.tts import TTSEngine
            from slop.engine.audio_player import AudioPlayer

            engine = TTSEngine(self._project.base_dir / "voices")
            tts_params = {
                "length_scale": cfg.length_scale,
                "noise_scale": cfg.noise_scale,
                "noise_w_scale": cfg.noise_w_scale,
            }
            if cfg.speaker_id is not None:
                tts_params["speaker_id"] = cfg.speaker_id

            text = f"Hallo, mein Name ist {self._current_name}. Ich bin bereit zu präsentieren."
            wav = engine.preview_text(text, str(self._project.resolve_voice_model(self._current_name)), tts_params)
            if not self._player:
                self._player = AudioPlayer()
            self._player.play(wav)
            self._preview_voice_btn.setText("Stop Voice")
        except Exception as e:
            QMessageBox.warning(self, "Preview Error", str(e))
