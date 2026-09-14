import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication,QLabel,QVBoxLayout,QWidget
from qfluentwidgets import BodyLabel,IndeterminateProgressBar,SubtitleLabel,Theme,setTheme
from core.inference_process import InferenceProcess
from core.settings import SettingsManager
from ui.main_window import MainWindow
APP_VERSION="0.1.0"
class LoadingWindow(QWidget):
    def __init__(self,icon_path):
        super().__init__(); self.setWindowTitle(f"Chatterbox · v{APP_VERSION}"); self.setFixedSize(440,270); self.setWindowFlag(Qt.WindowStaysOnTopHint,True); self.setWindowFlag(Qt.FramelessWindowHint,True); l=QVBoxLayout(self); l.setContentsMargins(38,34,38,34); l.setSpacing(10); icon=QLabel(); icon.setPixmap(QIcon(str(icon_path)).pixmap(58,58)) if icon_path.exists() else None; icon.setAlignment(Qt.AlignCenter); title=SubtitleLabel("Chatterbox"); title.setAlignment(Qt.AlignCenter); sub=BodyLabel("KI-Sprachmodell wird geladen …"); sub.setAlignment(Qt.AlignCenter); self.progress=IndeterminateProgressBar(start=True); self.progress.setFixedHeight(5); hint=BodyLabel("Das kann beim ersten Start einige Minuten dauern."); hint.setAlignment(Qt.AlignCenter); l.addWidget(icon); l.addWidget(title); l.addWidget(sub); l.addSpacing(10); l.addWidget(self.progress); l.addWidget(hint)
def main():
    if "--worker" in sys.argv:
        from core.worker_process import main as worker_main; return worker_main()
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough); app=QApplication(sys.argv); setTheme(Theme.AUTO); icon_path=Path(sys.executable) if getattr(sys,"frozen",False) else Path(__file__).resolve().parent/"app_icon.ico"; app.setWindowIcon(QIcon(str(icon_path))); settings=SettingsManager(); settings.ensure_directories(); loading=LoadingWindow(icon_path); loading.show(); inference=InferenceProcess(); state={"window":None}
    def ready():
        w=MainWindow(settings,inference); w.setWindowTitle(f"Chatterbox · v{APP_VERSION}"); state["window"]=w; w.show(); loading.close()
    def error(msg):
        loading.close();
        if state["window"] is not None: state["window"]._inference_error(msg)
        else:
            from qfluentwidgets import InfoBar; InfoBar.error("Chatterbox konnte nicht gestartet werden",msg,parent=None,duration=10000); app.quit()
    inference.ready.connect(ready); inference.error.connect(error); inference.start(); code=app.exec(); inference.shutdown(); return code
if __name__=="__main__": raise SystemExit(main())
