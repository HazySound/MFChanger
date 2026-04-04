"""크레스트 교체 핵심 로직"""

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image

from .config import Config
from .face_changer import _set_readonly, _remove_readonly


# 테마별 파일 접두사
THEME_PREFIX = {"dark": "d", "light": "l"}

# 사이즈별 픽셀 크기
SIZE_PX = {"large": 256, "medium": 128, "small": 64}


@dataclass
class CrestChangeRecord:
    crest_id: int
    image_path: str
    changed_at: str
    backup_paths: list[str] = field(default_factory=list)


def get_crest_file(crest_dir: Path, theme: str, size: str, crest_id: int) -> Path:
    """크레스트 파일 경로 반환."""
    prefix = THEME_PREFIX[theme]
    return crest_dir / theme / size / f"{prefix}{crest_id}.png"


def load_crest_image(crest_dir: Path, crest_id: int) -> Optional[Image.Image]:
    """dark/large 크레스트 이미지 로드 (미리보기용)."""
    path = get_crest_file(crest_dir, "dark", "large", crest_id)
    if not path.exists():
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def replace_crest(
    crest_id: int,
    src_image_path: Path,
    config: Config,
) -> CrestChangeRecord:
    """
    크레스트 교체 실행.

    1. 기존 파일 백업 (설정에 따라)
    2. src_image_path 로드 → 비정방형이면 중앙 크롭
    3. dark/light × large/medium/small 총 6개 경로에 맞는 크기로 리사이징 후 저장
    4. 각 파일 읽기전용 설정
    """
    crest_dir = config.crest_dir
    if not crest_dir.exists():
        raise FileNotFoundError(
            f"크레스트 폴더를 찾을 수 없습니다.\n경로: {crest_dir}\n\n"
            "설정에서 FC온라인 설치 경로를 확인해주세요."
        )

    # 소스 이미지 로드 + 정방형 크롭
    img = Image.open(src_image_path).convert("RGBA")
    w, h = img.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))

    backup_paths: list[str] = []

    for theme, prefix in THEME_PREFIX.items():
        for size_name, size_px in SIZE_PX.items():
            dest_file = get_crest_file(crest_dir, theme, size_name, crest_id)

            # 대상 폴더 없으면 건너뜀 (게임 설치에 해당 폴더가 없는 경우)
            if not dest_file.parent.exists():
                continue

            # 기존 파일 백업
            if config.backup_enabled and dest_file.exists():
                backup_dir = (
                    config.backup_path
                    / f"crest_{crest_id}"
                    / theme
                    / size_name
                )
                backup_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = backup_dir / f"{prefix}{crest_id}_backup_{timestamp}.png"
                _remove_readonly(dest_file)
                shutil.copy2(dest_file, backup_file)
                backup_paths.append(str(backup_file))

            # 읽기전용 해제
            if dest_file.exists():
                _remove_readonly(dest_file)

            # 리사이징 후 저장
            resized = img.resize((size_px, size_px), Image.LANCZOS)
            resized.save(dest_file, format="PNG")
            _set_readonly(dest_file)

    return CrestChangeRecord(
        crest_id=crest_id,
        image_path=str(src_image_path),
        changed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        backup_paths=backup_paths,
    )


def restore_crest(record: CrestChangeRecord, config: Config) -> bool:
    """
    백업 파일로 크레스트 복원.
    백업이 없으면 교체된 파일 삭제(게임 자체 리소스로 복구).
    """
    crest_dir = config.crest_dir
    any_restored = False

    for theme, prefix in THEME_PREFIX.items():
        for size_name in SIZE_PX:
            dest_file = get_crest_file(crest_dir, theme, size_name, record.crest_id)

            # theme/size 에 해당하는 백업 파일 찾기
            backup_file: Optional[Path] = None
            for bp in record.backup_paths:
                if (f"/{theme}/{size_name}/" in bp or f"\\{theme}\\{size_name}\\" in bp):
                    candidate = Path(bp)
                    if candidate.exists():
                        backup_file = candidate
                        break

            if dest_file.exists():
                _remove_readonly(dest_file)

            if backup_file:
                shutil.copy2(backup_file, dest_file)
                _set_readonly(dest_file)
                any_restored = True
            else:
                if dest_file.exists():
                    dest_file.unlink()

    return any_restored
