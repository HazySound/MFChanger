"""Nexon Open API / FC Online CDN 클라이언트"""

import json
import shutil
import threading
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

API_BASE = "https://nexon-api-proxy.cemigs1.workers.dev"  # CF Worker 프록시 (API 키 불필요)
CDN_BASE = "https://fco.dn.nexoncdn.co.kr"               # 이미지 (공개 CDN)

# 선수 이미지 CDN 경로 우선순위 (앞에서부터 순서대로 시도)
_CDN_IMAGE_PATHS = [
    "playersAction",
    "players",
    "playersActionHigh",
    "playersHigh",
]
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
IMAGE_CACHE_MAX = 300

# 이미지 소스 캐시 (spid -> CDN 상대 경로, 예: "players/p123456.png")
_image_source_cache: dict[int, str] = {}

# not_found 이미지 캐시
_not_found_image: Optional[Image.Image] = None
_not_found_lock = threading.Lock()

# 공식 미페 CDN 캐시 (spid -> PIL.Image) — 로컬 캐시와 분리
_official_image_cache: dict[int, Image.Image] = {}

# 로컬 assets 디렉터리 (_cache/live/externalAssets/common)
_assets_dir: Optional[Path] = None


def _set_api_key(api_key: str):
    pass  # CF Worker가 API 키를 처리하므로 클라이언트에서 불필요


def set_assets_dir(path: Path):
    """앱 초기화 시 로컬 assets 디렉터리 경로 주입."""
    global _assets_dir
    _assets_dir = path


# ──────────────────────────────────────────
# 메타데이터
# ──────────────────────────────────────────

def _is_cache_fresh() -> bool:
    """캐시 파일 존재 여부만 확인 (TTL 자동 갱신 없음 — 동기화는 수동)."""
    return SPID_CACHE_FILE.exists()


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


def sync_meta(backup_dir: Path) -> dict:
    """
    선수/시즌 메타데이터 강제 동기화.
    1. 기존 캐시 파일을 backup_dir에 타임스탬프 백업
    2. CF Worker에서 최신 파일 다운로드 (실패 시 예외 전파)
    반환: {"spid": 선수수, "seasons": 시즌수}
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    meta_backup = backup_dir / "meta_backup"

    season_cache = META_CACHE_PATH / "seasonid.json"
    for cache_file, prefix in [(SPID_CACHE_FILE, "spid"), (season_cache, "seasonid")]:
        if cache_file.exists():
            meta_backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cache_file, meta_backup / f"{prefix}_{timestamp}.json")

    # 다운로드 실패 시 예외를 그대로 전파 (폴백 없음)
    url_spid = f"{API_BASE}/static/fconline/meta/spid.json"
    resp = _session.get(url_spid, timeout=15)
    resp.raise_for_status()
    spid_list = resp.json()
    META_CACHE_PATH.mkdir(parents=True, exist_ok=True)
    SPID_CACHE_FILE.write_text(
        json.dumps(spid_list, ensure_ascii=False), encoding="utf-8"
    )

    url_season = f"{API_BASE}/static/fconline/meta/seasonid.json"
    resp = _session.get(url_season, timeout=15)
    resp.raise_for_status()
    seasons_raw = resp.json()
    (META_CACHE_PATH / "seasonid.json").write_text(
        json.dumps(seasons_raw, ensure_ascii=False), encoding="utf-8"
    )

    return {"spid": len(spid_list), "seasons": len(seasons_raw)}


def search_players(query: str, spid_list: list[dict]) -> list[dict]:
    """이름으로 선수 검색 (대소문자/공백 무시). 개수 제한 없음 — 호출부에서 처리."""
    q = query.strip().lower().replace(" ", "")
    if not q:
        return []
    return [
        entry for entry in spid_list
        if q in entry.get("name", "").lower().replace(" ", "")
    ]


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


def _spid_to_pid(spid: int) -> int:
    """spid 뒤 6자리에서 선수 고유 pid 추출. int() 변환으로 앞 0 제거."""
    s = str(spid)
    return int(s[-6:]) if len(s) > 6 else spid


def _fetch_image_from_url(url: str) -> Optional[Image.Image]:
    try:
        resp = _cdn_session.get(url, timeout=5)
        if resp.status_code == 200:
            return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception:
        pass
    return None


def _fetch_image_from_local(relative: str) -> Optional[Image.Image]:
    """로컬 assets 디렉터리에서 이미지 로드. assets_dir 미설정 또는 파일 없으면 None."""
    if _assets_dir is None:
        return None
    try:
        path = _assets_dir / relative
        if path.exists():
            return Image.open(path).convert("RGBA")
    except Exception:
        pass
    return None


def get_player_image(spid: int) -> Optional[Image.Image]:
    """선수 이미지 반환.
    1차: 로컬 assets에서 4개 경로 spid 기준 탐색
    2차: 로컬 assets에서 pid 기준 탐색
    3차: CDN 4개 경로 spid 기준 (로컬 없을 때 폴백)
    4차: CDN pid 기준
    5차: players/not_found.png
    결과는 메모리 캐시에 저장.
    """
    with _image_cache_lock:
        if spid in _image_cache:
            return _image_cache[spid]

    # 1차 — 로컬 spid 기준
    for cdn_path in _CDN_IMAGE_PATHS:
        relative = f"{cdn_path}/p{spid}.png"
        img = _fetch_image_from_local(relative)
        if img is not None:
            _cache_image(spid, img, source=relative)
            return img

    # 2차 — 로컬 pid 기준
    pid = _spid_to_pid(spid)
    if pid != spid:
        for cdn_path in ("players", "playersHigh"):
            relative = f"{cdn_path}/p{pid}.png"
            img = _fetch_image_from_local(relative)
            if img is not None:
                _cache_image(spid, img, source=relative)
                return img

    # 3차 — CDN spid 기준 (로컬 폴백)
    for cdn_path in _CDN_IMAGE_PATHS:
        img = _fetch_image_from_url(
            f"{CDN_BASE}/live/externalAssets/common/{cdn_path}/p{spid}.png"
        )
        if img is not None:
            _cache_image(spid, img, source=f"{cdn_path}/p{spid}.png")
            return img

    # 4차 — CDN pid 기준
    if pid != spid:
        for cdn_path in ("players", "playersHigh"):
            img = _fetch_image_from_url(
                f"{CDN_BASE}/live/externalAssets/common/{cdn_path}/p{pid}.png"
            )
            if img is not None:
                _cache_image(spid, img, source=f"{cdn_path}/p{pid}.png")
                return img

    # 5차 — not_found.png 폴백
    not_found = _get_not_found_image()
    if not_found is not None:
        _cache_image(spid, not_found, source="players/not_found.png")
        return not_found

    return None


def get_official_player_image(spid: int) -> Optional[Image.Image]:
    """공식 미페 프리뷰용 — CDN 전용 (로컬 파일 무시).
    로컬에서 바꾼 미페와 무관하게 서버 원본 이미지를 반환.
    별도 캐시(_official_image_cache) 사용.
    """
    with _image_cache_lock:
        if spid in _official_image_cache:
            return _official_image_cache[spid]

    # CDN spid 기준
    for cdn_path in _CDN_IMAGE_PATHS:
        img = _fetch_image_from_url(
            f"{CDN_BASE}/live/externalAssets/common/{cdn_path}/p{spid}.png"
        )
        if img is not None:
            with _image_cache_lock:
                _official_image_cache[spid] = img
            return img

    # CDN pid 기준
    pid = _spid_to_pid(spid)
    if pid != spid:
        for cdn_path in ("players", "playersHigh"):
            img = _fetch_image_from_url(
                f"{CDN_BASE}/live/externalAssets/common/{cdn_path}/p{pid}.png"
            )
            if img is not None:
                with _image_cache_lock:
                    _official_image_cache[spid] = img
                return img

    # not_found 폴백
    not_found = _get_not_found_image()
    if not_found is not None:
        with _image_cache_lock:
            _official_image_cache[spid] = not_found
    return not_found


def _get_not_found_image() -> Optional[Image.Image]:
    """players/not_found.png 로드 (전역 단일 캐시)."""
    global _not_found_image
    with _not_found_lock:
        if _not_found_image is not None:
            return _not_found_image
    img = _fetch_image_from_url(
        f"{CDN_BASE}/live/externalAssets/common/players/not_found.png"
    )
    if img is not None:
        with _not_found_lock:
            _not_found_image = img
    return img


def get_image_source(spid: int) -> Optional[str]:
    """spid에 대해 실제 이미지를 로드한 CDN 상대 경로 반환.
    예: 'players/p123456.png', 'playersAction/p200123456.png'
    이미지가 아직 로드되지 않은 경우 None 반환."""
    with _image_cache_lock:
        return _image_source_cache.get(spid)


def _cache_image(spid: int, img: Optional[Image.Image], source: str = ""):
    with _image_cache_lock:
        if len(_image_cache) >= IMAGE_CACHE_MAX:
            oldest_key = next(iter(_image_cache))
            del _image_cache[oldest_key]
        _image_cache[spid] = img
        if source:
            _image_source_cache[spid] = source


def download_original_image(spid: int) -> Optional[bytes]:
    """원본 해상도 이미지 bytes 반환. 로컬 우선, 없으면 CDN."""
    # 로컬 우선
    if _assets_dir is not None:
        pid = _spid_to_pid(spid)
        for cdn_path in _CDN_IMAGE_PATHS:
            path = _assets_dir / f"{cdn_path}/p{spid}.png"
            if path.exists():
                return path.read_bytes()
        if pid != spid:
            for cdn_path in ("players", "playersHigh"):
                path = _assets_dir / f"{cdn_path}/p{pid}.png"
                if path.exists():
                    return path.read_bytes()

    # CDN 폴백
    for cdn_path in _CDN_IMAGE_PATHS:
        url = f"{CDN_BASE}/live/externalAssets/common/{cdn_path}/p{spid}.png"
        try:
            resp = _cdn_session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            continue
    return None


def clear_image_cache():
    with _image_cache_lock:
        _image_cache.clear()


def invalidate_player_cache(spid: int):
    """특정 선수의 캐시 항목만 삭제 — 미페 교체 후 썸네일 갱신에 사용."""
    with _image_cache_lock:
        _image_cache.pop(spid, None)


def init(api_key: str):
    """앱 시작 시 API 키 설정."""
    _set_api_key(api_key)
