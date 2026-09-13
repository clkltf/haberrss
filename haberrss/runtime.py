from __future__ import annotations
import json, os, threading
from dataclasses import dataclass
from .config import settings

PATH=os.getenv('RUNTIME_SETTINGS_PATH','/app/runtime-settings.json')
LOCK=threading.Lock()
DEFAULTS={
 'scan_interval_seconds':settings.scan_interval_seconds,'trend_interval_seconds':settings.trend_interval_seconds,
 'signal_interval_seconds':settings.signal_interval_seconds,'source_timeout_seconds':settings.source_timeout_seconds,
 'max_articles_per_source':settings.max_articles_per_source,'publish_mode':settings.publish_mode,
 'auto_publish_score':settings.auto_publish_score,'alert_score':settings.alert_score,'log_level':settings.log_level}

def load():
    try:
        with open(PATH,encoding='utf-8') as f: data=json.load(f)
        return {**DEFAULTS,**data}
    except (OSError,ValueError,TypeError): return DEFAULTS.copy()

def save(data):
    data={**DEFAULTS,**data}
    os.makedirs(os.path.dirname(PATH),exist_ok=True)
    tmp=PATH+'.tmp'
    with LOCK:
        with open(tmp,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
        os.replace(tmp,PATH)
    return data

@dataclass
class Runtime:
    scan_interval_seconds:int
    trend_interval_seconds:int
    signal_interval_seconds:int
    source_timeout_seconds:int
    max_articles_per_source:int
    publish_mode:str
    auto_publish_score:float
    alert_score:float
    log_level:str

def current(): return Runtime(**load())
