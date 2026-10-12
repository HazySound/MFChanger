"""화면(JS)에서 호출하는 API — window.pywebview.api.<영역>.<메서드>(...)

pywebview는 호출마다 별도 스레드에서 실행하므로 네트워크·파일 작업을 그대로 수행해도 된다.
진행률은 window.state 에 값을 넣어 화면으로 보낸다 (Context.progress).
메서드가 예외를 올리면 화면의 Promise가 그 메시지로 거부된다.
"""

import base64
import shutil
import subprocess
import threading
import uuid
import webbrowser
from pathlib import Path
from typing import Optional

import webview
from PIL import Image, UnidentifiedImageError

from src.api import datacenter, nexon_api
from src.app.server import UPLOAD_DIR, AssetServer
from src.core import (
    crest_changer,
    db_init,
    face_catalog,
    face_changer,
    history,
    manager_changer,
    manager_db,
    updater,
)
from src.core.config import Config
from version import __version__

IMAGE_TYPES = ("이미지 파일 (*.png;*.jpg;*.jpeg;*.bmp;*.webp)",)


class Context:
    """영역별 API가 공유하는 의존성."""

    def __init__(self, config: Config, server: AssetServer):
        self.config = config
        self.server = server
        self.window: Optional[webview.Window] = None

    def progress(self, task: str, label: str, fraction: float):
        """화면의 진행률 표시 갱신 — JS에서 pywebview.state 'progress' 변경 이벤트로 받는다."""
        if self.window is not None:
            self.window.state.progress = {"task": task, "label": label, "fraction": fraction}

    def game_file_url(self, path: Path) -> Optional[str]:
        return self.server.game_url(path.relative_to(self.config.assets_dir).as_posix())

    def stage_image(self, name: str, write) -> dict:
        """교체에 쓸 이미지를 업로드 폴더(<고유ID>/<원래 파일명>)에 두고 정보를 반환.
        원래 파일명을 유지해야 이력에 사용자가 고른 파일명이 그대로 남는다.
        write(path)가 파일을 만든다. 이미지가 아니면 지우고 ValueError."""
        folder = UPLOAD_DIR / uuid.uuid4().hex
        folder.mkdir(parents=True)
        path = folder / Path(name).name
        write(path)
        try:
            with Image.open(path) as img:
                width, height = img.size
        except (UnidentifiedImageError, OSError):
            shutil.rmtree(folder, ignore_errors=True)
            raise ValueError("이미지 파일을 열 수 없습니다. PNG, JPG, BMP, WEBP 파일인지 확인해주세요.")
        return {
            "path": str(path),
            "name": path.name,
            "width": width,
            "height": height,
            "url": self.server.file_url(str(path)),
        }


class AppApi:
    def __init__(self, ctx: Context):
        self._ctx = ctx

    def bootstrap(self) -> dict:
        return {
            "version": __version__,
            "settings": self._ctx.config.as_dict(),
            "pathValid": self._ctx.config.is_fc_path_valid(),
            "missingDb": db_init.check_missing(),
            # 8만 명 넘는 선수 목록은 API 응답 대신 HTTP로 받는다 (브리지 직렬화 부담)
            "playersUrl": f"{self._ctx.server.url}/data/players.json",
        }

    def seasons(self) -> list[dict]:
        return nexon_api.fetch_season_meta()

    def build_db(self, missing: list[str]):
        db_init.build_missing(missing, lambda label, frac: self._ctx.progress("db", label, frac))

    def check_update(self) -> Optional[dict]:
        result = updater.check_for_update()
        if result:
            result["installable"] = bool(result["download_url"]) and updater.IS_FROZEN
        return result

    def install_update(self, download_url: str):
        """다운로드 → exe 교체 → 새 버전 실행 → 이 창을 닫아 종료."""
        new_exe = updater.download_update(
            download_url, lambda frac: self._ctx.progress("update", "다운로드 중", frac)
        )
        self._ctx.progress("update", "설치 중", 1.0)
        updater.apply_update(new_exe)
        # 화면이 응답을 받을 시간을 준 뒤 종료
        threading.Timer(0.5, self._ctx.window.destroy).start()

    def open_url(self, url: str):
        if url.startswith(("https://", "http://")):
            webbrowser.open(url)

    def reveal(self, path: str):
        """탐색기에서 파일을 선택한 상태로 열기. 파일이 없으면 상위 폴더를 연다."""
        target = Path(path)
        if target.is_file():
            subprocess.Popen(f'explorer /select,"{target}"')
            return
        while not target.exists() and target != target.parent:
            target = target.parent
        if target.exists():
            subprocess.Popen(f'explorer "{target}"')

    def reveal_game_file(self, relative: str):
        self.reveal(str(self._ctx.config.assets_dir / relative))

    def pick_folder(self, initial: str = "") -> Optional[str]:
        result = self._ctx.window.create_file_dialog(webview.FileDialog.FOLDER, directory=initial)
        return result[0] if result else None

    def pick_image(self) -> Optional[dict]:
        result = self._ctx.window.create_file_dialog(webview.FileDialog.OPEN, file_types=IMAGE_TYPES)
        if not result:
            return None
        source = Path(result[0])
        return self._ctx.stage_image(source.name, lambda dest: shutil.copyfile(source, dest))

    def upload_image(self, name: str, data_base64: str) -> dict:
        """드롭·붙여넣기한 이미지 (브라우저에서 읽은 파일 내용)."""
        data = base64.b64decode(data_base64)
        return self._ctx.stage_image(name, lambda dest: dest.write_bytes(data))


class FaceApi:
    def __init__(self, ctx: Context):
        self._ctx = ctx

    @staticmethod
    def _changed_at(relative: str) -> Optional[str]:
        """그 게임 파일을 마지막으로 바꾼 시각 (어느 카드에서 바꿨든)."""
        record = history.find_record_by_target(relative)
        return record.changed_at if record else None

    def resolve(self, spid: int, name: str) -> dict:
        fp = datacenter.resolve_face_path(spid, name)
        return {
            "relative": fp.relative,
            "sharedSpids": fp.shared_spids,
            "verified": fp.verified,
            "currentUrl": self._ctx.server.game_url(fp.relative),
            "officialUrl": nexon_api.cdn_url(fp.relative),
            "changedAt": self._changed_at(fp.relative),
        }

    def thumbnails(self, pid: int, name: str, spids: list[int]) -> dict[int, Optional[str]]:
        """검색 목록 썸네일 — 카드별 기본 미페 (게임 파일, 없으면 CDN).
        데이터센터도 이전 캐시도 없으면(오프라인 첫 조회 등) 게임 폴더의 카드 미페 → 대갈 미페."""
        server = self._ctx.server
        paths = datacenter.card_paths(pid, name)
        return {
            spid: server.game_url(paths[spid], fallback_cdn=True) if spid in paths
            else server.game_url(f"playersAction/p{spid}.png") or server.game_url(f"players/p{pid}.png")
            for spid in spids
        }

    def catalog(self, pid: int, name: str, spids: list[int]) -> list[dict]:
        faces = face_catalog.list_faces(pid, name, spids, self._ctx.config.assets_dir)
        return [
            {
                "relative": face.relative,
                "kind": face.kind,
                "spid": face.spid,
                "year": face.year,
                "defaultFor": face.default_for,
                "cached": face.cached,
                "currentUrl": self._ctx.server.game_url(face.relative, fallback_cdn=True),
                "officialUrl": nexon_api.cdn_url(face.relative),
                "changedAt": self._changed_at(face.relative),
            }
            for face in faces
        ]

    def replace(self, spid: int, name: str, image_path: str, relative: str) -> dict:
        record = face_changer.replace_face(spid, name, Path(image_path), self._ctx.config, relative)
        history.add_record(record)
        return {"changedAt": record.changed_at, "currentUrl": self._ctx.server.game_url(relative)}

    def restore_official(self, spid: int, name: str, relative: str) -> dict:
        record = face_changer.restore_to_official(spid, name, self._ctx.config, relative)
        history.add_record(record)
        return {"changedAt": record.changed_at, "currentUrl": self._ctx.server.game_url(relative)}


class CrestApi:
    def __init__(self, ctx: Context):
        self._ctx = ctx

    def parse_id(self, text: str) -> Optional[int]:
        return crest_changer.parse_crest_id(text)

    def info(self, crest_id: int) -> dict:
        if not self._ctx.config.crest_dir.exists():
            raise FileNotFoundError("크레스트 폴더를 찾을 수 없습니다. 설정에서 FC온라인 설치 경로를 확인해주세요.")
        path = crest_changer.preview_file(self._ctx.config, crest_id)
        record = history.find_crest_record(crest_id)
        return {
            "id": crest_id,
            "path": str(path),
            "currentUrl": self._ctx.game_file_url(path),
            "changedAt": record.changed_at if record else None,
        }

    def replace(self, crest_id: int, image_path: str) -> dict:
        record = crest_changer.replace_crest(crest_id, Path(image_path), self._ctx.config)
        history.add_crest_record(record)
        return self.info(crest_id)


class ManagerApi:
    def __init__(self, ctx: Context):
        self._ctx = ctx

    def entries(self) -> list[dict]:
        return [{"id": mid, **info} for mid, info in manager_db.ensure_db().items()]

    def info(self, manager_id: str) -> dict:
        config = self._ctx.config
        shown = manager_changer.displayed_file(config, manager_id)
        record = history.find_manager_record(manager_id)
        official = f"managers/{manager_changer.file_name(manager_id)}"
        return {
            "fileName": manager_changer.file_name(manager_id),
            "path": str(manager_changer.get_manager_file(config, manager_id)),
            "currentUrl": self._ctx.game_file_url(shown),
            # 공식 이미지가 없는 감독은 게임도 공용 얼굴을 쓰므로 그 원본을 보여준다
            "officialUrl": nexon_api.cdn_url(official) if nexon_api.cdn_exists(official)
            else self._ctx.game_file_url(manager_changer.generic_original(config)),
            "usesGeneric": shown.name == manager_changer.GENERIC,
            "changedAt": record.changed_at if record else None,
        }

    def thumbnails(self, manager_ids: list[str]) -> dict[str, Optional[str]]:
        return {
            mid: self._ctx.game_file_url(manager_changer.displayed_file(self._ctx.config, mid))
            for mid in manager_ids
        }

    def replace(self, manager_id: str, name: str, team: str, image_path: str) -> dict:
        record = manager_changer.replace_manager(manager_id, name, team, Path(image_path), self._ctx.config)
        history.add_manager_record(record)
        return self.info(manager_id)

    def restore_official(self, manager_id: str, name: str, team: str) -> dict:
        record = manager_changer.restore_to_official(manager_id, name, team, self._ctx.config)
        history.add_manager_record(record)
        return self.info(manager_id)


class HistoryApi:
    def __init__(self, ctx: Context):
        self._ctx = ctx

    def _face_groups(self) -> list[dict]:
        server, config = self._ctx.server, self._ctx.config
        groups: dict[int, list[face_changer.ChangeRecord]] = {}
        for record in history.load_history():
            groups.setdefault(record.spid, []).append(record)

        result = []
        for spid, records in groups.items():
            entries = []
            for pos, record in enumerate(records):
                is_latest = pos == len(records) - 1
                # 교체 후 이미지: 결과 스냅샷 → (최신이면) 현재 게임 파일 → 다음 기록의 백업
                if record.result_path and Path(record.result_path).is_file():
                    after = server.file_url(record.result_path)
                elif is_latest:
                    after = self._ctx.game_file_url(face_changer.target_file(config, spid, record.target_path))
                else:
                    after = server.file_url(records[pos + 1].backup_path)
                entries.append({
                    "position": pos,
                    "source": Path(record.image_path).name if record.image_path else "",
                    "changedAt": record.changed_at,
                    "beforeUrl": server.file_url(record.backup_path),
                    "afterUrl": after,
                    "hasBackup": bool(record.backup_path) and Path(record.backup_path).is_file(),
                })
            result.append({
                "spid": spid,
                "playerName": records[-1].player_name,
                "backupDir": str(config.backup_path / f"p{spid}"),
                "entries": entries[::-1],   # 최신순
            })
        return result

    def _crest_rows(self) -> list[dict]:
        server, config = self._ctx.server, self._ctx.config
        rows = []
        for record in history.load_crest_history():
            preview = next(
                (bp for bp in record.backup_paths
                 if Path(bp).parent.parts[-2:] == (crest_changer.PREVIEW_THEME, crest_changer.PREVIEW_SIZE)),
                None,
            )
            current = crest_changer.preview_file(config, record.crest_id)
            rows.append({
                "crestId": record.crest_id,
                "source": Path(record.image_path).name if record.image_path else "",
                "changedAt": record.changed_at,
                "beforeUrl": server.file_url(preview),
                "afterUrl": self._ctx.game_file_url(current),
                "hasBackup": any(Path(bp).is_file() for bp in record.backup_paths),
                "backupDir": str(config.backup_path / f"crest_{record.crest_id}"),
            })
        return rows

    def _manager_rows(self) -> list[dict]:
        return [
            {
                "managerId": record.manager_id,
                "name": record.manager_name,
                "team": record.team,
                "source": (record.image_path if record.image_path.startswith("(")
                           else Path(record.image_path).name),
                "changedAt": record.changed_at,
                "currentUrl": self._ctx.game_file_url(
                    manager_changer.displayed_file(self._ctx.config, record.manager_id)
                ),
            }
            for record in history.load_manager_history()
        ]

    def entries(self) -> dict:
        return {"faces": self._face_groups(), "crests": self._crest_rows(), "managers": self._manager_rows()}

    def restore_face(self, spid: int):
        """가장 최근 기록을 되돌린다 (백업이 없으면 교체 파일 삭제)."""
        record = history.find_record(spid)
        if record is None:
            raise ValueError("되돌릴 기록이 없습니다.")
        face_changer.restore_face(record, self._ctx.config)
        history.remove_record(spid)

    def delete_face_records(self, spid: int, positions: Optional[list[int]] = None):
        """이력과 백업 파일 삭제 (게임 파일은 그대로). positions가 없으면 해당 선수 전체."""
        records = history.get_records_for_spid(spid)
        doomed = set(range(len(records))) if positions is None else set(positions)
        for pos in doomed:
            face_changer.delete_face_record(records[pos])
        history.remove_records(spid, doomed)

    def restore_crest(self, crest_id: int):
        record = history.find_crest_record(crest_id)
        if record is None:
            raise ValueError("되돌릴 기록이 없습니다.")
        crest_changer.restore_crest(record, self._ctx.config)
        history.remove_crest_record(crest_id)

    def restore_manager(self, manager_id: str):
        record = history.find_manager_record(manager_id)
        if record is None:
            raise ValueError("되돌릴 기록이 없습니다.")
        manager_changer.restore_to_official(record.manager_id, record.manager_name, record.team, self._ctx.config)
        history.remove_manager_record(manager_id)

    def delete_manager_record(self, manager_id: str):
        history.remove_manager_record(manager_id)


class SettingsApi:
    def __init__(self, ctx: Context):
        self._ctx = ctx

    def save(self, values: dict) -> dict:
        self._ctx.config.update(**values)
        return {"settings": self._ctx.config.as_dict(), "pathValid": self._ctx.config.is_fc_path_valid()}

    def sync_meta(self) -> dict:
        return nexon_api.sync_meta(self._ctx.config.backup_path)


class Api:
    def __init__(self, ctx: Context):
        self.app = AppApi(ctx)
        self.face = FaceApi(ctx)
        self.crest = CrestApi(ctx)
        self.manager = ManagerApi(ctx)
        self.history = HistoryApi(ctx)
        self.settings = SettingsApi(ctx)
