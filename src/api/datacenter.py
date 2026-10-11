"""FC온라인 데이터센터 기반 미페 경로 조회.

게임이 카드별로 실제 사용하는 미페 파일은 넥슨 서버가 결정한다.
(예: 카드 전용 playersAction/p{spid}.png가 CDN에 있어도
 게임은 선수 공통 players/p{pid}.png 나 playersAction/p{pid}_25.png 를 쓰는 경우가 많음)
CDN 파일 존재 여부로는 판별할 수 없으므로, 공식 데이터센터 선수검색 결과에
붙어 있는 이미지 경로를 정답으로 사용한다.
"""

import json
import re
import threading
from dataclasses import dataclass
from typing import Optional

import requests

from src.core.config import CACHE_DIR

PLAYER_LIST_URL = "https://fconline.nexon.com/datacenter/PlayerList"
CACHE_FILE = CACHE_DIR / "face_paths.json"
NOT_FOUND_PATH = "players/not_found.png"
MAX_PAGES = 20

# 검색 폼 기본값 (데이터센터 form1 직렬화 값 중 필수 항목)
_BASE_FORM = {
    "n8PlayerGrade1Min": 0, "n8PlayerGrade1Max": 999900000, "n1Strong": 1,
    "n4OvrMin": 0, "n4OvrMax": 200, "n4SalaryMin": 4, "n4SalaryMax": 99,
    "n1Ability1Min": 40, "n1Ability1Max": 200, "n1Ability2Min": 40, "n1Ability2Max": 200,
    "n1Ability3Min": 40, "n1Ability3Max": 200, "n4BirthYearMin": 1900, "n4BirthYearMax": 2010,
    "n4HeightMin": 140, "n4HeightMax": 250, "n4WeightMin": 40, "n4WeightMax": 200,
    "n4AvgPointMin": 0, "n4AvgPointMax": 10, "strSearchStatus": "off",
}

# 선수 행: GetPlayerDetail(this,{spid},...) 뒤에 오는 첫 썸네일 이미지
_ROW_RE = re.compile(
    r"GetPlayerDetail\(this,(\d+),.*?<div class=\"thumb\"><img src=\"[^\"]*?"
    r"/externalAssets/common/([^\"?]+)",
    re.S,
)

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://fconline.nexon.com/datacenter/index",
})

_lock = threading.Lock()
_mem: dict[int, str] = {}          # spid → 상대 경로 (이번 세션에 조회한 값)
_disk: Optional[dict[str, str]] = None


@dataclass
class FacePath:
    relative: str           # assets 기준 상대 경로 (예: "players/p190871.png")
    shared_spids: list[int]  # 같은 파일을 쓰는 다른 카드 spid (자기 자신 제외)
    verified: bool           # 데이터센터로 확인된 경로인지 (False = 추정 경로)


def _pid(spid: int) -> int:
    s = str(spid)
    return int(s[-6:]) if len(s) > 6 else spid


def legacy_path(spid: int) -> str:
    """데이터센터 조회 불가 시 사용하는 기존 추정 경로."""
    return f"playersAction/p{spid}.png"


def _load_disk() -> dict[str, str]:
    global _disk
    if _disk is None:
        try:
            _disk = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _disk = {}
    return _disk


def _save_disk():
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_disk, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CACHE_FILE)
    except Exception:
        pass


def _search(name: str) -> dict[int, str]:
    """선수 이름으로 데이터센터 검색 → {spid: 이미지 상대 경로} (전체 페이지)."""
    result: dict[int, str] = {}
    for page in range(1, MAX_PAGES + 1):
        data = dict(_BASE_FORM, strPlayerName=name, n4PageNo=page)
        resp = _session.post(PLAYER_LIST_URL, data=data, timeout=10)
        resp.raise_for_status()
        rows = {int(spid): path for spid, path in _ROW_RE.findall(resp.text)}
        new = {k: v for k, v in rows.items() if k not in result}
        if not new:
            break
        result.update(new)
    return result


def resolve_face_path(spid: int, player_name: str) -> FacePath:
    """
    게임이 해당 카드에 실제로 쓰는 미페 파일 경로 반환.
    1. 데이터센터 검색 (같은 이름의 카드 전체를 한 번에 캐시)
    2. 실패 시 이전에 디스크에 캐시해 둔 값
    3. 그래도 없으면 legacy_path (verified=False)
    네트워크 호출이 있으므로 UI 스레드에서 호출하지 말 것.
    """
    pid = _pid(spid)

    with _lock:
        cached = spid in _mem

    if not cached:
        try:
            found = _search(player_name)
            # 같은 pid 카드만 사용 (동명이인 제외)
            same_pid = {s: p for s, p in found.items() if _pid(s) == pid}
            with _lock:
                _mem.update(same_pid)
                disk = _load_disk()
                disk.update({str(s): p for s, p in same_pid.items()})
                _save_disk()
        except Exception:
            pass

    with _lock:
        rel = _mem.get(spid)
        verified = rel is not None
        if rel is None:
            rel = _load_disk().get(str(spid))
            verified = rel is not None
        if rel is None:
            return FacePath(legacy_path(spid), [], False)

        # 공유 카드 계산 — 같은 pid의 알려진 카드 중 같은 파일을 쓰는 카드
        known = dict(_load_disk())
        known.update({str(k): v for k, v in _mem.items()})
        shared = sorted(
            int(s) for s, p in known.items()
            if p == rel and int(s) != spid and _pid(int(s)) == pid
        )
    return FacePath(rel, shared, verified)


def invalidate(spid: int):
    """세션 캐시에서 제거 → 다음 조회 시 데이터센터 재검색."""
    with _lock:
        _mem.pop(spid, None)
