"""Main application window with toolbar and tabbed panels."""

import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar, QPushButton, QFileDialog,
    QMessageBox, QProgressDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence

from slop.project import SlopProject, SlideConfig
from slop.constants import TEMPLATES_DIR
from slop.gui.script_editor import ScriptEditor
from slop.gui.presenter_manager import PresenterManager
from slop.gui.voice_browser import VoiceBrowser


class AudioGenThread(QThread):
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, project):
        super().__init__()
        self._project = project

    def run(self):
        try:
            from slop.engine.tts import TTSEngine
            engine_dict = self._project.to_engine_dict()
            engine = TTSEngine(self._project.base_dir / "voices")
            engine.generate_all(
                engine_dict["slides"],
                engine_dict["presenters"],
                Path(engine_dict["cache_dir"]),
                progress_callback=lambda cur, tot: self.progress.emit(cur, tot),
            )
            self.finished_ok.emit()
        except Exception as e:
            self.error.emit(str(e))


class MP4ExportThread(QThread):
    progress = pyqtSignal(int, int, str)
    finished_ok = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, project, output_path, width=1920, height=1080, fps=30):
        super().__init__()
        self._project = project
        self._output_path = output_path
        self._width = width
        self._height = height
        self._fps = fps
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            from slop.engine.video_export import export_mp4
            engine_dict = self._project.to_engine_dict()
            export_mp4(
                engine_dict,
                Path(self._output_path),
                width=self._width,
                height=self._height,
                fps=self._fps,
                progress_callback=lambda cur, tot, msg: self.progress.emit(cur, tot, msg),
                abort_flag=lambda: self._abort,
            )
            self.finished_ok.emit(self._output_path)
        except InterruptedError:
            pass
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Slop Presentation Holder")
        self.resize(1100, 750)

        self._project = None
        self._project_path = None
        self._unsaved = False
        self._gen_thread = None
        self._export_thread = None

        self._build_toolbar()
        self._build_tabs()
        self._update_title()

    def _build_toolbar(self):
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_act = QAction("New", self)
        new_act.setShortcut(QKeySequence("Ctrl+N"))
        new_act.triggered.connect(self._on_new)
        toolbar.addAction(new_act)

        open_act = QAction("Open", self)
        open_act.setShortcut(QKeySequence("Ctrl+O"))
        open_act.triggered.connect(self._on_open)
        toolbar.addAction(open_act)

        save_act = QAction("Save", self)
        save_act.setShortcut(QKeySequence("Ctrl+S"))
        save_act.triggered.connect(self._on_save)
        toolbar.addAction(save_act)

        save_as_act = QAction("Save As", self)
        save_as_act.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_act.triggered.connect(self._on_save_as)
        toolbar.addAction(save_as_act)

        toolbar.addSeparator()

        export_act = QAction("Export Prompt", self)
        export_act.triggered.connect(self._on_export_prompt)
        toolbar.addAction(export_act)

        gen_act = QAction("Generate Audio", self)
        gen_act.triggered.connect(self._on_generate_all_audio)
        toolbar.addAction(gen_act)

        export_mp4_act = QAction("Export MP4", self)
        export_mp4_act.triggered.connect(self._on_export_mp4)
        toolbar.addAction(export_mp4_act)

        toolbar.addSeparator()

        spacer = QToolBar()
        spacer.setStyleSheet("background: transparent; border: none;")
        toolbar.addWidget(spacer)

        present_btn = QPushButton("  Present  ")
        present_btn.setObjectName("presentBtn")
        present_btn.clicked.connect(self._on_present)
        toolbar.addWidget(present_btn)

    def _build_tabs(self):
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        self._script_editor = ScriptEditor()
        self._script_editor.slide_changed.connect(self._mark_dirty)
        self._tabs.addTab(self._script_editor, "Script Editor")

        self._presenter_mgr = PresenterManager()
        self._presenter_mgr.presenters_changed.connect(self._on_presenters_changed)
        self._tabs.addTab(self._presenter_mgr, "Presenters")

        self._voice_browser = VoiceBrowser()
        self._tabs.addTab(self._voice_browser, "Voice Library")

    def _mark_dirty(self):
        self._unsaved = True
        self._update_title()

    def _update_title(self):
        name = self._project.name if self._project else "No Project"
        dirty = " *" if self._unsaved else ""
        self.setWindowTitle(f"Slop Presentation Holder — {name}{dirty}")

    def _load_project(self, project):
        self._project = project
        self._unsaved = False
        self._update_title()
        self._script_editor.load_project(project)
        self._presenter_mgr.load_project(project)

    def _on_presenters_changed(self):
        self._mark_dirty()
        self._script_editor.refresh_presenters()

    # ── File operations ──────────────────────────────────────────

    def _on_new(self):
        if not self._confirm_discard():
            return

        pdf_path, _ = QFileDialog.getOpenFileName(
            self, "Select PDF", "", "PDF Files (*.pdf)"
        )
        if not pdf_path:
            return

        from slop.engine.pdf_renderer import get_slide_count
        count = get_slide_count(Path(pdf_path))

        project = SlopProject(
            name=Path(pdf_path).stem,
            pdf_path=pdf_path,
            slides=[SlideConfig() for _ in range(count)],
        )
        self._project_path = None
        self._load_project(project)
        self._mark_dirty()

    def _on_open(self):
        if not self._confirm_discard():
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", str(TEMPLATES_DIR),
            "Slop Projects (*.json);;All Files (*)",
        )
        if not path:
            return

        try:
            project = SlopProject.load(Path(path))
            self._project_path = path
            self._load_project(project)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")

    def _on_save(self):
        if not self._project:
            return
        if not self._project_path:
            self._on_save_as()
            return
        try:
            self._project.save(Path(self._project_path))
            self._unsaved = False
            self._update_title()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def _on_save_as(self):
        if not self._project:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", self._project.name + ".json",
            "Slop Projects (*.json)",
        )
        if not path:
            return
        self._project_path = path
        self._on_save()

    def _confirm_discard(self):
        if not self._unsaved:
            return True
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    # ── Export prompt template ───────────────────────────────────

    def _on_export_prompt(self):
        if not self._project:
            QMessageBox.information(self, "Export", "No project loaded.")
            return

        template_path = TEMPLATES_DIR / "prompt_template.md"
        if not template_path.exists():
            QMessageBox.warning(self, "Error", "Prompt template not found.")
            return

        template = template_path.read_text(encoding="utf-8")

        # Build presenter list
        presenter_lines = []
        for i, (name, cfg) in enumerate(self._project.presenters.items(), 1):
            presenter_lines.append(f"{i}. **{name}** — \"{cfg.title}\" — Personality description here.")
        presenter_list = "\n".join(presenter_lines) if presenter_lines else "(No presenters defined)"

        # Extract slide text from PDF
        slide_lines = []
        pdf_path = self._project.resolved_pdf_path
        if pdf_path.exists():
            from slop.engine.pdf_renderer import extract_slide_text
            texts = extract_slide_text(pdf_path)
            for i, text in enumerate(texts, 1):
                clean = text.strip().replace("\n", " ")[:200]
                slide_lines.append(f"Slide {i}: \"{clean}\"")
        else:
            for i in range(len(self._project.slides)):
                slide_lines.append(f"Slide {i + 1}: (no PDF loaded)")
        slides_text = "\n".join(slide_lines)

        filled = template.replace("{PRESENTER_LIST}", presenter_list)
        filled = filled.replace("{SLIDES_WITH_TEXT}", slides_text)
        filled = filled.replace("{LANGUAGE}", "German")

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Export Prompt", self._project.name + "_prompt.md",
            "Markdown (*.md);;All Files (*)",
        )
        if save_path:
            Path(save_path).write_text(filled, encoding="utf-8")
            QMessageBox.information(self, "Exported", f"Prompt saved to:\n{save_path}")

    # ── Audio generation ─────────────────────────────────────────

    def _on_generate_all_audio(self):
        if not self._project:
            QMessageBox.information(self, "Generate", "No project loaded.")
            return

        missing = []
        for i, slide in enumerate(self._project.slides):
            if not slide.presenter or slide.presenter not in self._project.presenters:
                missing.append(f"Slide {i + 1}: no valid presenter")
            elif not slide.text.strip():
                missing.append(f"Slide {i + 1}: no text")
        if missing:
            QMessageBox.warning(self, "Incomplete", "Some slides are not ready:\n" + "\n".join(missing[:10]))
            return

        progress = QProgressDialog("Generating audio...", "Cancel", 0, len(self._project.slides), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        self._gen_thread = AudioGenThread(self._project)
        self._gen_thread.progress.connect(lambda cur, tot: progress.setValue(cur))
        self._gen_thread.finished_ok.connect(lambda: self._on_gen_done(progress))
        self._gen_thread.error.connect(lambda e: self._on_gen_error(progress, e))
        progress.canceled.connect(self._gen_thread.terminate)
        self._gen_thread.start()

    def _on_gen_done(self, progress):
        progress.close()
        self._gen_thread = None
        QMessageBox.information(self, "Done", "All audio generated successfully.")

    def _on_gen_error(self, progress, error):
        progress.close()
        self._gen_thread = None
        QMessageBox.critical(self, "Error", f"Audio generation failed:\n{error}")

    # ── MP4 export ────────────────────────────────────────────────

    def _on_export_mp4(self):
        if not self._project:
            QMessageBox.information(self, "Export MP4", "No project loaded.")
            return
        if not self._project.resolved_pdf_path.exists():
            QMessageBox.warning(self, "Export MP4", "PDF file not found.")
            return
        if not shutil.which("ffmpeg"):
            QMessageBox.critical(
                self, "Export MP4",
                "ffmpeg is not installed or not on PATH.\n"
                "Install ffmpeg to enable video export.\n\n"
                "  Arch: sudo pacman -S ffmpeg\n"
                "  Ubuntu: sudo apt install ffmpeg",
            )
            return

        engine_dict = self._project.to_engine_dict()
        cache_dir = Path(engine_dict["cache_dir"])
        from slop.engine.presentation import audio_path_for_slide
        missing_audio = [
            i + 1 for i in range(len(self._project.slides))
            if not audio_path_for_slide(cache_dir, i)
        ]
        if missing_audio:
            QMessageBox.warning(
                self, "Export MP4",
                f"Missing audio for slides: {missing_audio}\n"
                "Generate audio first (toolbar > Generate Audio).",
            )
            return

        default_name = self._project.name + ".mp4"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export MP4", default_name,
            "MP4 Video (*.mp4);;All Files (*)",
        )
        if not path:
            return

        progress = QProgressDialog("Preparing export...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setMinimumWidth(420)

        def _on_export_progress(cur, tot, msg):
            if tot > 0 and progress.maximum() != tot:
                progress.setMaximum(tot)
            progress.setValue(cur)
            progress.setLabelText(msg)

        self._export_thread = MP4ExportThread(self._project, path)
        self._export_thread.progress.connect(_on_export_progress)
        self._export_thread.finished_ok.connect(lambda p: self._on_export_mp4_done(progress, p))
        self._export_thread.error.connect(lambda e: self._on_export_mp4_error(progress, e))
        progress.canceled.connect(self._export_thread.abort)
        self._export_thread.start()

    def _on_export_mp4_done(self, progress, path):
        progress.close()
        self._export_thread = None
        QMessageBox.information(self, "Export Complete", f"Video saved to:\n{path}")

    def _on_export_mp4_error(self, progress, error):
        progress.close()
        self._export_thread = None
        QMessageBox.critical(self, "Export Failed", f"Video export failed:\n{error}")

    # ── Present ──────────────────────────────────────────────────

    def _on_present(self):
        if not self._project:
            QMessageBox.information(self, "Present", "No project loaded.")
            return
        if not self._project.resolved_pdf_path.exists():
            QMessageBox.warning(self, "Present", "PDF file not found.")
            return

        engine_dict = self._project.to_engine_dict()

        self.hide()
        try:
            from slop.engine.presentation import run_presentation
            run_presentation(engine_dict)
        except Exception as e:
            QMessageBox.critical(self, "Presentation Error", str(e))
        finally:
            self.show()

    # ── Window close ─────────────────────────────────────────────

    def closeEvent(self, event):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
