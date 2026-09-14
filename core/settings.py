from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any
APP_NAME="ChatterboxDesktopApp"
class SettingsManager:
    def __init__(self)->None:
        appdata=os.environ.get("APPDATA") or str(Path.home()/"AppData"/"Roaming"); self.base_dir=Path(appdata)/APP_NAME; self.config_path=self.base_dir/"config.json"; self.voices_dir=self.base_dir/"voices"; self.projects_dir=self.base_dir/"projects"; self.history_path=self.base_dir/"history.json"; self.data={"selected_voice":"","safe_location":"","counter":0,"exaggeration":50,"cfg_weight":50,"speed":100,"favorite_voices":[]}; self.load()
    def ensure_directories(self): self.base_dir.mkdir(parents=True,exist_ok=True); self.voices_dir.mkdir(parents=True,exist_ok=True); self.projects_dir.mkdir(parents=True,exist_ok=True)
    def load(self):
        self.ensure_directories()
        if self.config_path.exists():
            try:
                loaded=json.loads(self.config_path.read_text(encoding="utf-8")); self.data.update(loaded) if isinstance(loaded,dict) else None
            except (OSError,json.JSONDecodeError): pass
    def save(self):
        self.ensure_directories(); tmp=self.config_path.with_suffix(".tmp"); tmp.write_text(json.dumps(self.data,indent=2,ensure_ascii=False),encoding="utf-8"); tmp.replace(self.config_path)
    @property
    def selected_voice(self): return str(self.data.get("selected_voice",""))
    @selected_voice.setter
    def selected_voice(self,v): self.data["selected_voice"]=v; self.save()
    @property
    def safe_location(self): return str(self.data.get("safe_location",""))
    @safe_location.setter
    def safe_location(self,v): self.data["safe_location"]=v; self.save()
    @property
    def favorite_voices(self): return [str(x) for x in self.data.get("favorite_voices",[]) if isinstance(x,(str,Path))]
    def toggle_favorite(self,p):
        f=self.favorite_voices; f.remove(p) if p in f else f.append(p); self.data["favorite_voices"]=f; self.save()
    def is_favorite(self,p): return p in self.favorite_voices
    def remove_favorite(self,p):
        f=self.favorite_voices
        if p in f: f.remove(p); self.data["favorite_voices"]=f; self.save()
    def get_slider_value(self,k,d):
        try:return max(0,min(200,int(self.data.get(k,d))))
        except (TypeError,ValueError):return d
    def set_slider_value(self,k,v): self.data[k]=int(v); self.save()
    @property
    def counter(self):
        try:return max(0,int(self.data.get("counter",0)))
        except (TypeError,ValueError):return 0
    @counter.setter
    def counter(self,v): self.data["counter"]=max(0,int(v)); self.save()
    def reserve_next_number(self,out):
        highest=0; d=Path(out)
        if d.exists():
            for p in d.glob("Voiceover(*).mp3"):
                n=p.stem[len("Voiceover("):-1]
                if p.stem.startswith("Voiceover(") and p.stem.endswith(")") and n.isdigit(): highest=max(highest,int(n))
        n=max(self.counter,highest)+1; self.counter=n; return n
    def load_history(self):
        if not self.history_path.exists():return []
        try:
            d=json.loads(self.history_path.read_text(encoding="utf-8")); return d if isinstance(d,list) else []
        except (OSError,json.JSONDecodeError):return []
    def save_history(self,h): self.ensure_directories(); self.history_path.write_text(json.dumps(h[-100:],indent=2,ensure_ascii=False),encoding="utf-8")
