"""감독 얼굴 교체 핵심 로직"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import fileops
from .config import Config

GENERIC = "generic.png"
GENERIC_BACKUP = "generic_backup.png"


@dataclass
class ManagerChangeRecord:
    manager_id: str
    manager_name: str
    team: str
    image_path: str
    changed_at: str


def file_name(manager_id: str) -> str:
    return f"heads_staff_{manager_id}.png"


def get_manager_file(config: Config, manager_id: str) -> Path:
    return config.manager_dir / file_name(manager_id)


def displayed_file(config: Config, manager_id: str) -> Path:
    """게임이 실제로 보여주는 파일 — 고유 파일이 없는 감독은 generic.png."""
    own = get_manager_file(config, manager_id)
    return own if own.exists() else config.manager_dir / GENERIC


def generic_original(config: Config) -> Path:
    """공용 얼굴의 원본 — 교체하기 전에 보관해 둔 generic_backup.png, 없으면 generic.png."""
    backup = config.manager_dir / GENERIC_BACKUP
    return backup if backup.exists() else config.manager_dir / GENERIC


def _require_manager_dir(config: Config):
    if not config.manager_dir.exists():
        raise FileNotFoundError(
            f"감독 이미지 폴더를 찾을 수 없습니다.\n경로: {config.manager_dir}\n\n"
            "설정에서 FC온라인 설치 경로를 확인해주세요."
        )


def replace_manager(
    manager_id: str,
    manager_name: str,
    team: str,
    src_image_path: Path,
    config: Config,
) -> ManagerChangeRecord:
    """감독 얼굴 교체.

    heads_staff_{id}.png 가 있으면 그 파일을, 없으면(generic 폴백 감독) generic.png 를 교체.
    generic.png 는 최초 1회 generic_backup.png 로 원본을 보관한다.
    """
    _require_manager_dir(config)
    dest = displayed_file(config, manager_id)
    if dest.name == GENERIC:
        backup = config.manager_dir / GENERIC_BACKUP
        if dest.exists() and not backup.exists():
            shutil.copy2(dest, backup)

    fileops.write_game_file(dest, fileops.to_png_bytes(fileops.load_square(src_image_path)))

    return ManagerChangeRecord(
        manager_id=manager_id,
        manager_name=manager_name,
        team=team,
        image_path=str(src_image_path),
        changed_at=fileops.now_text(),
    )


def restore_to_official(
    manager_id: str,
    manager_name: str,
    team: str,
    config: Config,
) -> ManagerChangeRecord:
    """공식 감독 얼굴로 복원.

    CDN에 있으면 heads_staff_{id}.png 를 덮어쓰고,
    없으면(generic 폴백 감독) generic_backup.png 로 generic.png 를 되돌린다.
    """
    from src.api import nexon_api

    _require_manager_dir(config)
    official = nexon_api.download_cdn_file(f"managers/{file_name(manager_id)}")

    if official is not None:
        fileops.write_game_file(get_manager_file(config, manager_id), official)
        image_path = "(공식 얼굴)"
    else:
        backup = config.manager_dir / GENERIC_BACKUP
        if get_manager_file(config, manager_id).exists() or not backup.exists():
            raise ValueError("공식 감독 이미지를 가져올 수 없습니다. 인터넷 연결을 확인해주세요.")
        fileops.write_game_file(config.manager_dir / GENERIC, backup.read_bytes())
        image_path = "(generic 원본으로 복원)"

    return ManagerChangeRecord(
        manager_id=manager_id,
        manager_name=manager_name,
        team=team,
        image_path=image_path,
        changed_at=fileops.now_text(),
    )
