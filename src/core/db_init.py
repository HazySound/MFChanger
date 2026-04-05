"""
시작 시 DB 파일 존재 여부 확인 및 자동 생성 모듈
대상: spid.json / seasonid.json / managers_db.json
"""

from pathlib import Path
from typing import Callable

from src.api.nexon_api import (
    META_CACHE_PATH,
    SPID_CACHE_FILE,
    fetch_spid_meta,
    fetch_season_meta,
)
from src.core.manager_db import DB_PATH, build_db

# (key, 표시 레이블, 파일 경로) 순서 고정
STEPS = [
    ("spid",    "선수 DB (spid.json)",       SPID_CACHE_FILE),
    ("season",  "시즌 DB (seasonid.json)",    META_CACHE_PATH / "seasonid.json"),
    ("manager", "감독 DB (managers_db.json)", DB_PATH),
]


def check_missing() -> list[str]:
    """없는 DB 파일의 key 목록 반환."""
    return [key for key, _, path in STEPS if not path.exists()]


def build_missing(
    missing: list[str],
    step_cb: Callable[[str, str, float], None] | None = None,
) -> None:
    """
    missing에 있는 DB 파일만 순서대로 생성.
    step_cb(key, label, fraction) — 각 단계 시작 전 호출 (fraction: 0.0~1.0)
    완료 후 step_cb("done", "완료", 1.0) 호출.
    """
    total = len(missing)
    for i, key in enumerate(missing):
        _, label, _ = next(s for s in STEPS if s[0] == key)
        if step_cb:
            step_cb(key, label, i / total)

        if key == "spid":
            fetch_spid_meta(force=True)
        elif key == "season":
            fetch_season_meta(force=True)
        elif key == "manager":
            build_db()

    if step_cb:
        step_cb("done", "완료", 1.0)
