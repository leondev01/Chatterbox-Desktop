# Chatterbox App

Windows-Desktop-App für Chatterbox TTS mit PySide6 und QFluentWidgets.

## Funktionen

- Mehrzeilige Texteingabe
- Emotionsstärke → `exaggeration` 0.0–1.0
- Texteinhaltung → `cfg_weight` 0.0–1.0
- Sprachgeschwindigkeit 0.5x–2.0x über FFmpeg `atempo`
- Lokale Voice-Cloning-Verwaltung
- Persistenter Safe-Location-Ordner
- Persistenter Voice-Auswahlpfad und Dateizähler
- `Voiceover(N).mp3`
- Generierung in einem `QThread`
- Mica-Backdrop unter Windows 11
- FFmpeg-PATH-Prüfung mit UI-Fehlermeldung

## Voraussetzungen

- Windows 10/11
- Python 3.11 wird empfohlen
- NVIDIA GPU + funktionierendes CUDA/PyTorch für `device="cuda"`
- FFmpeg im PATH
- Chatterbox TTS

Chatterbox selbst wird mit `pip install chatterbox-tts` installiert.

## Installation

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

FFmpeg muss anschließend über

```powershell
ffmpeg -version
```

erreichbar sein.

Danach:

```powershell
python main.py
```

## Wichtiger Hinweis zu Chatterbox

Dieses Projekt verwendet absichtlich:

```python
from chatterbox.tts import ChatterboxTTS
ChatterboxTTS.from_pretrained(device="cuda")
```

Das ist das klassische Chatterbox-TTS-Modell. Für die separate multilingual v3 API wäre ein anderer Wrapper (`ChatterboxMultilingualTTS`) und ein `language_id` nötig.

## Konfigurationsdatei

Die App legt automatisch an:

```text
%APPDATA%\ChatterboxDesktopApp\
├── config.json
└── voices\
```

Beispiel:

```json
{
  "selected_voice": "C:\\Users\\User\\AppData\\Roaming\\ChatterboxDesktopApp\\voices\\Meine Stimme.wav",
  "safe_location": "D:\\Voiceovers",
  "counter": 12
}
```

## Dateizähler

Beim Start bzw. vor einer Generierung wird der höchste vorhandene

```text
Voiceover(N).mp3
```

im Safe-Location-Ordner berücksichtigt. Die nächste Generierung bekommt mindestens `N + 1`. Der Wert wird zusätzlich in `config.json` gespeichert.

## FFmpeg

Die Geschwindigkeit wird nicht an Chatterbox übergeben. Nach der WAV-Erzeugung wird

```text
atempo=0.5 ... atempo=2.0
```

verwendet. Dadurch wird die Zeit verändert, ohne einfach die Tonhöhe per Resampling zu verschieben.

## Lizenzhinweis

`PySide6-Fluent-Widgets` ist GPLv3 bzw. für kommerzielle Nutzung lizenzpflichtig. Prüfe die aktuelle Lizenz des Pakets, wenn du die App verteilen oder kommerziell einsetzen möchtest.
