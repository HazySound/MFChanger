"""변경 이력 관리 (JSON 저장)"""

import json
from pathlib import Path
from typing import Optional

from .face_changer import ChangeRecord

HISTORY_PATH = Path.cwd() / "history.json"


def load_history() -> list[ChangeRecord]:
    if not HISTORY_PATH.exists():
        return []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [ChangeRecord(**item) for item in raw]
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
        }
        for r in records
    ]
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_record(record: ChangeRecord):
    records = load_history()
    # 동일 spid 기존 항목 교체
    records = [r for r in records if r.spid != record.spid]
    records.insert(0, record)
    save_history(records)


def remove_record(spid: int):
    records = load_history()
    records = [r for r in records if r.spid != spid]
    save_history(records)


def find_record(spid: int) -> Optional[ChangeRecord]:
    for r in load_history():
        if r.spid == spid:
            return r
    return None
