"""감독 얼굴 교체 핵심 로직"""

import ctypes
import io
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from .config import Config

CDN_BASE = "https://fco.dn.nexoncdn.co.kr"
_session = requests.Session()
_session.headers.update({"User-Agent": "MFChanger/1.0"})


@dataclass
class ManagerChangeRecord:
    manager_id: str
    manager_name: str
    team: str
    image_path: str
    changed_at: str

MANAGER_SUBPATH = r"_cache\live\externalAssets\common\managers"


def get_manager_dir(config: Config) -> Path:
    return Path(config.fc_online_path) / MANAGER_SUBPATH


def get_manager_file(config: Config, manager_id: str) -> Path:
    return get_manager_dir(config) / f"heads_staff_{manager_id}.png"


def load_manager_image(config: Config, manager_id: str) -> Optional[Image.Image]:
    path = get_manager_file(config, manager_id)
    if not path.exists():
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def load_generic_image(config: Config) -> Optional[Image.Image]:
    """이미지가 없는 감독용 generic.png 로드."""
    path = get_manager_dir(config) / "generic.png"
    if not path.exists():
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def _set_readonly(path: Path):
    path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    try:
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x1)
    except Exception:
        pass


def _remove_readonly(path: Path):
    try:
        path.chmod(stat.S_IWRITE | stat.S_IREAD)
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x80)
    except Exception:
        pass


def _to_png_bytes(src_path: Path) -> bytes:
    img = Image.open(src_path).convert("RGBA")
    w, h = img.size
    if w != h:
        side = min(w, h)
        img = img.crop(((w - side) // 2, (h - side) // 2,
                        (w - side) // 2 + side, (h - side) // 2 + side))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def replace_manager(
    manager_id: str,
    manager_name: str,
    team: str,
    src_image_path: Path,
    config: Config,
) -> ManagerChangeRecord:
    """감독 얼굴 교체."""
    manager_dir = get_manager_dir(config)
    if not manager_dir.exists():
        raise FileNotFoundError(
            f"감독 이미지 폴더를 찾을 수 없습니다.\n경로: {manager_dir}\n\n"
            "설정에서 FC온라인 설치 경로를 확인해주세요."
        )

    dest = get_manager_file(config, manager_id)
    if dest.exists():
        _remove_readonly(dest)

    png_bytes = _to_png_bytes(src_image_path)
    dest.write_bytes(png_bytes)
    _set_readonly(dest)

    return ManagerChangeRecord(
        manager_id=manager_id,
        manager_name=manager_name,
        team=team,
        image_path=str(src_image_path),
        changed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def restore_to_official(
    manager_id: str,
    manager_name: str,
    team: str,
    config: Config,
) -> ManagerChangeRecord:
    """CDN에서 공식 감독 얼굴을 다운로드해 덮어씀."""
    manager_dir = get_manager_dir(config)
    if not manager_dir.exists():
        raise FileNotFoundError(
            f"감독 이미지 폴더를 찾을 수 없습니다.\n경로: {manager_dir}"
        )

    url = f"{CDN_BASE}/live/externalAssets/common/managers/heads_staff_{manager_id}.png"
    resp = _session.get(url, timeout=15)
    if resp.status_code != 200:
        raise ValueError(f"공식 감독 이미지를 가져올 수 없습니다. (HTTP {resp.status_code})")

    dest = get_manager_file(config, manager_id)
    if dest.exists():
        _remove_readonly(dest)
    dest.write_bytes(resp.content)
    _set_readonly(dest)

    return ManagerChangeRecord(
        manager_id=manager_id,
        manager_name=manager_name,
        team=team,
        image_path="(공식 얼굴)",
        changed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def fetch_official_image(manager_id: str) -> Optional[Image.Image]:
    """CDN에서 공식 감독 얼굴 이미지 반환 (미리보기용). 없으면 None."""
    from io import BytesIO
    url = f"{CDN_BASE}/live/externalAssets/common/managers/heads_staff_{manager_id}.png"
    try:
        resp = _session.get(url, timeout=10)
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception:
        pass
    return None


def is_manager_dir_valid(config: Config) -> bool:
    return get_manager_dir(config).exists()
