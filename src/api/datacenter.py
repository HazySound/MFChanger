"""FC온라인 데이터센터 기반 미페 경로 조회.

게임이 카드별로 기본 사용하는 미페 파일은 넥슨 서버가 결정한다.
(예: 카드 전용 playersAction/p{spid}.png가 CDN에 있어도
 게임은 선수 공통 players/p{pid}.png 나 playersAction/p{pid}_25.png 를 쓰는 경우가 많음)
CDN 파일 존재 여부로는 판별할 수 없으므로, 공식 데이터센터 선수검색 결과에
붙어 있는 이미지 경로를 정답으로 사용한다.
"""

import json
import re
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import requests

from src.api.nexon_api import cdn_exists, spid_to_pid
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

_cache_lock = threading.Lock()
_pid_locks: defaultdict[int, threading.Lock] = defaultdict(threading.Lock)   # _cache_lock 안에서 꺼낼 것
_session_pids: set[int] = set()     # 이번 실행에서 데이터센터로 확인한 pid
_paths: Optional[dict[int, str]] = None   # spid → 상대 경로 (디스크 캐시 + 이번 실행 결과)


@dataclass
class FacePath:
    relative: str            # assets 기준 상대 경로 (예: "players/p190871.png")
    shared_spids: list[int]  # 같은 파일을 쓰는 다른 카드 spid (자기 자신 제외)
    verified: bool           # 데이터센터로 확인된 경로인지 (False = 추정 경로)


def guess_path(spid: int) -> str:
    """데이터센터 조회도, 이전 캐시도 없을 때의 추정 — 카드 전용 미페가 있으면 그것, 없으면 대갈 미페."""
    card_file = f"playersAction/p{spid}.png"
    return card_file if cdn_exists(card_file) else f"players/p{spid_to_pid(spid)}.png"


def _all_paths() -> dict[int, str]:
    """_cache_lock 안에서 호출."""
    global _paths
    if _paths is None:
        try:
            raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            _paths = {int(k): v for k, v in raw.items()}
        except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError):
            _paths = {}
    return _paths


def _save_paths():
    """_cache_lock 안에서 호출. 캐시 저장 실패는 다음 실행에서 재조회하면 되므로 무시."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({str(k): v for k, v in _paths.items()}), encoding="utf-8")
        tmp.replace(CACHE_FILE)
    except OSError:
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


def card_paths(pid: int, player_name: str) -> dict[int, str]:
    """
    선수(pid)의 카드별 기본 미페 경로 {spid: 상대 경로}.
    실행당 pid마다 한 번만 데이터센터를 조회하고, 실패하면 이전 실행의 캐시를 쓴다.
    네트워크 호출이 있으므로 UI 스레드에서 호출하지 말 것.
    """
    with _cache_lock:
        pid_lock = _pid_locks[pid]
    with pid_lock:   # 같은 선수를 동시에 조회하지 않도록
        if pid not in _session_pids:
            try:
                found = _search(player_name)
            except requests.RequestException:
                found = None
            if found is not None:
                with _cache_lock:
                    _all_paths().update({s: p for s, p in found.items() if spid_to_pid(s) == pid})
                    _save_paths()
                _session_pids.add(pid)

    with _cache_lock:
        paths = {s: p for s, p in _all_paths().items() if spid_to_pid(s) == pid}
    return paths


def resolve_face_path(spid: int, player_name: str) -> FacePath:
    """게임이 해당 카드에 기본으로 쓰는 미페 파일. 확인 불가 시 guess_path (verified=False)."""
    paths = card_paths(spid_to_pid(spid), player_name)
    rel = paths.get(spid)
    if rel is None:
        return FacePath(guess_path(spid), [], False)
    shared = sorted(s for s, p in paths.items() if p == rel and s != spid)
    return FacePath(rel, shared, True)
