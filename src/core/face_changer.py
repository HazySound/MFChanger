"""미페 교체 핵심 로직"""

import ctypes
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image

from .config import Config


@dataclass
class ChangeRecord:
    spid: int
    player_name: str
    image_path: str
    changed_at: str
    backup_path: Optional[str] = None
    result_path: Optional[str] = None   # 이 기록이 적용한 결과 스냅샷
    # 실제로 덮어쓴 게임 파일 (assets 기준 상대 경로, 예: "players/p190871.png")
    # None = 구버전 기록 → playersAction/p{spid}.png
    target_path: Optional[str] = None


def target_file(config: Config, spid: int, target_path: Optional[str]) -> Path:
    """기록/조회 결과의 상대 경로 → 실제 게임 파일 경로."""
    rel = target_path or f"playersAction/p{spid}.png"
    return config.assets_dir / rel


def _check_assets_dir(config: Config):
    if not config.face_dir.exists():
        raise FileNotFoundError(
            f"FC온라인 미페 폴더를 찾을 수 없습니다.\n경로: {config.face_dir}\n\n"
            "설정에서 FC온라인 설치 경로를 확인해주세요."
        )


def _write_game_file(spid: int, dest_file: Path, png_bytes: bytes, config: Config):
    """기존 파일 백업 → 덮어쓰기 → 읽기전용 → 결과 스냅샷. (backup_path, result_path) 반환."""
    backup_path: Optional[str] = None
    backup_dir = config.backup_path / f"p{spid}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    if dest_file.exists():
        _remove_readonly(dest_file)
        if config.backup_enabled:
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = backup_dir / f"p{spid}_backup_{timestamp}.png"
            shutil.copy2(dest_file, backup_file)
            backup_path = str(backup_file)

    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_bytes(png_bytes)
    _set_readonly(dest_file)

    result_path: Optional[str] = None
    if config.backup_enabled:
        backup_dir.mkdir(parents=True, exist_ok=True)
        result_file = backup_dir / f"p{spid}_result_{timestamp}.png"
        result_file.write_bytes(png_bytes)
        result_path = str(result_file)

    return backup_path, result_path


def _set_readonly(path: Path):
    """파일을 읽기전용으로 설정 (Windows)."""
    # stat 방식
    path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    # Windows FILE_ATTRIBUTE_READONLY 추가 설정
    try:
        FILE_ATTRIBUTE_READONLY = 0x1
        ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_READONLY)
    except Exception:
        pass


def _remove_readonly(path: Path):
    """읽기전용 해제."""
    try:
        path.chmod(stat.S_IWRITE | stat.S_IREAD)
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x80)  # NORMAL
    except Exception:
        pass


def _convert_to_png(src_path: Path) -> bytes:
    """이미지를 PNG bytes로 변환. 비정방형이면 중앙 크롭 후 변환."""
    img = Image.open(src_path).convert("RGBA")
    w, h = img.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def replace_face(
    spid: int,
    player_name: str,
    src_image_path: Path,
    config: Config,
    target_path: Optional[str] = None,
) -> ChangeRecord:
    """
    미페 교체 실행.

    target_path: 게임이 실제 사용하는 파일의 상대 경로 (datacenter.resolve_face_path).
                 None이면 playersAction/p{spid}.png.
    1. 기존 파일 백업 (설정에 따라)
    2. src_image_path → PNG 변환 후 덮어쓰기
    3. 읽기전용 설정
    """
    _check_assets_dir(config)
    dest_file = target_file(config, spid, target_path)
    png_bytes = _convert_to_png(src_image_path)
    backup_path, result_path = _write_game_file(spid, dest_file, png_bytes, config)

    return ChangeRecord(
        spid=spid,
        player_name=player_name,
        image_path=str(src_image_path),
        changed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        backup_path=backup_path,
        result_path=result_path,
        target_path=target_path,
    )


def restore_to_official(
    spid: int,
    player_name: str,
    config: Config,
    target_path: Optional[str] = None,
) -> ChangeRecord:
    """
    공식 미페(CDN)를 다운로드해 로컬 파일로 덮어씀.
    target_path가 있으면 CDN의 같은 경로 파일을 그대로 받아온다.
    기존 파일은 백업 설정에 따라 백업 후 교체.
    """
    from src.api import nexon_api

    _check_assets_dir(config)

    if target_path:
        png_bytes = nexon_api.download_cdn_file(target_path)
    else:
        img = nexon_api.get_official_player_image(spid)
        png_bytes = None
        if img is not None:
            import io
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            png_bytes = buf.getvalue()
    if png_bytes is None:
        raise ValueError("공식 미페를 가져올 수 없습니다. 인터넷 연결을 확인해주세요.")

    dest_file = target_file(config, spid, target_path)
    backup_path, result_path = _write_game_file(spid, dest_file, png_bytes, config)

    return ChangeRecord(
        spid=spid,
        player_name=player_name,
        image_path="(공식 미페)",
        changed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        backup_path=backup_path,
        result_path=result_path,
        target_path=target_path,
    )


def restore_face(record: ChangeRecord, config: Config) -> bool:
    """
    백업 파일로 복원.
    백업이 없으면 교체된 파일만 삭제(게임 자체 리소스로 복구).
    """
    dest_file = target_file(config, record.spid, record.target_path)

    if dest_file.exists():
        _remove_readonly(dest_file)

    if record.backup_path and Path(record.backup_path).exists():
        shutil.copy2(record.backup_path, dest_file)
        _set_readonly(dest_file)
        return True
    else:
        # 백업 없으면 파일 삭제 → 게임이 CDN에서 재다운로드
        if dest_file.exists():
            dest_file.unlink()
        return False


def delete_face_record(record: ChangeRecord):
    """백업/결과 스냅샷 파일 삭제 (게임 파일 건드리지 않음). 이력 정리용."""
    for path_str in (record.backup_path, record.result_path):
        if path_str:
            p = Path(path_str)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass


def is_square_image(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            w, h = img.size
        return w == h
    except Exception:
        return False


def get_image_size(path: Path) -> Optional[tuple[int, int]]:
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return None
