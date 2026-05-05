"""Reusable widgets: color picker button, GIF preview, labeled slider."""

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QLabel, QHBoxLayout, QVBoxLayout,
    QSlider, QColorDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QColor, QImage

from pathlib import Path
from PIL import Image


class ColorPickerButton(QPushButton):
    color_changed = pyqtSignal(tuple)

    def __init__(self, initial_color=(100, 100, 100), parent=None):
        super().__init__(parent)
        self._color = initial_color
        self.setFixedSize(40, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()
        self.clicked.connect(self._pick_color)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, c):
        self._color = tuple(c)
        self._update_style()

    def _update_style(self):
        r, g, b = self._color
        self.setStyleSheet(
            f"background: rgb({r},{g},{b}); border: 2px solid #cdd6f4; border-radius: 4px;"
        )

    def _pick_color(self):
        r, g, b = self._color
        c = QColorDialog.getColor(QColor(r, g, b), self, "Choose Presenter Color")
        if c.isValid():
            self._color = (c.red(), c.green(), c.blue())
            self._update_style()
            self.color_changed.emit(self._color)


class LabeledSlider(QWidget):
    value_changed = pyqtSignal(float)

    def __init__(self, label, min_val, max_val, default, step=0.01, parent=None):
        super().__init__(parent)
        self._step = step
        self._min = min_val
        self._max = max_val

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(label)
        self._label.setFixedWidth(100)
        layout.addWidget(self._label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(int(min_val / step))
        self._slider.setMaximum(int(max_val / step))
        self._slider.setValue(int(default / step))
        self._slider.valueChanged.connect(self._on_change)
        layout.addWidget(self._slider, 1)

        self._value_label = QLabel(f"{default:.2f}")
        self._value_label.setFixedWidth(50)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._value_label)

    @property
    def value(self):
        return self._slider.value() * self._step

    @value.setter
    def value(self, v):
        self._slider.setValue(int(v / self._step))

    def _on_change(self, raw):
        val = raw * self._step
        self._value_label.setText(f"{val:.2f}")
        self.value_changed.emit(val)


class GifPreviewWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frames = []
        self._current = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setFixedSize(200, 150)
        self._label.setStyleSheet("background: #181825; border-radius: 6px;")
        layout.addWidget(self._label)

    def load_gif(self, gif_path, tint_color=None, target_color=(235, 78, 10), tolerance=60):
        self._timer.stop()
        self._frames = []
        path = Path(gif_path)
        if not path.exists():
            self._label.setText("No GIF")
            return

        gif = Image.open(str(path))
        for i in range(min(gif.n_frames, 30)):
            gif.seek(i)
            frame = gif.convert("RGBA")

            if tint_color:
                pixels = frame.load()
                w, h = frame.size
                tr, tg, tb = target_color
                cr, cg, cb = tint_color
                for y in range(h):
                    for x in range(w):
                        r, g, b, a = pixels[x, y]
                        brightness = (r + g + b) / 3.0
                        if brightness < 30:
                            pixels[x, y] = (0, 0, 0, 0)
                        elif (abs(r - tr) < tolerance and abs(g - tg) < tolerance and abs(b - tb) < tolerance):
                            factor = brightness / 255.0
                            pixels[x, y] = (min(255, int(cr * factor)), min(255, int(cg * factor)), min(255, int(cb * factor)), a)

            data = frame.tobytes("raw", "RGBA")
            qimg = QImage(data, frame.width, frame.height, QImage.Format.Format_RGBA8888)
            pm = QPixmap.fromImage(qimg).scaled(
                self._label.width(), self._label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            self._frames.append(pm)

        if self._frames:
            self._current = 0
            self._label.setPixmap(self._frames[0])
            self._timer.start(100)

    def _next_frame(self):
        if not self._frames:
            return
        self._current = (self._current + 1) % len(self._frames)
        self._label.setPixmap(self._frames[self._current])

    def stop(self):
        self._timer.stop()
