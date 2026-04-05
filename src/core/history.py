"""변경 이력 관리 (JSON 저장)"""

import json
from pathlib import Path
from typing import Optional

from .face_changer import ChangeRecord
from .crest_changer import CrestChangeRecord
from .manager_changer import ManagerChangeRecord

HISTORY_PATH = Path.cwd() / "history.json"
CREST_HISTORY_PATH = Path.cwd() / "crest_history.json"
MANAGER_HISTORY_PATH = Path.cwd() / "manager_history.json"


def load_history() -> list[ChangeRecord]:
    if not HISTORY_PATH.exists():
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        records = []
        for item in raw:
            # 구버전 호환: result_path 없으면 None
            item.setdefault("result_path", None)
            records.append(ChangeRecord(**item))
        return records
    except Exception:
        return []


def save_history(records: list[ChangeRecord]):
    data = [
        {
            "spid": r.spid,
            "player_name": r.player_name,
            "image_path": r.image_path,
            "changed_at": r.changed_at,
            "backup_path": r.backup_path,
            "result_path": r.result_path,
        }
        for r in records
    ]
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_record(record: ChangeRecord):
    """기록 추가 — 같은 SPID라도 교체하지 않고 스택에 쌓음."""
    records = load_history()
    records.append(record)
    save_history(records)


def remove_record(spid: int):
    """가장 최근 기록 하나만 제거 (undo 1단계)."""
    records = load_history()
    # 마지막(가장 최근) 항목 제거
    for i in range(len(records) - 1, -1, -1):
        if records[i].spid == spid:
            records.pop(i)
            break
    save_history(records)


def remove_all_face_records(spid: int):
    """특정 SPID 기록 전체 제거."""
    records = load_history()
    records = [r for r in records if r.spid != spid]
    save_history(records)


def find_record(spid: int) -> Optional[ChangeRecord]:
    """가장 최근 기록 반환."""
    result = None
    for r in load_history():
        if r.spid == spid:
            result = r
    return result


def get_records_for_spid(spid: int) -> list[ChangeRecord]:
    """특정 SPID 기록 전체 반환 (오래된 순)."""
    return [r for r in load_history() if r.spid == spid]


# ──────────────────────────────────────────
# 크레스트 이력
# ──────────────────────────────────────────

def load_crest_history() -> list[CrestChangeRecord]:
    if not CREST_HISTORY_PATH.exists():
        return []
    try:
        with open(CREST_HISTORY_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [CrestChangeRecord(**item) for item in raw]
    except Exception:
        return []


def save_crest_history(records: list[CrestChangeRecord]):
    data = [
        {
            "crest_id": r.crest_id,
            "image_path": r.image_path,
            "changed_at": r.changed_at,
            "backup_paths": r.backup_paths,
        }
        for r in records
    ]
    with open(CREST_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_crest_record(record: CrestChangeRecord):
    records = load_crest_history()
    records = [r for r in records if r.crest_id != record.crest_id]
    records.insert(0, record)
    save_crest_history(records)


def remove_crest_record(crest_id: int):
    records = load_crest_history()
    records = [r for r in records if r.crest_id != crest_id]
    save_crest_history(records)


def find_crest_record(crest_id: int) -> Optional[CrestChangeRecord]:
    for r in load_crest_history():
        if r.crest_id == crest_id:
            return r
    return None


# ──────────────────────────────────────────
# 감독 이력
# ──────────────────────────────────────────

def load_manager_history() -> list[ManagerChangeRecord]:
    if not MANAGER_HISTORY_PATH.exists():
        return []
    try:
        with open(MANAGER_HISTORY_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [ManagerChangeRecord(**item) for item in raw]
    except Exception:
        return []


def save_manager_history(records: list[ManagerChangeRecord]):
    data = [
        {
            "manager_id": r.manager_id,
            "manager_name": r.manager_name,
            "team": r.team,
            "image_path": r.image_path,
            "changed_at": r.changed_at,
        }
        for r in records
    ]
    with open(MANAGER_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_manager_record(record: ManagerChangeRecord):
    records = load_manager_history()
    records = [r for r in records if r.manager_id != record.manager_id]
    records.insert(0, record)
    save_manager_history(records)


def find_manager_record(manager_id: str) -> Optional[ManagerChangeRecord]:
    for r in load_manager_history():
        if r.manager_id == manager_id:
            return r
    return None


def remove_manager_record(manager_id: str):
    records = load_manager_history()
    records = [r for r in records if r.manager_id != manager_id]
    save_manager_history(records)
