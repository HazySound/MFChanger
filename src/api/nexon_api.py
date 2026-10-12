"""넥슨 메타데이터(선수/시즌) 프록시 · FC온라인 CDN 클라이언트"""

import json
import shutil
from pathlib import Path
from typing import Optional

import requests

from src.core import fileops
from src.core.config import CACHE_DIR

API_BASE = "https://nexon-api-proxy.cemigs1.workers.dev"  # CF Worker 프록시 (API 키 불필요)
CDN_BASE = "https://fco.dn.nexoncdn.co.kr/live/externalAssets/common"

SPID_CACHE_FILE = CACHE_DIR / "spid.json"
SEASON_CACHE_FILE = CACHE_DIR / "seasonid.json"

_session = requests.Session()
_session.headers.update({"User-Agent": "MFChanger/1.0"})


# ──────────────────────────────────────────
# spid 구조: 앞 3자리 = 시즌 ID, 뒤 6자리 = 선수 고유 ID(pid)
# ──────────────────────────────────────────

def season_id(spid: int) -> int:
    return spid // 1_000_000


def spid_to_pid(spid: int) -> int:
    return spid % 1_000_000


# ──────────────────────────────────────────
# 시즌 분류
# ──────────────────────────────────────────

# 대분류 → 매칭 키워드 (className 영문 기준)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "TOTY":  ["TOTY", "TEAM OF THE YEAR", "TOTT", "TEAM OF THE NOMINATED"],
    "TOTS":  ["TOTS", "TEAM OF THE SEASON"],
    "UCL":   ["UCL", "UEFA CHAMPIONS LEAGUE"],
    "PL":    ["PREMIUM LIVE"],
    "LIVE":  ["LIVE"],                  # 일반 LIVE (Premium Live 제외)
    "K리그": ["K LEAGUE", "KLEAGUE", "K-LEAGUE", "KFA", "TEAM K LEAGUE",
              "K LEAGUE BEST", "KB (", "KH"],
    "ICON":  ["ICON"],
}
CATEGORY_ORDER = ["TOTY", "TOTS", "UCL", "PL", "LIVE", "K리그", "ICON", "기타"]


def _classify_season(class_name: str) -> str:
    cn = class_name.upper()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if cat == "LIVE" and "PREMIUM LIVE" in cn:
            continue
        if any(kw in cn for kw in keywords):
            return cat
    return "기타"


def _short_name(class_name: str) -> str:
    """'EPL (English Premier League)' → 'EPL'"""
    return class_name.split("(")[0].strip()


def _extract_year(class_name: str) -> str:
    """'25 TOTY (25 Team Of The Year)' → '25'"""
    parts = _short_name(class_name).split()
    if parts and len(parts[0]) == 2 and parts[0].isdigit():
        return parts[0]
    return ""


def _enrich_seasons(raw: list[dict]) -> list[dict]:
    return [
        {
            "seasonId":  item["seasonId"],
            "className": item["className"],
            "seasonImg": item.get("seasonImg", ""),
            "category":  _classify_season(item["className"]),
            "year":      _extract_year(item["className"]),
            "shortName": _short_name(item["className"]),
        }
        for item in raw
    ]


# ──────────────────────────────────────────
# 메타데이터 (로컬 캐시 우선 — 갱신은 sync_meta로 수동)
# ──────────────────────────────────────────

def _download_meta(name: str) -> list:
    resp = _session.get(f"{API_BASE}/static/fconline/meta/{name}", timeout=15)
    resp.raise_for_status()
    return resp.json()


def _load_meta(cache_file: Path, force: bool) -> list:
    """캐시 파일 우선. 없거나 force면 받아서 저장. 받기 실패 시 기존 캐시로 폴백."""
    if not force and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))
    try:
        data = _download_meta(cache_file.name)
    except (requests.RequestException, ValueError):
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))
        raise
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def fetch_spid_meta(force: bool = False) -> list[dict]:
    """전체 선수 목록 [{id, name}]."""
    return _load_meta(SPID_CACHE_FILE, force)


def fetch_season_meta(force: bool = False) -> list[dict]:
    """시즌 목록 (category, year, shortName 포함)."""
    return _enrich_seasons(_load_meta(SEASON_CACHE_FILE, force))


def sync_meta(backup_dir: Path) -> dict:
    """
    선수/시즌/감독 메타데이터 강제 동기화.
    1. 기존 캐시 파일을 backup_dir/meta_backup 에 타임스탬프 백업
    2. 선수·시즌 최신 다운로드 (실패 시 예외 전파 — 캐시는 그대로)
    3. 감독 DB 재크롤링 (실패해도 1·2 결과는 유지)
    """
    from src.core.manager_db import DB_PATH as MANAGER_DB_PATH, ensure_db

    stamp = fileops.timestamp()
    meta_backup = backup_dir / "meta_backup"
    for cache_file in (SPID_CACHE_FILE, SEASON_CACHE_FILE, MANAGER_DB_PATH):
        if cache_file.exists():
            meta_backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cache_file, meta_backup / f"{cache_file.stem}_{stamp}.json")

    # 둘 다 받은 뒤에 저장 — 한쪽만 갱신된 상태로 남지 않게
    spid_list = _download_meta(SPID_CACHE_FILE.name)
    seasons_raw = _download_meta(SEASON_CACHE_FILE.name)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SPID_CACHE_FILE.write_text(json.dumps(spid_list, ensure_ascii=False), encoding="utf-8")
    SEASON_CACHE_FILE.write_text(json.dumps(seasons_raw, ensure_ascii=False), encoding="utf-8")

    managers_count, managers_error = None, None
    try:
        managers_count = len(ensure_db(force_rebuild=True))
    except Exception as e:   # 크롤링 실패 사유는 다양 — 메시지만 전달
        managers_error = str(e)

    return {
        "spid": len(spid_list),
        "seasons": len(seasons_raw),
        "managers": managers_count,
        "managers_error": managers_error,
    }


# ──────────────────────────────────────────
# CDN
# ──────────────────────────────────────────

def cdn_url(relative: str) -> str:
    return f"{CDN_BASE}/{relative}"


def download_cdn_file(relative: str) -> Optional[bytes]:
    """CDN의 상대 경로 파일 원본 bytes (예: 'players/p190871.png'). 없으면 None."""
    try:
        resp = _session.get(cdn_url(relative), timeout=15)
    except requests.RequestException:
        return None
    return resp.content if resp.status_code == 200 else None


def cdn_exists(relative: str) -> bool:
    try:
        return _session.head(cdn_url(relative), timeout=8).status_code == 200
    except requests.RequestException:
        return False
