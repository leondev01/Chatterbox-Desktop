from __future__ import annotations
import re, shutil
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QUrl, Qt, Signal, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QFileDialog,QFrame,QHBoxLayout,QLabel,QInputDialog,QListWidget,QListWidgetItem,QMessageBox,QDialog,QScrollArea,QSizePolicy,QVBoxLayout
from qfluentwidgets import BodyLabel,CardWidget,ComboBox,FluentIcon as FIF,InfoBar,InfoBarPosition,LineEdit,PrimaryPushButton,ProgressBar,ProgressRing,PushButton,Slider,SubtitleLabel,TextEdit,TitleLabel
from core.audio_export import ffmpeg_available
from core.inference_process import InferenceProcess
from core.projects import load_project,project_path,safe_project_name,save_project
from core.settings import SettingsManager
class SliderRow(QFrame):
    valueChanged=Signal(int)
    def __init__(self,title,description,minimum,maximum,value,suffix="",parent=None):
        super().__init__(parent); self.setObjectName("sliderCard"); self.setMinimumHeight(92); l=QVBoxLayout(self); l.setContentsMargins(18,9,18,7); l.setSpacing(1); t=QHBoxLayout(); self.title=BodyLabel(title); self.value_label=BodyLabel(); t.addWidget(self.title); t.addStretch(); t.addWidget(self.value_label); self.description=QLabel(description); self.description.setObjectName("mutedLabel"); self.slider=Slider(Qt.Horizontal); self.slider.setRange(minimum,maximum); self.slider.setValue(value); self.suffix=suffix; l.addLayout(t); l.addWidget(self.description); l.addWidget(self.slider); self.slider.valueChanged.connect(self._update); self._update(value)
    def _update(self,v): self.value_label.setText(f"{v/100:.2f}x" if self.suffix=="x" else f"{v}{self.suffix}" if self.suffix else str(v)); self.valueChanged.emit(v)
class MainWindow(QWidget):
    def __init__(self,settings,inference):
        super().__init__(); self.settings=settings; self.inference=inference; self._generation_active=False; self._last_audio=""; self.setAcceptDrops(True); self.inference.status.connect(self._generation_status); self.inference.progress.connect(self._generation_progress); self.inference.progress_mode.connect(self._generation_progress_mode); self.inference.finished.connect(self._generation_finished); self.inference.error.connect(self._inference_error); self.player=QMediaPlayer(self); self.audio_output=QAudioOutput(self); self.player.setAudioOutput(self.audio_output); self.player.positionChanged.connect(lambda p:self.audio_slider.setValue(p)); self.player.durationChanged.connect(lambda d:self.audio_slider.setRange(0,max(0,d))); self.player.playbackStateChanged.connect(self._sync_play_button); self.resize(1120,820); self.setMinimumSize(820,580); self._build_ui(); self._load_voices(); self._load_persistent_values(); self._check_ffmpeg()
    def _build_ui(self):
        root=QVBoxLayout(self); root.setContentsMargins(28,24,28,22); header=QHBoxLayout(); box=QVBoxLayout(); box.addWidget(TitleLabel("Chatterbox Desktop")); sub=BodyLabel("Voiceover-Generator mit Chatterbox TTS"); sub.setObjectName("mutedLabel"); box.addWidget(sub); header.addLayout(box); header.addStretch(); self.status_ring=ProgressRing(); self.status_ring.hide(); header.addWidget(self.status_ring); root.addLayout(header)
        content=QWidget(); cl=QVBoxLayout(content); tc=CardWidget(); tl=QVBoxLayout(tc); top=QHBoxLayout(); top.addWidget(SubtitleLabel("Text")); top.addStretch(); self.import_button=PushButton(FIF.FOLDER,"Text importieren"); self.project_button=PushButton(FIF.SAVE,"Projekte"); self.history_button=PushButton(FIF.HISTORY,"Historie"); top.addWidget(self.import_button); top.addWidget(self.project_button); top.addWidget(self.history_button); tl.addLayout(top); self.text_edit=TextEdit(); self.text_edit.setMinimumHeight(210); self.text_edit.setPlaceholderText("Schreibe hier den Text, der vorgelesen werden soll..."); tl.addWidget(self.text_edit); cl.addWidget(tc); self.generation_progress=ProgressBar(); self.generation_progress.hide(); self.generation_progress.setFixedHeight(6); cl.addWidget(self.generation_progress)
        controls=QHBoxLayout(); left=CardWidget(); ll=QVBoxLayout(left); ll.addWidget(SubtitleLabel("Stimme")); vr=QHBoxLayout(); self.voice_combo=ComboBox(); self.voice_combo.setPlaceholderText("Stimme auswählen"); vr.addWidget(self.voice_combo,1); self.favorite_button=PushButton("☆"); self.preview_button=PushButton(FIF.PLAY,"Vorschau"); self.rename_button=PushButton(FIF.EDIT,"Umbenennen"); self.delete_button=PushButton(FIF.DELETE,"Löschen"); [vr.addWidget(b) for b in (self.favorite_button,self.preview_button,self.rename_button,self.delete_button)]; ll.addLayout(vr); self.add_button=PrimaryPushButton(FIF.ADD,"Stimme hinzufügen"); ll.addWidget(self.add_button); out=QHBoxLayout(); self.output_edit=LineEdit(); self.output_edit.setReadOnly(True); self.output_button=PushButton(FIF.FOLDER,"Ordner auswählen"); out.addWidget(self.output_edit,1); out.addWidget(self.output_button); ll.addWidget(SubtitleLabel("Ausgabeordner")); ll.addLayout(out); controls.addWidget(left,1)
        right=CardWidget(); rl=QVBoxLayout(right); rl.addWidget(SubtitleLabel("Feineinstellungen")); self.exaggeration=SliderRow("Emotionsstärke","Chatterbox exaggeration · 0.0 bis 1.0",0,100,50); self.cfg_weight=SliderRow("Texteinhaltung","Chatterbox cfg_weight · 0.0 bis 1.0",0,100,50); self.speed=SliderRow("Sprachgeschwindigkeit","1.00x entspricht normal",50,200,100,"x"); [rl.addWidget(x) for x in (self.exaggeration,self.cfg_weight,self.speed)]; controls.addWidget(right,1); cl.addLayout(controls)
        audio=CardWidget(); al=QHBoxLayout(audio); al.addWidget(SubtitleLabel("Audio")); self.audio_label=BodyLabel("Noch kein Audio geladen"); al.addWidget(self.audio_label); al.addStretch(); self.play_button=PushButton(FIF.PLAY,"Abspielen"); self.audio_slider=Slider(Qt.Horizontal); self.audio_slider.setRange(0,0); self.audio_slider.sliderMoved.connect(self.player.setPosition); al.addWidget(self.play_button); al.addWidget(self.audio_slider,1); cl.addWidget(audio); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(content); scroll.setFrameShape(QFrame.NoFrame); root.addWidget(scroll,1)
        footer=QHBoxLayout(); self.info_label=BodyLabel("Bereit"); self.info_label.setObjectName("mutedLabel"); self.generate_button=PrimaryPushButton(FIF.PLAY,"Voiceover generieren"); self.stop_button=PushButton(FIF.CLOSE,"Generierung stoppen"); self.stop_button.hide(); footer.addWidget(self.info_label); footer.addStretch(); footer.addWidget(self.stop_button); footer.addWidget(self.generate_button); root.addLayout(footer)
        self.import_button.clicked.connect(self._import_text); self.project_button.clicked.connect(self._open_projects); self.history_button.clicked.connect(self._open_history); self.add_button.clicked.connect(self._add_voice); self.preview_button.clicked.connect(self._preview_voice); self.rename_button.clicked.connect(self._rename_voice); self.delete_button.clicked.connect(self._delete_voice); self.favorite_button.clicked.connect(self._toggle_favorite); self.output_button.clicked.connect(self._choose_output); self.generate_button.clicked.connect(self._generate); self.stop_button.clicked.connect(self._stop_generation); self.play_button.clicked.connect(self._toggle_audio); self.voice_combo.currentIndexChanged.connect(self._voice_changed); self.exaggeration.valueChanged.connect(lambda v:self.settings.set_slider_value("exaggeration",v)); self.cfg_weight.valueChanged.connect(lambda v:self.settings.set_slider_value("cfg_weight",v)); self.speed.valueChanged.connect(lambda v:self.settings.set_slider_value("speed",v))
    def _load_persistent_values(self): self.exaggeration.slider.setValue(self.settings.get_slider_value("exaggeration",50)); self.cfg_weight.slider.setValue(self.settings.get_slider_value("cfg_weight",50)); self.speed.slider.setValue(self.settings.get_slider_value("speed",100)); self.output_edit.setText(self.settings.safe_location if Path(self.settings.safe_location).exists() else "")
    def _check_ffmpeg(self):
        if not ffmpeg_available(): InfoBar.warning("FFmpeg nicht gefunden","Starte build.bat für die automatische Einrichtung.",parent=self,duration=6000)
    def _voice_files(self): return sorted([p for p in self.settings.voices_dir.iterdir() if p.suffix.lower() in {".wav",".mp3"}],key=lambda p:(not self.settings.is_favorite(str(p)),p.stem.lower()))
    def _load_voices(self):
        self.voice_combo.blockSignals(True); self.voice_combo.clear(); files=self._voice_files(); [self.voice_combo.addItem(("★ " if self.settings.is_favorite(str(p)) else "")+p.stem,str(p)) for p in files]; self.voice_combo.blockSignals(False); i=self.voice_combo.findData(self.settings.selected_voice); self.voice_combo.setCurrentIndex(i if i>=0 else 0); self._update_voice_buttons()
    def _current_voice(self): return Path(self.voice_combo.currentData()) if self.voice_combo.currentData() else None
    def _update_voice_buttons(self):
        p=self._current_voice(); ok=bool(p and p.exists()); [b.setEnabled(ok and not self._generation_active) for b in (self.favorite_button,self.preview_button,self.rename_button,self.delete_button)]; self.favorite_button.setText("★" if ok and self.settings.is_favorite(str(p)) else "☆")
    def _voice_changed(self,i):
        if i>=0:self.settings.selected_voice=str(self.voice_combo.itemData(i) or "")
        self._update_voice_buttons()
    def _add_voice_file(self,source):
        p=Path(source); name,ok=QInputDialog.getText(self,"Stimme benennen","Name der Stimme:",text=p.stem)
        if not ok:return
        safe=re.sub(r'[<>:"/\\|?*]+',"_",name.strip()).strip(". ") or "Stimme"; dest=self.settings.voices_dir/f"{safe}{p.suffix.lower()}"; n=2
        while dest.exists():dest=self.settings.voices_dir/f"{safe} ({n}){p.suffix.lower()}"; n+=1
        shutil.copy2(p,dest); self._load_voices(); self.voice_combo.setCurrentIndex(self.voice_combo.findData(str(dest)))
    def _add_voice(self):
        p,_=QFileDialog.getOpenFileName(self,"Referenz-Audio auswählen","","Audio-Dateien (*.wav *.mp3)"); self._add_voice_file(p) if p else None
    def _preview_voice(self): self._play_audio(self._current_voice())
    def _rename_voice(self):
        p=self._current_voice();
        if not p:return
        name,ok=QInputDialog.getText(self,"Stimme umbenennen","Neuer Name:",text=p.stem)
        if not ok:return
        new=p.with_name(safe_project_name(name)+p.suffix); old=str(p); p.rename(new); self.settings.selected_voice=str(new) if self.settings.selected_voice==old else self.settings.selected_voice
        if self.settings.is_favorite(old):self.settings.remove_favorite(old);self.settings.toggle_favorite(str(new))
        self._load_voices()
    def _delete_voice(self):
        p=self._current_voice();
        if not p:return
        if QMessageBox.question(self,"Stimme löschen",f"„{p.stem}“ wirklich löschen?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:p.unlink(missing_ok=True);self.settings.remove_favorite(str(p));self.settings.selected_voice="" if self.settings.selected_voice==str(p) else self.settings.selected_voice;self._load_voices()
    def _toggle_favorite(self):
        p=self._current_voice();
        if p:self.settings.toggle_favorite(str(p));self._load_voices();self.voice_combo.setCurrentIndex(self.voice_combo.findData(str(p)))
    def _import_text(self):
        p,_=QFileDialog.getOpenFileName(self,"Textdatei importieren","","Textdateien (*.txt *.md)");
        if p:self.text_edit.setPlainText(Path(p).read_text(encoding="utf-8"))
    def _project_payload(self):return {"text":self.text_edit.toPlainText(),"voice_path":str(self.voice_combo.currentData() or ""),"exaggeration":self.exaggeration.slider.value(),"cfg_weight":self.cfg_weight.slider.value(),"speed":self.speed.slider.value(),"output_dir":self.output_edit.text()}
    def _apply_project(self,p): self.text_edit.setPlainText(p.get("text",""));i=self.voice_combo.findData(p.get("voice_path",""));self.voice_combo.setCurrentIndex(i) if i>=0 else None;self.exaggeration.slider.setValue(int(p.get("exaggeration",50)));self.cfg_weight.slider.setValue(int(p.get("cfg_weight",50)));self.speed.slider.setValue(int(p.get("speed",100)));self.output_edit.setText(p.get("output_dir",""))
    def _open_projects(self):
        d=QDialog(self);d.setWindowTitle("Projekte");d.resize(560,430);l=QVBoxLayout(d);listing=QListWidget();l.addWidget(listing);row=QHBoxLayout();save=PrimaryPushButton(FIF.SAVE,"Speichern");openb=PushButton(FIF.ACCEPT,"Öffnen");rename=PushButton(FIF.EDIT,"Umbenennen");delete=PushButton(FIF.DELETE,"Löschen");[row.addWidget(b) for b in (save,openb,rename,delete)];l.addLayout(row)
        def refresh(sel=""):
            listing.clear();[listing.addItem(p.stem) for p in sorted(self.settings.projects_dir.glob("*.json"))];h=listing.findItems(sel,Qt.MatchExactly);listing.setCurrentItem(h[0]) if h else None
        def save_ui():
            n,ok=QInputDialog.getText(d,"Projekt speichern","Projektname:");
            if ok and n.strip():save_project(self.settings.projects_dir,n,self._project_payload());refresh(safe_project_name(n))
        def open_ui():
            i=listing.currentItem();
            if i:self._apply_project(load_project(project_path(self.settings.projects_dir,i.text())));d.accept()
        def rename_ui():
            i=listing.currentItem();
            if i:
                n,ok=QInputDialog.getText(d,"Projekt umbenennen","Neuer Name:",text=i.text());
                if ok and n.strip():project_path(self.settings.projects_dir,i.text()).rename(project_path(self.settings.projects_dir,n));refresh(safe_project_name(n))
        def delete_ui():
            i=listing.currentItem();
            if i and QMessageBox.question(d,"Projekt löschen",f"„{i.text()}“ wirklich löschen?",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:project_path(self.settings.projects_dir,i.text()).unlink(missing_ok=True);refresh()
        refresh();save.clicked.connect(save_ui);openb.clicked.connect(open_ui);rename.clicked.connect(rename_ui);delete.clicked.connect(delete_ui);listing.itemDoubleClicked.connect(lambda _:open_ui());d.exec()
    def _open_history(self):
        d=QDialog(self);d.setWindowTitle("Generierungs-Historie");d.resize(650,450);l=QVBoxLayout(d);listing=QListWidget();l.addWidget(listing);h=list(reversed(self.settings.load_history()));
        for e in h:it=QListWidgetItem(f"{e.get('timestamp','')} · {Path(e.get('path','')).name}");it.setData(Qt.UserRole,e);listing.addItem(it)
        row=QHBoxLayout();play=PushButton(FIF.PLAY,"Abspielen");regen=PrimaryPushButton(FIF.SYNC,"Erneut generieren");row.addWidget(play);row.addWidget(regen);l.addLayout(row)
        def sel():return listing.currentItem().data(Qt.UserRole) if listing.currentItem() else None
        play.clicked.connect(lambda:self._play_audio(Path(sel().get("path",""))) if sel() else None);regen.clicked.connect(lambda:(self._apply_project(sel()),d.accept(),self._generate()) if sel() else None);d.exec()
    def _choose_output(self):
        p=QFileDialog.getExistingDirectory(self,"Safe-Location auswählen",str(Path.home()));
        if p:self.settings.safe_location=p;self.output_edit.setText(p)
    def _generate(self):
        text=self.text_edit.toPlainText().strip();out=self.output_edit.text().strip()
        if not text or not out or not Path(out).exists() or not ffmpeg_available() or not self.inference.is_ready:return
        n=self.settings.reserve_next_number(out);payload={"text":text,"exaggeration":self.exaggeration.slider.value()/100,"cfg_weight":self.cfg_weight.slider.value()/100,"speed":self.speed.slider.value()/100,"voice_path":str(self.voice_combo.currentData() or ""),"output_dir":out,"number":n};self._generation_active=True;self._set_generating(True,f"Generiere Voiceover({n}).mp3 …");self.inference.generate(payload)
    def _generation_status(self,m):
        if self._generation_active:self.info_label.setText(m)
    def _generation_progress_mode(self,m):
        if self._generation_active:self.generation_progress.setRange(0,0) if m=="busy" else self.generation_progress.setRange(0,100)
    def _generation_progress(self,v):
        if self._generation_active:
            if self.generation_progress.maximum()==0:self.generation_progress.setRange(0,100)
            self.generation_progress.setValue(v)
    def _generation_finished(self,path):
        self._generation_active=False;self._set_generating(False,f"Fertig: {Path(path).name}");self._last_audio=path;self._play_audio(Path(path),False);h=self.settings.load_history();p=self._project_payload();p.update({"path":path,"timestamp":datetime.now().strftime("%Y-%m-%d %H:%M:%S")});h.append(p);self.settings.save_history(h)
    def _inference_error(self,m):
        if self._generation_active:self._generation_active=False;self._set_generating(False,"Generierung fehlgeschlagen");InfoBar.error("Generierung fehlgeschlagen",m,parent=self,position=InfoBarPosition.TOP)
    def _stop_generation(self):
        if self._generation_active:self._generation_active=False;self._set_generating(False,"Generierung abgebrochen");self.inference.stop_and_restart()
    def _set_generating(self,a,status):self.generate_button.setEnabled(not a);self.stop_button.setVisible(a);self.generation_progress.setVisible(a);self.status_ring.setVisible(a);self.info_label.setText(status);self._update_voice_buttons()
    def _play_audio(self,p,autoplay=True):
        if p and p.exists():self.player.setSource(QUrl.fromLocalFile(str(p)));self.audio_label.setText(p.name);self.audio_slider.setValue(0);self.player.play() if autoplay else None
    def _toggle_audio(self):self.player.pause() if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState else self.player.play()
    def _sync_play_button(self,*_):self.play_button.setText("Pause" if self.player.playbackState()==QMediaPlayer.PlaybackState.PlayingState else "Abspielen")
    def dragEnterEvent(self,e):e.acceptProposedAction() if any(Path(u.toLocalFile()).suffix.lower() in {".wav",".mp3"} for u in e.mimeData().urls()) else e.ignore()
    def dropEvent(self,e):
        for u in e.mimeData().urls():
            if Path(u.toLocalFile()).suffix.lower() in {".wav",".mp3"}:self._add_voice_file(u.toLocalFile())
        e.acceptProposedAction()
