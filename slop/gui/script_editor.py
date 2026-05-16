"""Script Editor tab: slide list with thumbnails + narration text editor."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPlainTextEdit, QLabel, QComboBox, QPushButton, QSplitter,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QIcon

from pathlib import Path


class ScriptEditor(QWidget):
    slide_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._thumbnails = []
        self._current_idx = -1
        self._updating = False
        self._player = None
        self._preview_wav_path = None
        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(250)
        self._playback_timer.timeout.connect(self._check_playback)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: slide list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("Slides")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(lbl)

        self._slide_list = QListWidget()
        self._slide_list.setIconSize(self._slide_list.iconSize().__class__(160, 120))
        self._slide_list.currentRowChanged.connect(self._on_slide_selected)
        left_layout.addWidget(self._slide_list)

        splitter.addWidget(left)

        # Right: editor
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Preview thumbnail
        self._preview_label = QLabel()
        self._preview_label.setFixedHeight(300)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("background: #181825; border-radius: 8px;")
        right_layout.addWidget(self._preview_label)

        # Presenter selector
        pres_row = QHBoxLayout()
        pres_row.addWidget(QLabel("Presenter:"))
        self._presenter_combo = QComboBox()
        self._presenter_combo.currentTextChanged.connect(self._on_presenter_changed)
        pres_row.addWidget(self._presenter_combo, 1)
        right_layout.addLayout(pres_row)

        # Narration text
        right_layout.addWidget(QLabel("Narration Text:"))
        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlaceholderText("Enter narration text for this slide...")
        self._text_edit.textChanged.connect(self._on_text_changed)
        right_layout.addWidget(self._text_edit, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        self._preview_btn = QPushButton("Preview Audio")
        self._preview_btn.clicked.connect(self._on_preview_audio)
        btn_row.addWidget(self._preview_btn)

        self._regen_btn = QPushButton("Regenerate Audio")
        self._regen_btn.clicked.connect(self._on_regenerate_audio)
        btn_row.addWidget(self._regen_btn)

        btn_row.addStretch()

        word_count_label = QLabel("")
        self._word_count = word_count_label
        btn_row.addWidget(word_count_label)

        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([250, 600])
        layout.addWidget(splitter)

    def load_project(self, project):
        self._project = project
        self._updating = True
        self._slide_list.clear()
        self._thumbnails = []

        pdf_path = project.resolved_pdf_path
        if pdf_path.exists():
            from slop.engine.pdf_renderer import render_slide_thumbnail
            for i in range(len(project.slides)):
                try:
                    png_bytes = render_slide_thumbnail(pdf_path, i, max_width=160)
                    pm = QPixmap()
                    pm.loadFromData(png_bytes)
                    self._thumbnails.append(pm)
                except Exception:
                    self._thumbnails.append(QPixmap())

        for i, slide in enumerate(project.slides):
            item = QListWidgetItem(f"Slide {i + 1}")
            if i < len(self._thumbnails) and not self._thumbnails[i].isNull():
                item.setIcon(QIcon(self._thumbnails[i]))
            pname = slide.presenter or "—"
            item.setText(f"Slide {i + 1}  [{pname}]")
            self._slide_list.addItem(item)

        self._update_presenter_combo()
        self._updating = False

        if self._slide_list.count() > 0:
            self._slide_list.setCurrentRow(0)

    def _update_presenter_combo(self):
        self._presenter_combo.blockSignals(True)
        self._presenter_combo.clear()
        self._presenter_combo.addItem("— None —")
        if self._project:
            for name in self._project.presenters:
                self._presenter_combo.addItem(name)
        self._presenter_combo.blockSignals(False)

    def refresh_presenters(self):
        current = self._presenter_combo.currentText()
        self._update_presenter_combo()
        idx = self._presenter_combo.findText(current)
        if idx >= 0:
            self._presenter_combo.setCurrentIndex(idx)

    def _on_slide_selected(self, row):
        if row < 0 or not self._project or row >= len(self._project.slides):
            return
        self.stop_audio()
        self._current_idx = row
        self._updating = True

        slide = self._project.slides[row]

        # Show larger preview
        if row < len(self._thumbnails) and not self._thumbnails[row].isNull():
            from slop.engine.pdf_renderer import render_slide_thumbnail
            try:
                png = render_slide_thumbnail(self._project.resolved_pdf_path, row, max_width=500)
                pm = QPixmap()
                pm.loadFromData(png)
                self._preview_label.setPixmap(pm.scaled(
                    self._preview_label.width(), self._preview_label.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
            except Exception:
                self._preview_label.setText(f"Slide {row + 1}")
        else:
            self._preview_label.setText(f"Slide {row + 1}")

        # Set presenter
        idx = self._presenter_combo.findText(slide.presenter)
        self._presenter_combo.setCurrentIndex(idx if idx >= 0 else 0)

        # Set text
        self._text_edit.setPlainText(slide.text)
        self._update_word_count()

        self._updating = False

    def _on_presenter_changed(self, name):
        if self._updating or self._current_idx < 0 or not self._project:
            return
        presenter = name if name != "— None —" else ""
        self._project.slides[self._current_idx].presenter = presenter
        item = self._slide_list.item(self._current_idx)
        pname = presenter or "—"
        item.setText(f"Slide {self._current_idx + 1}  [{pname}]")
        self.slide_changed.emit()

    def _on_text_changed(self):
        if self._updating or self._current_idx < 0 or not self._project:
            return
        self._project.slides[self._current_idx].text = self._text_edit.toPlainText()
        self._update_word_count()
        self.slide_changed.emit()

    def _update_word_count(self):
        text = self._text_edit.toPlainText()
        words = len(text.split()) if text.strip() else 0
        self._word_count.setText(f"{words} words")

    def stop_audio(self):
        if self._player:
            self._player.stop()
        self._playback_timer.stop()
        self._preview_btn.setText("Preview Audio")
        self._cleanup_preview_wav()

    def _cleanup_preview_wav(self):
        if self._preview_wav_path:
            try:
                p = Path(self._preview_wav_path)
                if p.exists():
                    p.unlink()
            except Exception:
                pass
            self._preview_wav_path = None

    def _check_playback(self):
        if not self._player or not self._player.is_playing():
            self._playback_timer.stop()
            self._preview_btn.setText("Preview Audio")
            self._cleanup_preview_wav()

    def _on_preview_audio(self):
        if self._current_idx < 0 or not self._project:
            return

        if self._player and self._player.is_playing():
            self._player.stop()
            self._preview_btn.setText("Preview Audio")
            return

        slide = self._project.slides[self._current_idx]
        if not slide.text.strip():
            QMessageBox.information(self, "Preview", "No text to preview.")
            return
        if not slide.presenter or slide.presenter not in self._project.presenters:
            QMessageBox.information(self, "Preview", "No presenter assigned to this slide.")
            return

        try:
            from slop.engine.tts import TTSEngine
            from slop.engine.audio_player import AudioPlayer

            presenter = self._project.presenters[slide.presenter]
            engine = TTSEngine(self._project.base_dir / "voices")
            tts_params = {
                "length_scale": presenter.length_scale,
                "noise_scale": presenter.noise_scale,
                "noise_w_scale": presenter.noise_w_scale,
            }
            if presenter.speaker_id is not None:
                tts_params["speaker_id"] = presenter.speaker_id

            wav_path = engine.preview_text(
                slide.text,
                str(self._project.resolve_voice_model(slide.presenter)),
                tts_params,
            )
            self._cleanup_preview_wav()
            self._preview_wav_path = str(wav_path)
            if not self._player:
                self._player = AudioPlayer()
            self._player.play(wav_path)
            self._preview_btn.setText("Stop Audio")
            self._playback_timer.start()
        except Exception as e:
            QMessageBox.warning(self, "Preview Error", str(e))

    def _on_regenerate_audio(self):
        if self._current_idx < 0 or not self._project:
            return
        slide = self._project.slides[self._current_idx]
        if not slide.text.strip() or not slide.presenter:
            return

        try:
            from slop.engine.tts import TTSEngine

            presenter = self._project.presenters[slide.presenter]
            engine = TTSEngine(self._project.base_dir / "voices")
            tts_params = {
                "length_scale": presenter.length_scale,
                "noise_scale": presenter.noise_scale,
                "noise_w_scale": presenter.noise_w_scale,
            }
            if presenter.speaker_id is not None:
                tts_params["speaker_id"] = presenter.speaker_id

            engine.generate_slide(
                self._current_idx,
                slide.text,
                str(self._project.resolve_voice_model(slide.presenter)),
                tts_params,
                self._project.cache_dir,
                force=True,
            )
            QMessageBox.information(self, "Done", f"Audio regenerated for slide {self._current_idx + 1}.")
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
