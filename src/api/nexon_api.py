"""Nexon Open API / FC Online CDN 클라이언트"""

import json
import threading
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

API_BASE = "https://open.api.nexon.com"   # 메타데이터 (API 키 필요)
CDN_BASE = "https://fco.dn.nexoncdn.co.kr"  # 이미지 (공개 CDN)
META_CACHE_PATH = Path.cwd() / ".cache"
SPID_CACHE_FILE = META_CACHE_PATH / "spid.json"
CACHE_TTL_DAYS = 30

# API 키가 필요한 요청용
_session = requests.Session()
_session.headers.update({"User-Agent": "MFChanger/1.0"})

# 이미지 CDN 전용 세션 (API 키 불필요)
_cdn_session = requests.Session()
_cdn_session.headers.update({"User-Agent": "MFChanger/1.0"})

# 이미지 메모리 캐시 (spid -> PIL.Image)
_image_cache: dict[int, Image.Image] = {}
_image_cache_lock = threading.Lock()
IMAGE_CACHE_MAX = 100


def _set_api_key(api_key: str):
    if api_key:
        _session.headers.update({"x-nxopen-api-key": api_key})


# ──────────────────────────────────────────
# 메타데이터
# ──────────────────────────────────────────

def _is_cache_fresh() -> bool:
    if not SPID_CACHE_FILE.exists():
        return False
    age_days = (time.time() - SPID_CACHE_FILE.stat().st_mtime) / 86400
    return age_days < CACHE_TTL_DAYS


# ──────────────────────────────────────────
# 시즌 분류 정의
# ──────────────────────────────────────────

# 대분류 → 매칭 키워드 (className 영문 기준)
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "TOTY":  ["TOTY", "TEAM OF THE YEAR", "TOTT", "TEAM OF THE NOMINATED"],
    "TOTS":  ["TOTS", "TEAM OF THE SEASON"],
    "UCL":   ["UCL", "UEFA CHAMPIONS LEAGUE"],
    "PL":    ["PREMIUM LIVE"],          # Premium Live (PL 표기 시즌)
    "LIVE":  ["LIVE"],                  # 일반 LIVE (Premium Live 제외)
    "K리그": ["K LEAGUE", "KLEAGUE", "K-LEAGUE", "KFA", "TEAM K LEAGUE",
              "K LEAGUE BEST", "KB (", "KH"],
    "ICON":  ["ICON"],
}
CATEGORY_ORDER = ["TOTY", "TOTS", "UCL", "PL", "LIVE", "K리그", "ICON", "기타"]


def _classify_season(class_name: str) -> str:
    """className → 대분류 반환."""
    cn = class_name.upper()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in cn:
                # LIVE 카테고리는 Premium Live 제외
                if cat == "LIVE" and "PREMIUM LIVE" in cn:
                    continue
                return cat
    return "기타"


def _extract_year(class_name: str) -> str:
    """'25 TOTY (25 Team Of The Year)' → '25'"""
    short = class_name.split("(")[0].strip()
    parts = short.split()
    if parts and len(parts[0]) == 2 and parts[0].isdigit():
        return parts[0]
    return ""


def fetch_season_meta(force: bool = False) -> list[dict]:
    """시즌 전체 목록 반환 (id, className, seasonImg, category, year 포함).
    갱신 실패 시 구 캐시로 폴백 — 사용은 계속 가능."""
    cache_file = META_CACHE_PATH / "seasonid.json"

    if not force and cache_file.exists():
        age_days = (time.time() - cache_file.stat().st_mtime) / 86400
        if age_days < CACHE_TTL_DAYS:
            with open(cache_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return _enrich_seasons(raw)

    try:
        url = f"{API_BASE}/static/fconline/meta/seasonid.json"
        resp = _session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        META_CACHE_PATH.mkdir(parents=True, exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        return _enrich_seasons(data)
    except Exception:
        # 갱신 실패 → 구 캐시 폴백
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return _enrich_seasons(json.load(f))
        raise  # 캐시 자체가 없으면 예외 전파


def _enrich_seasons(raw: list[dict]) -> list[dict]:
    """각 시즌에 category, year, short_name 필드 추가."""
    result = []
    for item in raw:
        cn = item["className"]
        result.append({
            "seasonId":  item["seasonId"],
            "className": cn,
            "seasonImg": item.get("seasonImg", ""),
            "category":  _classify_season(cn),
            "year":      _extract_year(cn),
            "shortName": get_season_short_name(cn),
        })
    return result


def build_season_map(seasons: list[dict]) -> dict[int, dict]:
    """seasonId → 시즌 정보 딕셔너리."""
    return {s["seasonId"]: s for s in seasons}


def get_season_id(spid: int) -> int:
    """spid에서 시즌 ID 추출 (앞 3자리)."""
    return int(str(spid)[:-6]) if len(str(spid)) > 6 else 0


def get_season_short_name(class_name: str) -> str:
    """'EPL (English Premier League)' → 'EPL' 형태로 단축."""
    if "(" in class_name:
        return class_name[:class_name.index("(")].strip()
    return class_name.strip()


def fetch_spid_meta(force: bool = False) -> list[dict]:
    """선수 전체 목록 반환. 로컬 캐시 우선, 만료 시 갱신 시도.
    갱신 실패(API 키 없음 등) 시 구 캐시로 폴백 — 사용은 계속 가능."""
    if not force and _is_cache_fresh():
        with open(SPID_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    try:
        url = f"{API_BASE}/static/fconline/meta/spid.json"
        resp = _session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        META_CACHE_PATH.mkdir(parents=True, exist_ok=True)
        with open(SPID_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        return data
    except Exception:
        # 갱신 실패 → 구 캐시 폴백
        if SPID_CACHE_FILE.exists():
            with open(SPID_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        raise  # 캐시 자체가 없으면 예외 전파


def search_players(query: str, spid_list: list[dict]) -> list[dict]:
    """이름으로 선수 검색 (대소문자/공백 무시)."""
    q = query.strip().lower().replace(" ", "")
    if not q:
        return []
    results = []
    for entry in spid_list:
        name = entry.get("name", "").lower().replace(" ", "")
        if q in name:
            results.append(entry)
    return results[:50]  # 최대 50개


# ──────────────────────────────────────────
# 이미지
# ──────────────────────────────────────────

# 시즌 뱃지 캐시 (seasonId → PIL.Image)
_badge_cache: dict[int, Image.Image] = {}
_badge_cache_lock = threading.Lock()


def get_season_badge(season_id: int, img_url: str, size: int = 24) -> Optional[Image.Image]:
    """시즌 뱃지 이미지 반환 (캐시 적용)."""
    with _badge_cache_lock:
        if season_id in _badge_cache:
            return _badge_cache[season_id]

    if not img_url:
        return None
    try:
        resp = _cdn_session.get(img_url, timeout=8)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        with _badge_cache_lock:
            _badge_cache[season_id] = img
        return img
    except Exception:
        return None


def prefetch_season_badges(seasons: list[dict]):
    """시즌 뱃지 이미지를 백그라운드에서 미리 캐시."""
    def _worker():
        for s in seasons:
            get_season_badge(s["seasonId"], s.get("seasonImg", ""))
    threading.Thread(target=_worker, daemon=True).start()


def get_player_image(spid: int) -> Optional[Image.Image]:
    """선수 미페 이미지 원본 반환 (메모리 캐시 적용). 크기 조정은 호출부에서 처리."""
    with _image_cache_lock:
        if spid in _image_cache:
            return _image_cache[spid]

    url = f"{CDN_BASE}/live/externalAssets/common/playersAction/p{spid}.png"
    try:
        resp = _cdn_session.get(url, timeout=10)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        # 원본 그대로 캐시 (resize 하지 않음)
        with _image_cache_lock:
            if len(_image_cache) >= IMAGE_CACHE_MAX:
                oldest_key = next(iter(_image_cache))
                del _image_cache[oldest_key]
            _image_cache[spid] = img

        return img
    except Exception:
        return None


def download_original_image(spid: int) -> Optional[bytes]:
    """원본 해상도 이미지 bytes 반환."""
    url = f"{CDN_BASE}/live/externalAssets/common/playersAction/p{spid}.png"
    try:
        resp = _cdn_session.get(url, timeout=15)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None


def clear_image_cache():
    with _image_cache_lock:
        _image_cache.clear()


def init(api_key: str):
    """앱 시작 시 API 키 설정."""
    _set_api_key(api_key)
