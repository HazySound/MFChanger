"""감독 얼굴 교체 핵심 로직"""

import ctypes
import io
import shutil
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


def load_generic_official_image(config: Config) -> Optional[Image.Image]:
    """공식 얼굴 미리보기용 generic 폴백.
    generic_backup.png 가 있으면 원본 백업을 우선 반환, 없으면 generic.png."""
    manager_dir = get_manager_dir(config)
    for name in ("generic_backup.png", "generic.png"):
        path = manager_dir / name
        if path.exists():
            try:
                return Image.open(path).convert("RGBA")
            except Exception:
                pass
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


def _backup_generic_once(manager_dir: Path):
    """generic.png를 generic_backup.png로 최초 1회 백업. 백업이 이미 있으면 아무것도 안 함."""
    backup = manager_dir / "generic_backup.png"
    if backup.exists():
        return
    generic = manager_dir / "generic.png"
    if generic.exists():
        shutil.copy2(str(generic), str(backup))


def replace_manager(
    manager_id: str,
    manager_name: str,
    team: str,
    src_image_path: Path,
    config: Config,
) -> ManagerChangeRecord:
    """감독 얼굴 교체.

    heads_staff_{id}.png 가 존재하면 해당 파일을 교체.
    존재하지 않으면(generic 폴백 감독) generic.png 를 교체하되,
    최초 1회 generic_backup.png 를 만들어 둔다.
    """
    manager_dir = get_manager_dir(config)
    if not manager_dir.exists():
        raise FileNotFoundError(
            f"감독 이미지 폴더를 찾을 수 없습니다.\n경로: {manager_dir}\n\n"
            "설정에서 FC온라인 설치 경로를 확인해주세요."
        )

    dest = get_manager_file(config, manager_id)
    png_bytes = _to_png_bytes(src_image_path)

    if dest.exists():
        # 고유 파일 존재 → 직접 교체
        _remove_readonly(dest)
        dest.write_bytes(png_bytes)
        _set_readonly(dest)
    else:
        # generic 폴백 감독 → generic.png 교체
        _backup_generic_once(manager_dir)
        generic = manager_dir / "generic.png"
        if generic.exists():
            _remove_readonly(generic)
        generic.write_bytes(png_bytes)
        _set_readonly(generic)

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
    """공식 감독 얼굴로 복원.

    CDN 다운로드에 성공하면 heads_staff_{id}.png 를 덮어씀.
    실패했을 때 고유 파일이 없는 감독(generic 폴백)이면
    generic_backup.png 로 generic.png 를 복원한다.
    백업도 없으면 에러를 그대로 올린다.
    """
    manager_dir = get_manager_dir(config)
    if not manager_dir.exists():
        raise FileNotFoundError(
            f"감독 이미지 폴더를 찾을 수 없습니다.\n경로: {manager_dir}"
        )

    url = f"{CDN_BASE}/live/externalAssets/common/managers/heads_staff_{manager_id}.png"
    try:
        resp = _session.get(url, timeout=15)
        cdn_ok = resp.status_code == 200
    except Exception:
        cdn_ok = False
        resp = None

    if cdn_ok:
        dest = get_manager_file(config, manager_id)
        if dest.exists():
            _remove_readonly(dest)
        dest.write_bytes(resp.content)
        _set_readonly(dest)
        image_path_str = "(공식 얼굴)"
    else:
        # CDN 실패 — generic 폴백 감독(고유 파일 없음) + 백업 있으면 generic 복원
        dest = get_manager_file(config, manager_id)
        backup = manager_dir / "generic_backup.png"
        if not dest.exists() and backup.exists():
            generic = manager_dir / "generic.png"
            if generic.exists():
                _remove_readonly(generic)
            shutil.copy2(str(backup), str(generic))
            _set_readonly(generic)
            image_path_str = "(generic 원본으로 복원)"
        else:
            status = resp.status_code if resp is not None else "연결 실패"
            raise ValueError(f"공식 감독 이미지를 가져올 수 없습니다. (HTTP {status})")

    return ManagerChangeRecord(
        manager_id=manager_id,
        manager_name=manager_name,
        team=team,
        image_path=image_path_str,
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
