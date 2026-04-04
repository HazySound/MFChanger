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
) -> ChangeRecord:
    """
    미페 교체 실행.

    1. 기존 파일 백업 (설정에 따라)
    2. src_image_path → PNG 변환
    3. face_dir/p{spid}.png 로 복사
    4. 읽기전용 설정
    """
    face_dir = config.face_dir
    if not face_dir.exists():
        raise FileNotFoundError(
            f"FC온라인 미페 폴더를 찾을 수 없습니다.\n경로: {face_dir}\n\n"
            "설정에서 FC온라인 설치 경로를 확인해주세요."
        )

    dest_file = face_dir / f"p{spid}.png"
    backup_path: Optional[str] = None

    # 기존 파일 백업
    if config.backup_enabled and dest_file.exists():
        backup_dir = config.backup_path / f"p{spid}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"p{spid}_backup_{timestamp}.png"
        _remove_readonly(dest_file)
        shutil.copy2(dest_file, backup_file)
        backup_path = str(backup_file)

    # 기존 파일 읽기전용 해제
    if dest_file.exists():
        _remove_readonly(dest_file)

    # 이미지 변환 후 저장
    png_bytes = _convert_to_png(src_image_path)
    dest_file.write_bytes(png_bytes)

    # 읽기전용 설정
    _set_readonly(dest_file)

    # 적용 결과 스냅샷 저장 (백업 활성화 시)
    result_path: Optional[str] = None
    if config.backup_enabled:
        backup_dir = config.backup_path / f"p{spid}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = backup_dir / f"p{spid}_result_{timestamp}.png"
        result_file.write_bytes(png_bytes)
        result_path = str(result_file)

    return ChangeRecord(
        spid=spid,
        player_name=player_name,
        image_path=str(src_image_path),
        changed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        backup_path=backup_path,
        result_path=result_path,
    )


def restore_to_official(spid: int, player_name: str, config: Config) -> ChangeRecord:
    """
    공식 미페(CDN)를 다운로드해 로컬 파일로 덮어씀.
    기존 파일은 백업 설정에 따라 백업 후 교체.
    """
    import io
    from src.api import nexon_api

    face_dir = config.face_dir
    if not face_dir.exists():
        raise FileNotFoundError(
            f"FC온라인 미페 폴더를 찾을 수 없습니다.\n경로: {face_dir}\n\n"
            "설정에서 FC온라인 설치 경로를 확인해주세요."
        )

    img = nexon_api.get_official_player_image(spid)
    if img is None:
        raise ValueError("공식 미페를 가져올 수 없습니다. 인터넷 연결을 확인해주세요.")

    dest_file = face_dir / f"p{spid}.png"
    backup_path: Optional[str] = None

    if config.backup_enabled and dest_file.exists():
        backup_dir = config.backup_path / f"p{spid}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"p{spid}_backup_{timestamp}.png"
        _remove_readonly(dest_file)
        shutil.copy2(dest_file, backup_file)
        backup_path = str(backup_file)

    if dest_file.exists():
        _remove_readonly(dest_file)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    dest_file.write_bytes(png_bytes)
    _set_readonly(dest_file)

    # 적용 결과 스냅샷 저장 (백업 활성화 시)
    result_path: Optional[str] = None
    if config.backup_enabled:
        backup_dir = config.backup_path / f"p{spid}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = backup_dir / f"p{spid}_result_{timestamp}.png"
        result_file.write_bytes(png_bytes)
        result_path = str(result_file)

    return ChangeRecord(
        spid=spid,
        player_name=player_name,
        image_path="(공식 미페)",
        changed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        backup_path=backup_path,
        result_path=result_path,
    )


def restore_face(record: ChangeRecord, config: Config) -> bool:
    """
    백업 파일로 복원.
    백업이 없으면 교체된 파일만 삭제(게임 자체 리소스로 복구).
    """
    face_dir = config.face_dir
    dest_file = face_dir / f"p{record.spid}.png"

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
