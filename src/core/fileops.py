"""게임 리소스 파일 공통 처리 — 읽기전용 속성, 이미지 정규화, 백업 파일명."""

import ctypes
import io
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image

_FILE_ATTRIBUTE_READONLY = 0x1
_FILE_ATTRIBUTE_NORMAL = 0x80


def set_readonly(path: Path):
    """읽기전용 설정 — 게임 패치가 교체한 파일을 덮어쓰지 못하게 한다."""
    path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    try:
        ctypes.windll.kernel32.SetFileAttributesW(str(path), _FILE_ATTRIBUTE_READONLY)
    except (AttributeError, OSError):
        pass


def remove_readonly(path: Path):
    try:
        path.chmod(stat.S_IWRITE | stat.S_IREAD)
        ctypes.windll.kernel32.SetFileAttributesW(str(path), _FILE_ATTRIBUTE_NORMAL)
    except (AttributeError, OSError):
        pass


def write_game_file(path: Path, data: bytes):
    """읽기전용을 풀고 덮어쓴 뒤 다시 읽기전용으로 잠근다."""
    if path.exists():
        remove_readonly(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    set_readonly(path)


def copy_backup(src: Path, dest: Path):
    """백업 복사 — 내용만 복사해 게임 파일의 읽기전용 속성이 백업에 옮겨가지 않게 한다
    (속성까지 복사하면 이력 정리 때 백업을 지우지 못한다)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)


def load_square(src: Path) -> Image.Image:
    """이미지를 RGBA로 열고, 정방형이 아니면 중앙을 기준으로 잘라낸다."""
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    if w != h:
        side = min(w, h)
        left, top = (w - side) // 2, (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
    return img


def to_png_bytes(img: Image.Image, size: Optional[int] = None) -> bytes:
    if size is not None and img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def timestamp() -> str:
    """백업 파일명용 — 같은 초에 여러 번 교체해도 겹치지 않도록 마이크로초까지."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
