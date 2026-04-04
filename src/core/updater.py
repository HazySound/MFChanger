"""GitHub Releases 기반 업데이트 확인 및 설치"""

import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Callable, Optional

import certifi
import requests
from packaging.version import Version

from version import __version__, GITHUB_REPO

RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# frozen(PyInstaller) 환경에서만 자동 설치 지원
IS_FROZEN = getattr(sys, "frozen", False)


def _safe_get(url: str, stream: bool = False, **kwargs) -> requests.Response:
    """SSL 검증 실패 시 certifi → verify=False 순으로 재시도."""
    try:
        return requests.get(url, verify=certifi.where(), stream=stream, **kwargs)
    except requests.exceptions.SSLError:
        return requests.get(url, verify=False, stream=stream, **kwargs)


def check_for_update(timeout: int = 5) -> Optional[dict]:
    """
    최신 릴리즈 확인.
    새 버전이 있으면 {"version", "url", "download_url", "notes"} 반환.
    download_url: exe 에셋 직접 다운로드 URL (없으면 None).
    최신 버전이거나 확인 실패 시 None 반환.
    """
    try:
        resp = _safe_get(RELEASES_API, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        latest_tag = data.get("tag_name", "").lstrip("v")
        if not latest_tag:
            return None

        if Version(latest_tag) <= Version(__version__):
            return None

        # exe 에셋 URL 탐색
        download_url: Optional[str] = None
        for asset in data.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".exe"):
                download_url = asset.get("browser_download_url")
                break

        return {
            "version": data["tag_name"],
            "url": data.get("html_url", ""),
            "download_url": download_url,
            "notes": data.get("body", ""),
        }
    except Exception:
        return None


def download_update(
    download_url: str,
    progress_cb: Optional[Callable[[float], None]] = None,
) -> Path:
    """
    새 exe를 현재 exe 옆에 임시 파일로 다운로드.
    progress_cb(0.0~1.0) 로 진행률 콜백.
    완료 시 임시 파일 경로 반환.
    frozen 환경이 아니면 RuntimeError.
    """
    if not IS_FROZEN:
        raise RuntimeError("개발 환경에서는 자동 업데이트를 지원하지 않습니다.")

    current_exe = Path(sys.executable)
    tmp_path = current_exe.parent / "_MFChanger_update.exe"

    with _safe_get(download_url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total:
                    progress_cb(downloaded / total)

    if progress_cb:
        progress_cb(1.0)

    return tmp_path


def apply_update(new_exe_path: Path):
    """
    배치 스크립트로 현재 exe를 새 exe로 교체 후 재실행.
    이 함수가 반환되지 않음 (sys.exit 호출).
    """
    current_exe = Path(sys.executable)
    bat_path = new_exe_path.parent / "_update.bat"

    bat = (
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'move /y "{new_exe_path}" "{current_exe}"\r\n'
        f'start "" "{current_exe}"\r\n'
        'del "%~f0"\r\n'
    )
    bat_path.write_bytes(bat.encode("mbcs", errors="replace"))

    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE

    subprocess.Popen(str(bat_path), startupinfo=si, close_fds=True)
    sys.exit(0)


def open_release_page(url: str):
    webbrowser.open(url)
