"""크레스트 교체 핵심 로직"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import fileops
from .config import Config

# 테마별 파일 접두사
THEME_PREFIX = {"dark": "d", "light": "l"}

# 사이즈별 픽셀 크기
SIZE_PX = {"large": 256, "medium": 128, "small": 64}

PREVIEW_THEME, PREVIEW_SIZE = "dark", "large"

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


@dataclass
class CrestChangeRecord:
    crest_id: int
    image_path: str
    changed_at: str
    backup_paths: list[str] = field(default_factory=list)


def get_crest_file(crest_dir: Path, theme: str, size: str, crest_id: int) -> Path:
    return crest_dir / theme / size / f"{THEME_PREFIX[theme]}{crest_id}.png"


def preview_file(config: Config, crest_id: int) -> Path:
    """미리보기에 쓰는 대표 파일 (dark/large)."""
    return get_crest_file(config.crest_dir, PREVIEW_THEME, PREVIEW_SIZE, crest_id)


def parse_crest_id(text: str) -> Optional[int]:
    """'1234', 'd1234', 'l1234', '1234.png', 'l1234.jpg' 형식에서 크레스트 ID 추출."""
    s = text.strip()
    if Path(s).suffix.lower() in IMAGE_SUFFIXES:
        s = Path(s).stem
    if len(s) > 1 and s[0].lower() in THEME_PREFIX.values():
        s = s[1:]
    return int(s) if s.isdigit() else None


def _variants(crest_dir: Path, crest_id: int):
    """(theme, size_name, size_px, 파일 경로) — 6개 조합."""
    for theme in THEME_PREFIX:
        for size_name, size_px in SIZE_PX.items():
            yield theme, size_name, size_px, get_crest_file(crest_dir, theme, size_name, crest_id)


def replace_crest(crest_id: int, src_image_path: Path, config: Config) -> CrestChangeRecord:
    """dark/light × large/medium/small 6개 파일을 각 크기로 리사이즈해 교체."""
    crest_dir = config.crest_dir
    if not crest_dir.exists():
        raise FileNotFoundError(
            f"크레스트 폴더를 찾을 수 없습니다.\n경로: {crest_dir}\n\n"
            "설정에서 FC온라인 설치 경로를 확인해주세요."
        )

    img = fileops.load_square(src_image_path)
    stamp = fileops.timestamp()
    backup_paths: list[str] = []

    for theme, size_name, size_px, dest_file in _variants(crest_dir, crest_id):
        # 게임 설치에 해당 폴더가 없으면 건너뜀
        if not dest_file.parent.exists():
            continue

        if config.backup_enabled and dest_file.exists():
            backup_dir = config.backup_path / f"crest_{crest_id}" / theme / size_name
            backup_file = backup_dir / f"{dest_file.stem}_backup_{stamp}.png"
            fileops.copy_backup(dest_file, backup_file)
            backup_paths.append(str(backup_file))

        fileops.write_game_file(dest_file, fileops.to_png_bytes(img, size_px))

    return CrestChangeRecord(
        crest_id=crest_id,
        image_path=str(src_image_path),
        changed_at=fileops.now_text(),
        backup_paths=backup_paths,
    )


def _find_backup(record: CrestChangeRecord, theme: str, size_name: str) -> Optional[Path]:
    for bp in record.backup_paths:
        path = Path(bp)
        if path.parent.parts[-2:] == (theme, size_name) and path.exists():
            return path
    return None


def restore_crest(record: CrestChangeRecord, config: Config) -> bool:
    """백업으로 복원. 백업이 없는 파일은 삭제해 게임이 다시 받게 한다."""
    any_restored = False
    for theme, size_name, _, dest_file in _variants(config.crest_dir, record.crest_id):
        backup_file = _find_backup(record, theme, size_name)
        if backup_file:
            fileops.write_game_file(dest_file, backup_file.read_bytes())
            any_restored = True
        elif dest_file.exists():
            fileops.remove_readonly(dest_file)
            dest_file.unlink()
    return any_restored
