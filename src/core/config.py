"""설정 관리 모듈 - JSON 파일로 영구 저장"""

import json
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

ASSETS_SUBPATH = Path("_cache/live/externalAssets/common")

DEFAULTS = {
    "fc_online_path": r"C:\Nexon\EA SPORTS(TM) FC ONLINE",
    "backup_enabled": True,
    "backup_path": str(Path.home() / "MFChanger_backup"),
    "check_update_on_start": True,
    "zoom": 1.0,
}

# 이전 버전(tkinter UI)에서만 쓰던 키 — 불러올 때 정리
_OBSOLETE_KEYS = ("theme", "ui_scale")


class Config:
    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        try:
            self._data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self._data = {}
        for key in _OBSOLETE_KEYS:
            self._data.pop(key, None)
        for key, val in DEFAULTS.items():
            self._data.setdefault(key, val)

    def save(self):
        CONFIG_PATH.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def update(self, **values):
        """알려진 설정 키만 반영하고 저장."""
        unknown = set(values) - set(DEFAULTS)
        if unknown:
            raise KeyError(f"알 수 없는 설정: {', '.join(sorted(unknown))}")
        self._data.update(values)
        self.save()

    def as_dict(self) -> dict:
        return {key: self._data[key] for key in DEFAULTS}

    @property
    def fc_online_path(self) -> str:
        return self._data["fc_online_path"]

    @property
    def assets_dir(self) -> Path:
        """CDN 캐시 루트 (_cache/live/externalAssets/common)."""
        return Path(self.fc_online_path) / ASSETS_SUBPATH

    @property
    def crest_dir(self) -> Path:
        return self.assets_dir / "crests"

    @property
    def manager_dir(self) -> Path:
        return self.assets_dir / "managers"

    @property
    def backup_enabled(self) -> bool:
        return self._data["backup_enabled"]

    @property
    def backup_path(self) -> Path:
        return Path(self._data["backup_path"])

    @property
    def check_update_on_start(self) -> bool:
        return self._data["check_update_on_start"]

    def is_fc_path_valid(self) -> bool:
        return self.assets_dir.exists()
