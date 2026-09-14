import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from qfluentwidgets import Theme, setTheme

from core.settings import SettingsManager
from core.tts_engine import TTSEngine
from ui.main_window import MainWindow

APP_VERSION = "0.0.1"

def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    setTheme(Theme.AUTO)

    settings = SettingsManager()
    settings.ensure_directories()

    # The requested Chatterbox model is loaded once during application startup.
    engine = TTSEngine(device="cuda")

    window = MainWindow(settings=settings, engine=engine)
    window.setWindowTitle(f"Chatterbox Desktop · v{APP_VERSION}")
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
