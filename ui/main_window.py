from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from qfluentwidgets import (
    BodyLabel, CardWidget, ComboBox, FluentIcon as FIF, InfoBar,
    InfoBarPosition, LineEdit, PrimaryPushButton, ProgressBar, ProgressRing,
    PushButton, Slider, SubtitleLabel, TextEdit, TitleLabel,
)

from core.audio_export import ffmpeg_available
from core.inference_process import InferenceProcess
from core.projects import load_project, project_path, safe_project_name, save_project
from core.settings import SettingsManager


class SliderRow(QFrame):
    valueChanged = Signal(int)

    def __init__(self, title, minimum, maximum, value, suffix="", parent=None):
        super().__init__(parent)
        self.setObjectName("sliderCard")
        self.setMinimumHeight(68)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(4)
        top = QHBoxLayout()
        self.title = BodyLabel(title)
        self.value_label = BodyLabel()
        self.value_label.setAlignment(Qt.AlignRight)
        top.addWidget(self.title)
        top.addStretch()
        top.addWidget(self.value_label)
        self.slider = Slider(Qt.Horizontal)
        self.slider.setFixedHeight(20)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.suffix = suffix
        layout.addLayout(top)
        layout.addWidget(self.slider)
        self.slider.valueChanged.connect(self._update_value)
        self._update_value(value)

    def _update_value(self, value):
        self.value_label.setText(f"{value / 100:.2f}x" if self.suffix == "x" else f"{value}{self.suffix}" if self.suffix else str(value))
        self.valueChanged.emit(value)


class MainWindow(QWidget):
    def __init__(self, settings: SettingsManager, inference: InferenceProcess):
        super().__init__()
        self.settings = settings
        self.inference = inference
        self._generation_active = False
        self._last_audio = ""
        self._drag_voice_path = ""
        self.setAcceptDrops(True)
        self.inference.status.connect(self._generation_status)
        self.inference.progress.connect(self._generation_progress)
        self.inference.progress_mode.connect(self._generation_progress_mode)
        self.inference.finished.connect(self._generation_finished)
        self.inference.error.connect(self._inference_error)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(1.0)
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self._player_position)
        self.player.durationChanged.connect(self._player_duration)
        self.player.playbackStateChanged.connect(lambda *_: self._sync_play_button())

        self.setWindowTitle("Chatterbox Desktop")
        self.resize(1120, 820)
        self.setMinimumSize(820, 580)
        self._apply_windows_mica()
        self._build_ui()
        self._load_voices()
        self._load_persistent_values()
        self._check_ffmpeg()

    def _apply_windows_mica(self):
        try:
            import ctypes
            from ctypes import wintypes
            hwnd = int(self.winId())
            backdrop = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
            corner = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), 33, ctypes.byref(corner), ctypes.sizeof(corner))
        except Exception:
            pass

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 22)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.addWidget(TitleLabel("Chatterbox Desktop"))
        header.addLayout(title_box)
        header.addStretch()
        self.status_ring = ProgressRing()
        self.status_ring.setFixedSize(28, 28)
        self.status_ring.hide()
        header.addWidget(self.status_ring)
        root.addLayout(header)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        text_card = CardWidget()
        text_layout = QVBoxLayout(text_card)
        text_layout.setContentsMargins(20, 18, 20, 20)
        top = QHBoxLayout()
        top.addWidget(SubtitleLabel("Text"))
        top.addStretch()
        self.import_text_button = PushButton(FIF.FOLDER, "Text importieren")
        self.project_button = PushButton(FIF.SAVE, "Projekte")
        self.history_button = PushButton(FIF.HISTORY, "Historie")
        top.addWidget(self.import_text_button)
        top.addWidget(self.project_button)
        top.addWidget(self.history_button)
        text_layout.addLayout(top)
        self.text_edit = TextEdit()
        self.text_edit.setPlaceholderText("Schreibe hier den Text, der vorgelesen werden soll...")
        self.text_edit.setMinimumHeight(210)
        text_layout.addWidget(self.text_edit)
        content_layout.addWidget(text_card)

        self.generation_progress = ProgressBar()
        self.generation_progress.setRange(0, 100)
        self.generation_progress.setValue(0)
        self.generation_progress.setFixedHeight(6)
        self.generation_progress.hide()
        content_layout.addWidget(self.generation_progress)

        controls = QHBoxLayout()
        controls.setSpacing(18)
        left = CardWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(20, 18, 20, 18)
        left_layout.setSpacing(12)
        left_layout.addWidget(SubtitleLabel("Stimme"))
        voice_row = QHBoxLayout()
        self.voice_combo = ComboBox()
        self.voice_combo.setPlaceholderText("Stimme auswählen")
        self.voice_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        voice_row.addWidget(self.voice_combo, 1)
        self.favorite_voice_button = PushButton("☆")
        self.favorite_voice_button.setToolTip("Stimme favorisieren")
        self.preview_voice_button = PushButton(FIF.PLAY, "Vorschau")
        self.rename_voice_button = PushButton(FIF.EDIT, "Umbenennen")
        self.delete_voice_button = PushButton(FIF.DELETE, "Löschen")
        voice_row.addWidget(self.favorite_voice_button)
        voice_row.addWidget(self.preview_voice_button)
        voice_row.addWidget(self.rename_voice_button)
        voice_row.addWidget(self.delete_voice_button)
        left_layout.addLayout(voice_row)
        voice_actions = QHBoxLayout()
        self.add_voice_button = PrimaryPushButton(FIF.ADD, "Stimme hinzufügen")
        voice_actions.addWidget(self.add_voice_button)
        left_layout.addLayout(voice_actions)
        left_layout.addWidget(SubtitleLabel("Ausgabeordner"))
        output_row = QHBoxLayout()
        self.output_edit = LineEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText("Noch kein Safe-Location-Ordner gewählt")
        self.output_button = PushButton(FIF.FOLDER, "Ordner auswählen")
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.output_button)
        left_layout.addLayout(output_row)
        controls.addWidget(left, 1)

        right = CardWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(20, 18, 20, 18)
        right_layout.setSpacing(8)
        right_layout.addWidget(SubtitleLabel("Einstellungen"))
        self.exaggeration = SliderRow("Emotionsstärke", 0, 100, 50)
        self.cfg_weight = SliderRow("Texteinhaltung", 0, 100, 50)
        self.speed = SliderRow("Sprachgeschwindigkeit", 50, 200, 100, "x")
        right_layout.addWidget(self.exaggeration)
        right_layout.addWidget(self.cfg_weight)
        right_layout.addWidget(self.speed)
        controls.addWidget(right, 1)
        content_layout.addLayout(controls)

        audio_card = CardWidget()
        audio_layout = QVBoxLayout(audio_card)
        audio_layout.setContentsMargins(18, 14, 18, 14)
        audio_top = QHBoxLayout()
        audio_top.addStretch()
        self.audio_label = BodyLabel("Noch kein Audio geladen")
        self.audio_label.setObjectName("mutedLabel")
        audio_top.addWidget(self.audio_label)
        audio_layout.addLayout(audio_top)
        audio_controls = QHBoxLayout()
        self.play_button = PushButton(FIF.PLAY, "Abspielen")
        self.audio_slider = Slider(Qt.Horizontal)
        self.audio_slider.setRange(0, 0)
        self.audio_slider.sliderMoved.connect(self.player.setPosition)
        audio_controls.addSpacing(24)
        audio_controls.addWidget(self.play_button)
        audio_controls.addWidget(self.audio_slider, 1)
        audio_layout.addLayout(audio_controls)
        content_layout.addWidget(audio_card)

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

        self.import_text_button.clicked.connect(self._import_text)
        self.project_button.clicked.connect(self._open_projects)
        self.history_button.clicked.connect(self._open_history)
        self.add_voice_button.clicked.connect(self._add_voice)
        self.preview_voice_button.clicked.connect(self._preview_voice)
        self.rename_voice_button.clicked.connect(self._rename_voice)
        self.delete_voice_button.clicked.connect(self._delete_voice)
        self.favorite_voice_button.clicked.connect(self._toggle_favorite_voice)
        self.output_button.clicked.connect(self._choose_output)
        self.generate_button.clicked.connect(self._generate)
        self.stop_button.clicked.connect(self._stop_generation)
        self.play_button.clicked.connect(self._toggle_audio)
        self.voice_combo.currentIndexChanged.connect(self._voice_changed)
        self.exaggeration.valueChanged.connect(lambda v: self.settings.set_slider_value("exaggeration", v))
        self.cfg_weight.valueChanged.connect(lambda v: self.settings.set_slider_value("cfg_weight", v))
        self.speed.valueChanged.connect(lambda v: self.settings.set_slider_value("speed", v))

        self.setStyleSheet("""
            QWidget { font-size: 14px; }
            #mutedLabel { color: rgba(128,128,128,230); }
            #sliderCard { border-radius: 12px; background: rgba(255,255,255,35); }
            QLineEdit, QTextEdit { border-radius: 10px; }
        """)

    def _load_persistent_values(self):
        self.exaggeration.slider.setValue(self.settings.get_slider_value("exaggeration", 50))
        self.cfg_weight.slider.setValue(self.settings.get_slider_value("cfg_weight", 50))
        self.speed.slider.setValue(max(50, min(200, self.settings.get_slider_value("speed", 100))))
        output = self.settings.safe_location
        self.output_edit.setText(output if output and Path(output).exists() else "")
        selected = self.settings.selected_voice
        if selected:
            index = self.voice_combo.findData(selected)
            if index >= 0:
                self.voice_combo.setCurrentIndex(index)

    def _check_ffmpeg(self):
        if not ffmpeg_available():
            self.info_label.setText("FFmpeg fehlt")
            InfoBar.warning("FFmpeg nicht gefunden", "Starte build.bat für einen automatischen FFmpeg-Setup oder installiere FFmpeg im PATH.", parent=self, duration=7000)

    def _voice_files(self):
        return sorted([p for p in self.settings.voices_dir.iterdir() if p.is_file() and p.suffix.lower() in {".wav", ".mp3"}], key=lambda p: (not self.settings.is_favorite(str(p)), p.stem.lower()))

    def _load_voices(self):
        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        files = self._voice_files()
        for path in files:
            prefix = "★ " if self.settings.is_favorite(str(path)) else ""
            self.voice_combo.addItem(prefix + path.stem, str(path))
        self.voice_combo.blockSignals(False)
        if not files:
            self.voice_combo.setPlaceholderText("Noch keine Stimme gespeichert")
        selected = self.settings.selected_voice
        idx = self.voice_combo.findData(selected)
        if idx >= 0:
            self.voice_combo.setCurrentIndex(idx)
        elif files:
            self.voice_combo.setCurrentIndex(0)
        self._update_voice_buttons()

    def _current_voice_path(self) -> Path | None:
        value = self.voice_combo.currentData()
        if not value and self.voice_combo.currentIndex() >= 0:
            value = self.voice_combo.itemData(self.voice_combo.currentIndex())
        return Path(value) if value else None

    def _update_voice_buttons(self):
        path = self._current_voice_path()
        enabled = path is not None and path.exists()
        for button in (self.favorite_voice_button, self.preview_voice_button, self.rename_voice_button, self.delete_voice_button):
            button.setEnabled(enabled and not self._generation_active)
        self.favorite_voice_button.setText("★" if enabled and self.settings.is_favorite(str(path)) else "☆")

    def _voice_changed(self, index):
        if index >= 0 and self.voice_combo.itemData(index):
            self.settings.selected_voice = str(self.voice_combo.itemData(index))
        self._update_voice_buttons()

    def _add_voice_file(self, source: str, suggested_name: str | None = None):
        source_path = Path(source)
        if not source_path.exists() or source_path.suffix.lower() not in {".wav", ".mp3"}:
            return
        name, accepted = QInputDialog.getText(self, "Stimme benennen", "Name der Stimme:", text=suggested_name or source_path.stem)
        if not accepted or not name.strip():
            return
        safe = re.sub(r'[<>:"/\\|?*]+', "_", name.strip()).strip(". ") or "Stimme"
        destination = self.settings.voices_dir / f"{safe}{source_path.suffix.lower()}"
        counter = 2
        while destination.exists():
            destination = self.settings.voices_dir / f"{safe} ({counter}){source_path.suffix.lower()}"
            counter += 1
        try:
            shutil.copy2(source_path, destination)
        except OSError as exc:
            InfoBar.error("Stimme konnte nicht gespeichert werden", str(exc), parent=self, position=InfoBarPosition.TOP)
            return
        self._load_voices()
        idx = self.voice_combo.findData(str(destination))
        if idx >= 0:
            self.voice_combo.setCurrentIndex(idx)
        InfoBar.success("Stimme gespeichert", f"„{destination.stem}“ wurde hinzugefügt.", parent=self, position=InfoBarPosition.TOP, duration=2500)

    def _add_voice(self):
        source, _ = QFileDialog.getOpenFileName(self, "Referenz-Audio auswählen", "", "Audio-Dateien (*.wav *.mp3)")
        if source:
            self._add_voice_file(source)

    def _preview_voice(self):
        path = self._current_voice_path()
        if not path:
            return
        self._play_audio(path)

    def _rename_voice(self):
        path = self._current_voice_path()
        if not path:
            return
        name, ok = QInputDialog.getText(self, "Stimme umbenennen", "Neuer Name:", text=path.stem)
        if not ok or not name.strip():
            return
        new_path = path.with_name(safe_project_name(name) + path.suffix.lower())
        if new_path != path and new_path.exists():
            QMessageBox.warning(self, "Name bereits vorhanden", "Eine Stimme mit diesem Namen existiert bereits.")
            return
        old = str(path)
        try:
            path.rename(new_path)
        except OSError as exc:
            InfoBar.error("Umbenennen fehlgeschlagen", str(exc), parent=self)
            return
        if self.settings.selected_voice == old:
            self.settings.selected_voice = str(new_path)
        if self.settings.is_favorite(old):
            self.settings.remove_favorite(old)
            self.settings.toggle_favorite(str(new_path))
        self._load_voices()

    def _delete_voice(self):
        path = self._current_voice_path()
        if not path:
            return
        answer = QMessageBox.question(self, "Stimme löschen", f"„{path.stem}“ wirklich löschen?", QMessageBox.Yes | QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            path.unlink()
        except OSError as exc:
            InfoBar.error("Löschen fehlgeschlagen", str(exc), parent=self)
            return
        self.settings.remove_favorite(str(path))
        if self.settings.selected_voice == str(path):
            self.settings.selected_voice = ""
        self._load_voices()
        InfoBar.success("Stimme gelöscht", f"„{path.stem}“ wurde gelöscht.", parent=self, position=InfoBarPosition.TOP)

    def _toggle_favorite_voice(self):
        path = self._current_voice_path()
        if path:
            self.settings.toggle_favorite(str(path))
            self._load_voices()
            self.voice_combo.setCurrentIndex(self.voice_combo.findData(str(path)))

    def _import_text(self):
        path, _ = QFileDialog.getOpenFileName(self, "Textdatei importieren", "", "Textdateien (*.txt *.md)")
        if not path:
            return
        try:
            self.text_edit.setPlainText(Path(path).read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            self.text_edit.setPlainText(Path(path).read_text(encoding="utf-8-sig"))
        except OSError as exc:
            InfoBar.error("Text konnte nicht importiert werden", str(exc), parent=self)

    def _project_payload(self):
        return {
            "text": self.text_edit.toPlainText(),
            "voice_path": str(self.voice_combo.currentData() or ""),
            "exaggeration": self.exaggeration.slider.value(),
            "cfg_weight": self.cfg_weight.slider.value(),
            "speed": self.speed.slider.value(),
            "output_dir": self.output_edit.text().strip(),
        }

    def _apply_project(self, payload):
        self.text_edit.setPlainText(str(payload.get("text", "")))
        voice = str(payload.get("voice_path", ""))
        idx = self.voice_combo.findData(voice)
        if idx >= 0:
            self.voice_combo.setCurrentIndex(idx)
        self.exaggeration.slider.setValue(int(payload.get("exaggeration", 50)))
        self.cfg_weight.slider.setValue(int(payload.get("cfg_weight", 50)))
        self.speed.slider.setValue(max(50, min(200, int(payload.get("speed", 100)))))
        output = str(payload.get("output_dir", ""))
        if output:
            self.output_edit.setText(output)

    def _open_projects(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Projekte")
        dialog.resize(560, 430)
        layout = QVBoxLayout(dialog)
        layout.addWidget(SubtitleLabel("Gespeicherte Projekte"))
        listing = QListWidget()
        files = sorted(self.settings.projects_dir.glob("*.json"), key=lambda p: p.stem.lower())
        for p in files:
            listing.addItem(p.stem)
        layout.addWidget(listing)
        buttons = QHBoxLayout()
        new_btn = PrimaryPushButton(FIF.SAVE, "Speichern")
        open_btn = PushButton(FIF.ACCEPT, "Öffnen")
        rename_btn = PushButton(FIF.EDIT, "Umbenennen")
        delete_btn = PushButton(FIF.DELETE, "Löschen")
        close_btn = PushButton("Schließen")
        for b in (new_btn, open_btn, rename_btn, delete_btn, close_btn): buttons.addWidget(b)
        layout.addLayout(buttons)

        def refresh(select_name=""):
            listing.clear()
            for p in sorted(self.settings.projects_dir.glob("*.json"), key=lambda p: p.stem.lower()): listing.addItem(p.stem)
            if select_name:
                hits = listing.findItems(select_name, Qt.MatchExactly)
                if hits: listing.setCurrentItem(hits[0])

        def save():
            name, ok = QInputDialog.getText(dialog, "Projekt speichern", "Projektname:")
            if not ok or not name.strip(): return
            path = project_path(self.settings.projects_dir, name)
            if path.exists():
                if QMessageBox.question(dialog, "Überschreiben", "Dieses Projekt existiert bereits. Überschreiben?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes: return
            save_project(self.settings.projects_dir, name, self._project_payload())
            refresh(path.stem)

        def open_selected():
            item = listing.currentItem()
            if not item: return
            try: self._apply_project(load_project(project_path(self.settings.projects_dir, item.text())))
            except (OSError, json.JSONDecodeError) as exc: QMessageBox.warning(dialog, "Projekt konnte nicht geöffnet werden", str(exc)); return
            dialog.accept()

        def rename():
            item = listing.currentItem()
            if not item: return
            old = item.text()
            name, ok = QInputDialog.getText(dialog, "Projekt umbenennen", "Neuer Name:", text=old)
            if not ok or not name.strip(): return
            new_path = project_path(self.settings.projects_dir, name)
            old_path = project_path(self.settings.projects_dir, old)
            if new_path.exists() and new_path != old_path: QMessageBox.warning(dialog, "Name bereits vorhanden", "Dieses Projekt existiert bereits."); return
            old_path.rename(new_path); refresh(new_path.stem)

        def delete():
            item = listing.currentItem()
            if not item: return
            if QMessageBox.question(dialog, "Projekt löschen", f"„{item.text()}“ wirklich löschen?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes: return
            project_path(self.settings.projects_dir, item.text()).unlink(missing_ok=True); refresh()

        new_btn.clicked.connect(save); open_btn.clicked.connect(open_selected); rename_btn.clicked.connect(rename); delete_btn.clicked.connect(delete); close_btn.clicked.connect(dialog.reject)
        listing.itemDoubleClicked.connect(lambda _: open_selected())
        dialog.exec()

    def _open_history(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Generierungs-Historie")
        dialog.resize(700, 480)
        layout = QVBoxLayout(dialog)
        listing = QListWidget()
        history = list(reversed(self.settings.load_history()))
        for entry in history:
            path = Path(entry.get("path", ""))
            label = f"{entry.get('timestamp', '')} · {path.name if path.name else 'Audio'}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, entry)
            listing.addItem(item)
        layout.addWidget(listing)
        buttons = QHBoxLayout()
        play = PushButton(FIF.PLAY, "Abspielen")
        regenerate = PrimaryPushButton(FIF.SYNC, "Erneut generieren")
        close = PushButton("Schließen")
        buttons.addWidget(play); buttons.addWidget(regenerate); buttons.addStretch(); buttons.addWidget(close)
        layout.addLayout(buttons)

        def selected():
            item = listing.currentItem()
            return item.data(Qt.UserRole) if item else None

        def play_selected():
            entry = selected()
            if entry: self._play_audio(Path(entry.get("path", "")))

        def regen():
            entry = selected()
            if not entry: return
            self._apply_project(entry)
            dialog.accept()
            self._generate()

        play.clicked.connect(play_selected); regenerate.clicked.connect(regen); close.clicked.connect(dialog.reject)
        listing.itemDoubleClicked.connect(lambda _: play_selected())
        dialog.exec()

    def _choose_output(self):
        current = self.settings.safe_location
        folder = QFileDialog.getExistingDirectory(self, "Safe-Location auswählen", current if current and Path(current).exists() else str(Path.home()))
        if folder:
            self.settings.safe_location = folder
            self.output_edit.setText(folder)
            self.info_label.setText(f"Ausgabe: {folder}")

    def _generate(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            InfoBar.warning("Kein Text", "Bitte gib zuerst Text ein.", parent=self, position=InfoBarPosition.TOP); return
        output_dir = self.output_edit.text().strip()
        if not output_dir or not Path(output_dir).exists():
            InfoBar.warning("Kein Ausgabeordner", "Wähle zuerst einen gültigen Safe-Location-Ordner aus.", parent=self); return
        if not ffmpeg_available(): self._check_ffmpeg(); return
        if not self.inference.is_ready:
            InfoBar.warning("Modell wird noch geladen", "Warte bitte, bis Chatterbox vollständig gestartet ist.", parent=self, position=InfoBarPosition.TOP); return
        number = self.settings.reserve_next_number(output_dir)
        payload = {"text": text, "exaggeration": self.exaggeration.slider.value()/100, "cfg_weight": self.cfg_weight.slider.value()/100, "speed": self.speed.slider.value()/100, "voice_path": str(self.voice_combo.currentData() or ""), "output_dir": output_dir, "number": number}
        self._generation_active = True
        self._set_generating(True, f"Generiere Voiceover({number}).mp3 …")
        self.inference.generate(payload)

    @Slot(str)
    def _generation_status(self, message):
        if self._generation_active: self.info_label.setText(message)

    @Slot(str)
    def _generation_progress_mode(self, mode):
        if not self._generation_active: return
        if mode == "busy": self.generation_progress.setRange(0, 0)
        else: self.generation_progress.setRange(0, 100); self.generation_progress.setValue(0)

    @Slot(int)
    def _generation_progress(self, value):
        if self._generation_active:
            if self.generation_progress.maximum() == 0: self.generation_progress.setRange(0, 100)
            self.generation_progress.setValue(max(0, min(100, value)))

    @Slot(str)
    def _generation_finished(self, path):
        self._generation_active = False
        self._set_generating(False, f"Fertig: {Path(path).name}")
        self._last_audio = path
        self._play_audio(Path(path), autoplay=False)
        history = self.settings.load_history()
        payload = self._project_payload()
        payload["path"] = path
        payload["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history.append(payload)
        self.settings.save_history(history)
        InfoBar.success("Voiceover erstellt", f"Gespeichert unter: {path}", parent=self, position=InfoBarPosition.TOP, duration=5000)

    @Slot(str)
    def _inference_error(self, message):
        if self._generation_active:
            self._generation_active = False
            self._set_generating(False, "Generierung fehlgeschlagen")
            InfoBar.error("Generierung fehlgeschlagen", message, parent=self, position=InfoBarPosition.TOP, duration=8000)

    def _stop_generation(self):
        if not self._generation_active: return
        self._generation_active = False
        self._set_generating(False, "Generierung abgebrochen")
        self.inference.stop_and_restart()
        InfoBar.warning("Generierung abgebrochen", "Der laufende Chatterbox-Prozess wurde sicher beendet.", parent=self, position=InfoBarPosition.TOP, duration=4500)

    def _set_generating(self, active, status):
        self.generate_button.setEnabled(not active)
        self.stop_button.setVisible(active)
        self.stop_button.setEnabled(active)
        for button in (self.add_voice_button, self.output_button, self.import_text_button, self.project_button, self.history_button, self.favorite_voice_button, self.preview_voice_button, self.rename_voice_button, self.delete_voice_button): button.setEnabled(not active)
        self.voice_combo.setEnabled(not active)
        self.status_ring.setVisible(active)
        self.generation_progress.setVisible(active)
        if not active: self.generation_progress.setRange(0, 100); self.generation_progress.setValue(0)
        self.info_label.setText(status)
        self._update_voice_buttons()

    def _play_audio(self, path: Path, autoplay=True):
        if not path.exists():
            InfoBar.warning("Audio nicht gefunden", str(path), parent=self); return
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.audio_label.setText(path.name)
        self.audio_slider.setValue(0)
        if autoplay: self.player.play()

    def _toggle_audio(self):
        if not self.player.source().isValid():
            if self._last_audio: self._play_audio(Path(self._last_audio))
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState: self.player.pause()
        else: self.player.play()
        self._sync_play_button()

    def _sync_play_button(self):
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setText("Pause" if playing else "Abspielen")
        self.play_button.setIcon(FIF.PAUSE if playing else FIF.PLAY)

    def _player_position(self, position): self.audio_slider.setValue(position)
    def _player_duration(self, duration): self.audio_slider.setRange(0, max(0, duration))

    def dragEnterEvent(self, event: QDragEnterEvent):
        if any(Path(url.toLocalFile()).suffix.lower() in {".wav", ".mp3"} for url in event.mimeData().urls()): event.acceptProposedAction()
        else: event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if Path(path).suffix.lower() in {".wav", ".mp3"}: self._add_voice_file(path)
        event.acceptProposedAction()
