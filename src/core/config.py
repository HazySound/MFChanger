"""설정 관리 모듈 - JSON 파일로 영구 저장"""

import json
import os
import sys
from pathlib import Path


def _app_dir() -> Path:
    """영구 데이터(.cache / config.json / history 등)의 기준 폴더.

    빌드(frozen): exe 파일이 들어있는 폴더.
    개발 환경: 프로젝트 루트.
    cwd(현재 작업 폴더)가 아니라 exe/스크립트의 실제 위치를 직접 사용한다 —
    실행 방식(바로가기·관리자 권한·탐색기 등)과 무관하게 항상 고정.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


APP_DIR = _app_dir()
CACHE_DIR = APP_DIR / ".cache"

CONFIG_PATH = APP_DIR / "config.json"
API_KEY_PATH = APP_DIR / "api_key.txt"

DEFAULT_FC_PATH = r"C:\Nexon\EA SPORTS(TM) FC ONLINE"
FACE_SUBPATH = r"_cache\live\externalAssets\common\playersAction"
CREST_SUBPATH = r"_cache\live\externalAssets\common\crests"

DEFAULTS = {
    "fc_online_path": DEFAULT_FC_PATH,
    "backup_enabled": True,
    "backup_path": str(Path.home() / "MFChanger_backup"),
    "check_update_on_start": True,
    "theme": "dark",
    "ui_scale": 1.5,
}


class Config:
    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        # 누락된 기본값 채우기
        for key, val in DEFAULTS.items():
            self._data.setdefault(key, val)

    def save(self):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    @property
    def fc_online_path(self) -> str:
        return self._data["fc_online_path"]

    @fc_online_path.setter
    def fc_online_path(self, value: str):
        self.set("fc_online_path", value)

    @property
    def assets_dir(self) -> Path:
        """CDN 캐시 루트 (_cache/live/externalAssets/common)."""
        return Path(self.fc_online_path) / r"_cache\live\externalAssets\common"

    @property
    def face_dir(self) -> Path:
        return Path(self.fc_online_path) / FACE_SUBPATH

    @property
    def crest_dir(self) -> Path:
        return Path(self.fc_online_path) / CREST_SUBPATH

    @property
    def manager_dir(self) -> Path:
        return Path(self.fc_online_path) / r"_cache\live\externalAssets\common\managers"

    @property
    def backup_enabled(self) -> bool:
        return self._data["backup_enabled"]

    @backup_enabled.setter
    def backup_enabled(self, value: bool):
        self.set("backup_enabled", value)

    @property
    def backup_path(self) -> Path:
        return Path(self._data["backup_path"])

    @backup_path.setter
    def backup_path(self, value: str):
        self.set("backup_path", value)

    @property
    def check_update_on_start(self) -> bool:
        return self._data["check_update_on_start"]

    @check_update_on_start.setter
    def check_update_on_start(self, value: bool):
        self.set("check_update_on_start", value)

    @property
    def ui_scale(self) -> float:
        return float(self._data.get("ui_scale", 1.5))

    @ui_scale.setter
    def ui_scale(self, value: float):
        self.set("ui_scale", value)

    def get_api_key(self) -> str:
        if API_KEY_PATH.exists():
            return API_KEY_PATH.read_text(encoding="utf-8").strip()
        return ""

    def is_fc_path_valid(self) -> bool:
        return self.face_dir.exists()

    def is_crest_path_valid(self) -> bool:
        return self.crest_dir.exists()
