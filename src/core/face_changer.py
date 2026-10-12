"""미페 교체 핵심 로직"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import fileops
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
    return config.assets_dir / (target_path or f"playersAction/p{spid}.png")


def _require_assets_dir(config: Config):
    if not config.is_fc_path_valid():
        raise FileNotFoundError(
            f"FC온라인 미페 폴더를 찾을 수 없습니다.\n경로: {config.assets_dir}\n\n"
            "설정에서 FC온라인 설치 경로를 확인해주세요."
        )


def _write_with_backup(spid: int, dest_file: Path, png_bytes: bytes, config: Config):
    """기존 파일 백업 → 덮어쓰기 → 결과 스냅샷. (backup_path, result_path) 반환."""
    backup_dir = config.backup_path / f"p{spid}"
    stamp = fileops.timestamp()

    backup_path: Optional[str] = None
    if config.backup_enabled and dest_file.exists():
        backup_file = backup_dir / f"p{spid}_backup_{stamp}.png"
        fileops.copy_backup(dest_file, backup_file)
        backup_path = str(backup_file)

    fileops.write_game_file(dest_file, png_bytes)

    result_path: Optional[str] = None
    if config.backup_enabled:
        backup_dir.mkdir(parents=True, exist_ok=True)
        result_file = backup_dir / f"p{spid}_result_{stamp}.png"
        result_file.write_bytes(png_bytes)
        result_path = str(result_file)

    return backup_path, result_path


def replace_face(
    spid: int,
    player_name: str,
    src_image_path: Path,
    config: Config,
    target_path: str,
) -> ChangeRecord:
    """
    미페 교체. target_path는 게임이 실제 사용하는 파일의 상대 경로
    (datacenter.resolve_face_path 또는 face_catalog.list_faces 결과).
    """
    _require_assets_dir(config)
    png_bytes = fileops.to_png_bytes(fileops.load_square(src_image_path))
    dest_file = target_file(config, spid, target_path)
    backup_path, result_path = _write_with_backup(spid, dest_file, png_bytes, config)

    return ChangeRecord(
        spid=spid,
        player_name=player_name,
        image_path=str(src_image_path),
        changed_at=fileops.now_text(),
        backup_path=backup_path,
        result_path=result_path,
        target_path=target_path,
    )


def restore_to_official(
    spid: int,
    player_name: str,
    config: Config,
    target_path: str,
) -> ChangeRecord:
    """CDN의 같은 경로 파일(공식 미페)을 받아 로컬 파일을 덮어쓴다."""
    from src.api import nexon_api

    _require_assets_dir(config)
    png_bytes = nexon_api.download_cdn_file(target_path)
    if png_bytes is None:
        raise ValueError("공식 미페를 가져올 수 없습니다. 인터넷 연결을 확인해주세요.")

    dest_file = target_file(config, spid, target_path)
    backup_path, result_path = _write_with_backup(spid, dest_file, png_bytes, config)

    return ChangeRecord(
        spid=spid,
        player_name=player_name,
        image_path="(공식 미페)",
        changed_at=fileops.now_text(),
        backup_path=backup_path,
        result_path=result_path,
        target_path=target_path,
    )


def restore_face(record: ChangeRecord, config: Config) -> bool:
    """
    백업 파일로 복원.
    백업이 없으면 교체된 파일만 삭제 → 게임이 CDN에서 다시 받는다.
    """
    dest_file = target_file(config, record.spid, record.target_path)
    if record.backup_path and Path(record.backup_path).exists():
        fileops.write_game_file(dest_file, Path(record.backup_path).read_bytes())
        return True

    if dest_file.exists():
        fileops.remove_readonly(dest_file)
        dest_file.unlink()
    return False


def delete_face_record(record: ChangeRecord):
    """백업/결과 스냅샷 파일 삭제 (게임 파일은 건드리지 않음). 이력 정리용."""
    for path_str in (record.backup_path, record.result_path):
        if path_str:
            try:
                fileops.remove_readonly(Path(path_str))   # 이전 버전이 읽기전용으로 만든 백업 대비
                Path(path_str).unlink(missing_ok=True)
            except OSError:
                pass   # 사용 중인 파일 등 — 이력 정리는 계속 진행
