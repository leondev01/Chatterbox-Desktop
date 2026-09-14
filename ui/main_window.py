from __future__ import annotations

import re
import shutil
from pathlib import Path

from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QScrollArea,
)

from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    ProgressBar,
    ProgressRing,
    PushButton,
    Slider,
    SubtitleLabel,
    TextEdit,
    TitleLabel,
)

from core.audio_export import ffmpeg_available
from core.inference_process import InferenceProcess
from core.settings import SettingsManager


class SliderRow(QFrame):
    valueChanged = Signal(int)

    def __init__(self, title: str, description: str, minimum: int, maximum: int, value: int, suffix: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("sliderCard")

        # Fixed vertical budget prevents Fluent labels from being clipped on
        # Windows scaling settings (125%/150%) and smaller window heights.
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 9, 18, 7)
        layout.setSpacing(1)

        top = QHBoxLayout()
        self.title = BodyLabel(title)
        self.value_label = BodyLabel()
        self.value_label.setAlignment(Qt.AlignRight)

        top.addWidget(self.title)
        top.addStretch()
        top.addWidget(self.value_label)

        self.description = QLabel(description)
        self.description.setObjectName("mutedLabel")
        self.description.setMinimumHeight(18)
        self.description.setMaximumHeight(20)
        self.description.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.slider = Slider(Qt.Horizontal)
        self.slider.setFixedHeight(20)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.suffix = suffix

        layout.addLayout(top)
        layout.addWidget(self.description)
        layout.addWidget(self.slider)

        self.slider.valueChanged.connect(self._update_value)
        self._update_value(value)

    def _update_value(self, value: int) -> None:
        self.value_label.setText(
            (f"{value / 100:.2f}x" if self.suffix == "x" else f"{value}{self.suffix}")
            if self.suffix
            else str(value)
        )
        self.valueChanged.emit(value)


class MainWindow(QWidget):
    def __init__(self, settings: SettingsManager, inference: InferenceProcess):
        super().__init__()
        self.settings = settings
        self.inference = inference
        self._generation_active = False
        self.inference.status.connect(self._generation_status)
        self.inference.progress.connect(self._generation_progress)
        self.inference.finished.connect(self._generation_finished)
        self.inference.error.connect(self._inference_error)

        self.setWindowTitle("Chatterbox Desktop")
        self.resize(1120, 780)
        self.setMinimumSize(820, 560)

        self._apply_windows_mica()
        self._build_ui()
        self._load_voices()
        self._load_persistent_values()
        self._check_ffmpeg()

    def _apply_windows_mica(self) -> None:
        """
        QFluentWidgets' native FluentWindow already supports Mica. This app
        intentionally uses a normal QWidget so the content layout stays simple;
        on Windows 11 we request the native Mica backdrop directly.
        """
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(self.winId())

            # DWMWA_SYSTEMBACKDROP_TYPE = 38, DWMSBT_MAINWINDOW = 2 (Mica)
            attribute = 38
            backdrop = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                attribute,
                ctypes.byref(backdrop),
                ctypes.sizeof(backdrop),
            )

            # DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2
            corner = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd),
                33,
                ctypes.byref(corner),
                ctypes.sizeof(corner),
            )
        except Exception:
            # On non-Windows or unsupported Windows builds the app simply
            # falls back to the regular Fluent stylesheet.
            pass

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = TitleLabel("Chatterbox Desktop")
        subtitle = BodyLabel("Voiceover-Generator mit Chatterbox TTS")
        subtitle.setObjectName("mutedLabel")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.status_ring = ProgressRing()
        self.status_ring.setFixedSize(28, 28)
        self.status_ring.hide()
        header.addWidget(self.status_ring, 0, Qt.AlignVCenter)

        root.addLayout(header)

        # Text card
        text_card = CardWidget()
        text_layout = QVBoxLayout(text_card)
        text_layout.setContentsMargins(20, 18, 20, 20)
        text_layout.setSpacing(8)
        text_layout.addWidget(SubtitleLabel("Text"))

        self.text_edit = TextEdit()
        self.text_edit.setPlaceholderText(
            "Schreibe hier den Text, der vorgelesen werden soll..."
        )
        self.text_edit.setMinimumHeight(210)
        text_layout.addWidget(self.text_edit)
        # The main content is vertically scrollable so smaller window sizes
        # never clip the controls. The footer stays visible at the bottom.
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(text_card)

        self.generation_progress = ProgressBar()
        self.generation_progress.setRange(0, 100)
        self.generation_progress.setValue(0)
        self.generation_progress.setFixedHeight(6)
        self.generation_progress.hide()
        content_layout.addWidget(self.generation_progress)

        # Controls in two columns
        controls = QHBoxLayout()
        controls.setSpacing(18)

        left_card = CardWidget()
        left_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(18, 18, 18, 18)
        left_layout.setSpacing(20)
        left_layout.addWidget(SubtitleLabel("Stimme"))

        voice_row = QHBoxLayout()
        self.voice_combo = ComboBox()
        self.voice_combo.setPlaceholderText("Stimme auswählen")
        self.voice_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.add_voice_button = PrimaryPushButton(FIF.ADD, "Stimme hinzufügen")
        voice_row.addWidget(self.voice_combo, 1)
        voice_row.addWidget(self.add_voice_button)
        left_layout.addLayout(voice_row)

        left_layout.addWidget(SubtitleLabel("Ausgabeordner"))
        output_row = QHBoxLayout()
        self.output_edit = LineEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText("Noch kein Safe-Location-Ordner gewählt")
        self.output_button = PushButton(FIF.FOLDER, "Ordner auswählen")
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_button)
        left_layout.addLayout(output_row)

        controls.addWidget(left_card, 1, Qt.AlignTop)

        right_card = CardWidget()
        right_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(8)
        right_layout.addWidget(SubtitleLabel("Feineinstellungen"))

        self.exaggeration = SliderRow(
            "Emotionsstärke",
            "Chatterbox exaggeration · 0.0 bis 1.0",
            0, 100, 50
        )
        self.cfg_weight = SliderRow(
            "Texteinhaltung",
            "Chatterbox cfg_weight · 0.0 bis 1.0",
            0, 100, 50
        )
        self.speed = SliderRow(
            "Sprachgeschwindigkeit",
            "1.00x entspricht der normalen Voiceover-Geschwindigkeit",
            50, 200, 100, "x"
        )
        right_layout.addWidget(self.exaggeration)
        right_layout.addWidget(self.cfg_weight)
        right_layout.addWidget(self.speed)

        controls.addWidget(right_card, 1, Qt.AlignTop)
        content_layout.addLayout(controls)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        footer = QHBoxLayout()
        self.info_label = BodyLabel("Bereit")
        self.info_label.setObjectName("mutedLabel")

        self.generate_button = PrimaryPushButton(FIF.PLAY, "Voiceover generieren")
        self.generate_button.setMinimumHeight(44)
        self.generate_button.setMinimumWidth(220)

        self.stop_button = PushButton(FIF.CLOSE, "Generierung stoppen")
        self.stop_button.setMinimumHeight(44)
        self.stop_button.setMinimumWidth(190)
        self.stop_button.hide()

        footer.addWidget(self.info_label)
        footer.addStretch()
        footer.addWidget(self.stop_button)
        footer.addWidget(self.generate_button)
        root.addLayout(footer)

        self.add_voice_button.clicked.connect(self._add_voice)
        self.output_button.clicked.connect(self._choose_output)
        self.generate_button.clicked.connect(self._generate)
        self.stop_button.clicked.connect(self._stop_generation)
        self.voice_combo.currentIndexChanged.connect(self._voice_changed)

        # Remember the three generation settings between app launches.
        self.exaggeration.valueChanged.connect(
            lambda value: self.settings.set_slider_value("exaggeration", value)
        )
        self.cfg_weight.valueChanged.connect(
            lambda value: self.settings.set_slider_value("cfg_weight", value)
        )
        self.speed.valueChanged.connect(
            lambda value: self.settings.set_slider_value("speed", value)
        )

        self.setStyleSheet("""
            QWidget {
                font-size: 14px;
            }
            #mutedLabel {
                color: rgba(128, 128, 128, 230);
            }
            #sliderCard {
                border-radius: 12px;
                background: rgba(255, 255, 255, 35);
            }
            QLineEdit, QTextEdit {
                border-radius: 10px;
            }
        """)

    def _load_persistent_values(self) -> None:
        # Restore the last generation settings. Values are stored as slider
        # integers so there is no precision loss.
        self.exaggeration.slider.setValue(
            self.settings.get_slider_value("exaggeration", 50)
        )
        self.cfg_weight.slider.setValue(
            self.settings.get_slider_value("cfg_weight", 50)
        )
        self.speed.slider.setValue(
            max(50, min(200, self.settings.get_slider_value("speed", 100)))
        )

        output = self.settings.safe_location
        if output and Path(output).exists():
            self.output_edit.setText(output)
        else:
            self.output_edit.setText("")

        selected = self.settings.selected_voice
        if selected:
            index = self.voice_combo.findData(selected)
            if index >= 0:
                self.voice_combo.setCurrentIndex(index)

    def _check_ffmpeg(self) -> None:
        if not ffmpeg_available():
            self.info_label.setText("FFmpeg fehlt")
            InfoBar.warning(
                "FFmpeg nicht gefunden",
                "Lege ffmpeg.exe für die Entwicklung in den Projektordner "
                "oder installiere FFmpeg im PATH. Die fertige EXE kann FFmpeg mitbringen.",
                parent=self,
                duration=7000,
            )

    def _load_voices(self) -> None:
        self.voice_combo.clear()
        voices_dir = self.settings.voices_dir
        voices_dir.mkdir(parents=True, exist_ok=True)

        files = sorted(
            [
                p for p in voices_dir.iterdir()
                if p.is_file() and p.suffix.lower() in {".wav", ".mp3"}
            ],
            key=lambda p: p.stem.lower(),
        )

        for path in files:
            self.voice_combo.addItem(path.stem, str(path))

        if not files:
            self.voice_combo.setPlaceholderText("Noch keine Stimme gespeichert")

    def _voice_changed(self, index: int) -> None:
        if index < 0:
            return
        path = self.voice_combo.itemData(index)
        if path:
            self.settings.selected_voice = str(path)

    def _add_voice(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self,
            "Referenz-Audio auswählen",
            "",
            "Audio-Dateien (*.wav *.mp3)",
        )
        if not source:
            return

        name, accepted = QInputDialog.getText(
            self,
            "Stimme benennen",
            "Name der Stimme:",
            text=Path(source).stem,
        )
        if not accepted or not name.strip():
            return

        safe_name = re.sub(r'[<>:"/\\\\|?*]+', "_", name.strip()).strip(". ")
        if not safe_name:
            safe_name = "Stimme"

        extension = Path(source).suffix.lower()
        destination = self.settings.voices_dir / f"{safe_name}{extension}"

        # Avoid silently overwriting an existing voice.
        counter = 2
        while destination.exists():
            destination = self.settings.voices_dir / f"{safe_name} ({counter}){extension}"
            counter += 1

        try:
            shutil.copy2(source, destination)
        except OSError as exc:
            InfoBar.error("Stimme konnte nicht gespeichert werden", str(exc), parent=self, position=InfoBarPosition.TOP)
            return

        self._load_voices()
        index = self.voice_combo.findData(str(destination))
        if index >= 0:
            self.voice_combo.setCurrentIndex(index)

        InfoBar.success(
            "Stimme gespeichert",
            f"Die Referenzdatei wurde als „{destination.stem}“ gespeichert.",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2500,
        )

    def _choose_output(self) -> None:
        current = self.settings.safe_location
        folder = QFileDialog.getExistingDirectory(
            self,
            "Safe-Location auswählen",
            current if current and Path(current).exists() else str(Path.home()),
        )
        if not folder:
            return

        self.settings.safe_location = folder
        self.output_edit.setText(folder)
        self.info_label.setText(f"Ausgabe: {folder}")

    def _generate(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            InfoBar.warning("Kein Text", "Bitte gib zuerst Text ein.", parent=self, position=InfoBarPosition.TOP)
            return

        output_dir = self.output_edit.text().strip()
        if not output_dir:
            InfoBar.warning("Kein Ausgabeordner", "Wähle zuerst einen Safe-Location-Ordner aus.", parent=self)
            return
        if not Path(output_dir).exists():
            InfoBar.warning("Ausgabeordner fehlt", "Der gespeicherte Ordner existiert nicht mehr. Bitte wähle einen neuen.", parent=self)
            return
        if not ffmpeg_available():
            self._check_ffmpeg()
            return
        if not self.inference.is_ready:
            InfoBar.warning("Modell wird noch geladen", "Warte bitte, bis Chatterbox vollständig gestartet ist.", parent=self, position=InfoBarPosition.TOP)
            return

        voice_path = self.voice_combo.currentData() or ""
        number = self.settings.reserve_next_number(output_dir)
        payload = {
            "text": text,
            "exaggeration": self.exaggeration.slider.value() / 100.0,
            "cfg_weight": self.cfg_weight.slider.value() / 100.0,
            "speed": self.speed.slider.value() / 100.0,
            "voice_path": str(voice_path),
            "output_dir": output_dir,
            "number": number,
        }

        self._generation_active = True
        self._set_generating(True, f"Generiere Voiceover({number}).mp3 …")
        self.inference.generate(payload)

    @Slot(str)
    def _generation_status(self, message: str) -> None:
        if self._generation_active:
            self.info_label.setText(message)

    @Slot(int)
    def _generation_progress(self, value: int) -> None:
        if self._generation_active:
            self.generation_progress.setValue(max(0, min(100, value)))

    @Slot(str)
    def _generation_finished(self, path: str) -> None:
        self._generation_active = False
        self._set_generating(False, f"Fertig: {Path(path).name}")
        InfoBar.success("Voiceover erstellt", f"Gespeichert unter:\n{path}", parent=self, position=InfoBarPosition.TOP, duration=5000)

    @Slot(str)
    def _inference_error(self, message: str) -> None:
        # Startup errors are handled by main.py. During generation, show them here.
        if self._generation_active:
            self._generation_active = False
            self._set_generating(False, "Generierung fehlgeschlagen")
            InfoBar.error("Generierung fehlgeschlagen", message, parent=self, position=InfoBarPosition.TOP, duration=8000)

    @Slot(str)
    def _generation_error(self, message: str) -> None:
        self._inference_error(message)


    def _stop_generation(self) -> None:
        if not self._generation_active:
            return
        self.stop_button.setEnabled(False)
        self.info_label.setText("Generierung wird sofort beendet …")
        self._generation_active = False
        self._set_generating(False, "Generierung abgebrochen")
        self.inference.stop_and_restart()
        InfoBar.warning(
            "Generierung abgebrochen",
            "Der laufende Chatterbox-Prozess wurde sicher beendet. Das Modell wird im Hintergrund neu geladen.",
            parent=self,
            position=InfoBarPosition.TOP,
            duration=4500,
        )

    def _set_generating(self, active: bool, status: str) -> None:
        self.generate_button.setEnabled(not active)
        self.stop_button.setVisible(active)
        self.stop_button.setEnabled(active)
        self.add_voice_button.setEnabled(not active)
        self.output_button.setEnabled(not active)
        self.voice_combo.setEnabled(not active)
        self.status_ring.setVisible(active)
        self.generation_progress.setVisible(active)
        self.generation_progress.setValue(0 if not active else self.generation_progress.value())
        self.info_label.setText(status)
