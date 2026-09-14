from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QObject, Signal


class InferenceProcess(QObject):
    """Runs Chatterbox in a separate OS process so the Qt UI never freezes."""

    ready = Signal()
    status = Signal(str)
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)
    restarted = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.errorOccurred.connect(self._process_error)
        self.process.finished.connect(self._process_finished)
        self._buffer = ""
        self._stderr_buffer = ""
        self._ready = False
        self._intentional_restart = False
        self._startup_error_sent = False

    @property
    def is_ready(self) -> bool:
        return self._ready and self.process.state() == QProcess.ProcessState.Running

    def start(self) -> None:
        self._ready = False
        self._startup_error_sent = False
        self._buffer = ""
        self._stderr_buffer = ""

        if getattr(sys, "frozen", False):
            program = sys.executable
            arguments = ["--worker"]
            working_dir = str(Path(sys.executable).resolve().parent)
        else:
            program = sys.executable
            arguments = [str(Path(__file__).resolve().parent.parent / "main.py"), "--worker"]
            working_dir = str(Path(__file__).resolve().parent.parent)

        env = QProcess.systemEnvironment()
        env.append("PYTHONUNBUFFERED=1")
        self.process.setEnvironment(env)
        self.process.setWorkingDirectory(working_dir)
        self.process.start(program, arguments)

    def _send(self, payload: dict) -> None:
        if self.process.state() != QProcess.ProcessState.Running:
            self.error.emit("Der Chatterbox-Prozess läuft nicht mehr.")
            return
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        self.process.write(data)
        self.process.waitForBytesWritten(1000)

    def generate(self, payload: dict) -> None:
        if not self.is_ready:
            self.error.emit("Das Chatterbox-Modell ist noch nicht vollständig geladen.")
            return
        self._send({"command": "generate", **payload})

    def stop_and_restart(self) -> None:
        """Hard-cancel generation by killing only the inference process.

        This is safe for the GUI because CUDA/PyTorch lives exclusively in the
        child process. The child is then restarted and reloads the model.
        """
        if self.process.state() == QProcess.ProcessState.NotRunning:
            self.start()
            return
        self._intentional_restart = True
        self._ready = False
        self.process.kill()

    def shutdown(self) -> None:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self._intentional_restart = False
            self._send({"command": "shutdown"})
            if not self.process.waitForFinished(3000):
                self.process.kill()

    def _read_stdout(self) -> None:
        raw = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        self._buffer += raw
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if not line.startswith("CBMSG:"):
                continue
            try:
                message = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            kind = message.get("type")
            if kind == "ready":
                self._ready = True
                self.ready.emit()
            elif kind == "status":
                self.status.emit(str(message.get("message", "")))
            elif kind == "progress":
                self.progress.emit(int(message.get("value", 0)))
            elif kind == "finished":
                self.finished.emit(str(message.get("path", "")))
            elif kind == "error":
                self.error.emit(str(message.get("message", "Unbekannter Fehler.")))

    def _read_stderr(self) -> None:
        # Keep model/library warnings out of the JSON protocol. They remain
        # available to the developer when launching the app from PowerShell.
        self._stderr_buffer += bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")

    def _process_error(self, _error) -> None:
        if self._intentional_restart:
            return
        if not self._ready and not self._startup_error_sent:
            self._startup_error_sent = True
            self.error.emit(self.process.errorString() or "Der Chatterbox-Prozess konnte nicht gestartet werden.")

    def _process_finished(self, exit_code: int, _exit_status) -> None:
        restarting = self._intentional_restart
        self._intentional_restart = False
        was_ready = self._ready
        self._ready = False
        if restarting:
            self.restarted.emit()
            self.start()
            return
        if not was_ready and exit_code != 0 and not self._startup_error_sent:
            self._startup_error_sent = True
            detail = self._stderr_buffer.strip()
            self.error.emit(detail or f"Chatterbox-Prozess wurde mit Code {exit_code} beendet.")
