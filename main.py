import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, IndeterminateProgressBar, SubtitleLabel, Theme, setTheme

from core.inference_process import InferenceProcess
from core.settings import SettingsManager
from ui.main_window import MainWindow

APP_VERSION = "0.0.8"


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

        # Indeterminate mode is deliberately kept alive in the GUI process.
        # Model loading happens in a separate OS process, so this animation
        # cannot freeze when CUDA/PyTorch initialization is busy.
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
            LoadingWindow { border-radius: 18px; background: rgba(32, 32, 32, 245); }
            #loadingSubtitle, #loadingHint { color: rgba(180, 180, 180, 235); }
        """)


def main():
    if "--worker" in sys.argv:
        from core.worker_process import main as worker_main
        return worker_main()

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    setTheme(Theme.AUTO)

    if getattr(sys, "frozen", False):
        app_icon = QIcon(sys.executable)
        app.setWindowIcon(app_icon)
        icon_path = Path(sys.executable)
    else:
        icon_path = Path(__file__).resolve().parent / "app_icon.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))

    settings = SettingsManager()
    settings.ensure_directories()

    loading = LoadingWindow(icon_path)
    loading.show()

    inference = InferenceProcess()
    state = {"window": None}

    def on_ready():
        window = MainWindow(settings=settings, inference=inference)
        window.setWindowTitle(f"Chatterbox · v{APP_VERSION}")
        state["window"] = window
        window.show()
        loading.close()

    def on_error(message: str):
        if state["window"] is not None:
            state["window"]._generation_error(message)
            return
        loading.close()
        from qfluentwidgets import InfoBar
        InfoBar.error(
            "Chatterbox konnte nicht gestartet werden",
            message,
            parent=None,
            duration=10000,
        )
        app.quit()

    inference.ready.connect(on_ready)
    inference.error.connect(on_error)
    inference.start()

    exit_code = app.exec()
    inference.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
