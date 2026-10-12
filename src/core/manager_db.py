"""감독 DB — managers_db.json (없으면 데이터센터 감독 페이지를 크롤링해 생성)"""

import json
import re

import requests
from bs4 import BeautifulSoup

from .config import CACHE_DIR

DB_PATH = CACHE_DIR / "managers_db.json"
_DATACENTER_URL = "https://fconline.nexon.com/datacenter/manager"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# 메모리 캐시 (프로세스 재시작 전까지 유지)
_cache: dict[str, dict] | None = None


def build_db(timeout: int = 15) -> dict[str, dict]:
    """
    FC온라인 데이터센터 감독 페이지를 크롤링해서 DB를 구성하고 저장.
    반환: {manager_id: {"name": ..., "team": ...}}
    """
    resp = requests.get(_DATACENTER_URL, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = "utf-8"

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("div.tbody > div.tr")

    db: dict[str, dict] = {}
    for row in rows:
        try:
            coach = row.find("span", class_="rank_coach")
            if not coach:
                continue
            name = coach.find("span", class_="name").get_text(strip=True)
            team = coach.find("span", class_="desc").get_text(strip=True)
            src = coach.find("span", class_="thumb").find("img")["src"]
            m = re.search(r"heads_staff_(\d+)\.png", src)
            if not m:
                continue
            db[m.group(1)] = {"name": name, "team": team}
        except (AttributeError, KeyError, TypeError):
            continue

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    return db


def load_db() -> dict[str, dict]:
    """DB 파일을 읽어 반환. 없거나 읽을 수 없으면 빈 dict (자동 생성은 ensure_db)."""
    if not DB_PATH.exists():
        return {}
    try:
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def ensure_db(force_rebuild: bool = False) -> dict[str, dict]:
    """
    DB가 없거나 force_rebuild=True이면 크롤링 후 반환.
    있으면 메모리 캐시 또는 파일에서 반환.
    """
    global _cache
    if not force_rebuild and _cache:
        return _cache
    if not force_rebuild and DB_PATH.exists():
        _cache = load_db()
        return _cache
    _cache = build_db()
    return _cache
