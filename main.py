import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    IndeterminateProgressBar,
    SubtitleLabel,
    Theme,
    setTheme,
)

from core.settings import SettingsManager
from core.tts_engine import TTSEngine
from ui.main_window import MainWindow

APP_VERSION = "0.0.6"


class StartupLoader(QObject):
    ready = Signal(object)
    error = Signal(str)

    @Slot()
    def run(self) -> None:
        try:
            engine = TTSEngine(device="cuda")
            self.ready.emit(engine)
        except Exception as exc:
            self.error.emit(str(exc))


class LoadingWindow(QWidget):
    def __init__(self, icon_path: Path):
        super().__init__()
        self.setWindowTitle(f"Chatterbox · v{APP_VERSION}")
        self.setFixedSize(440, 270)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(38, 34, 38, 34)
        layout.setSpacing(10)

        icon = QLabel()
        if icon_path.exists():
            icon.setPixmap(QIcon(str(icon_path)).pixmap(58, 58))
        icon.setAlignment(Qt.AlignCenter)

        title = SubtitleLabel("Chatterbox")
        title.setAlignment(Qt.AlignCenter)

        subtitle = BodyLabel("KI-Sprachmodell wird geladen …")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("loadingSubtitle")

        self.progress = IndeterminateProgressBar(start=True)
        self.progress.setFixedHeight(5)

        hint = BodyLabel("Das kann beim ersten Start einige Minuten dauern.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setObjectName("loadingHint")

        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.progress)
        layout.addSpacing(4)
        layout.addWidget(hint)

        self.setStyleSheet("""
            LoadingWindow {
                border-radius: 18px;
                background: rgba(32, 32, 32, 245);
            }
            #loadingSubtitle, #loadingHint {
                color: rgba(180, 180, 180, 235);
            }
        """)


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    setTheme(Theme.AUTO)

    if getattr(sys, "frozen", False):
        icon = QIcon(sys.executable)
        app.setWindowIcon(icon)
        icon_path = Path(sys.executable)
    else:
        icon_path = Path(__file__).resolve().parent / "app_icon.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))

    settings = SettingsManager()
    settings.ensure_directories()

    loading = LoadingWindow(icon_path)
    loading.show()

    loader_thread = QThread()
    loader = StartupLoader()
    loader.moveToThread(loader_thread)

    state = {"window": None, "engine": None}

    def on_ready(engine):
        state["engine"] = engine
        window = MainWindow(settings=settings, engine=engine)
        window.setWindowTitle(f"Chatterbox · v{APP_VERSION}")
        state["window"] = window
        window.show()
        loading.close()
        loader_thread.quit()

    def on_error(message):
        loading.close()
        from qfluentwidgets import InfoBar
        InfoBar.error(
            "Chatterbox konnte nicht gestartet werden",
            message,
            parent=None,
            duration=10000,
        )
        loader_thread.quit()
        app.quit()

    loader.ready.connect(on_ready)
    loader.error.connect(on_error)
    loader_thread.started.connect(loader.run)
    loader_thread.finished.connect(loader.deleteLater)
    loader_thread.finished.connect(loader_thread.deleteLater)
    loader_thread.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
