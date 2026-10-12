"""시작 시 필요한 DB 파일(spid.json / seasonid.json / managers_db.json) 확인 및 생성"""

from typing import Callable

from src.api.nexon_api import SEASON_CACHE_FILE, SPID_CACHE_FILE, fetch_season_meta, fetch_spid_meta
from src.core.manager_db import DB_PATH, build_db

# (key, 표시 이름, 파일 경로, 생성 함수) — 순서대로 생성
STEPS = [
    ("spid",    "선수 DB",  SPID_CACHE_FILE,   lambda: fetch_spid_meta(force=True)),
    ("season",  "시즌 DB",  SEASON_CACHE_FILE, lambda: fetch_season_meta(force=True)),
    ("manager", "감독 DB",  DB_PATH,           build_db),
]


def check_missing() -> list[str]:
    """없는 DB 파일의 key 목록."""
    return [key for key, _, path, _ in STEPS if not path.exists()]


def build_missing(missing: list[str], on_step: Callable[[str, float], None]) -> None:
    """missing에 있는 DB만 순서대로 생성. 각 단계 시작 전 on_step(표시 이름, 진행률).
    실패하면 예외를 그대로 올린다 — 호출부가 사용자에게 알리고 진행 화면을 닫아야 한다."""
    targets = [step for step in STEPS if step[0] in missing]
    for i, (_, label, _, build) in enumerate(targets):
        on_step(label, i / len(targets))
        build()
    on_step("완료", 1.0)
