"""GitHub Releases 기반 자동 업데이트 확인"""

import webbrowser
from typing import Optional

import requests
from packaging.version import Version

from version import __version__, GITHUB_REPO

RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def check_for_update(timeout: int = 5) -> Optional[dict]:
    """
    최신 릴리즈 확인.
    새 버전이 있으면 {"version": "v1.2.0", "url": "...", "notes": "..."} 반환.
    최신 버전이면 None 반환.
    """
    try:
        resp = requests.get(RELEASES_API, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        latest_tag = data.get("tag_name", "").lstrip("v")
        if not latest_tag:
            return None

        if Version(latest_tag) > Version(__version__):
            return {
                "version": data["tag_name"],
                "url": data.get("html_url", ""),
                "notes": data.get("body", ""),
            }
        return None
    except Exception:
        return None


def open_release_page(url: str):
    webbrowser.open(url)
