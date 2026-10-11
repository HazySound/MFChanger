"""GitHub Releases 기반 업데이트 확인 및 설치"""

import ctypes
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import certifi
import requests
from packaging.version import Version

from version import __version__, GITHUB_REPO

RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# frozen(PyInstaller) 환경에서만 자동 설치 지원
IS_FROZEN = getattr(sys, "frozen", False)

# exe 다운로드를 허용하는 호스트 (GitHub Releases 에셋)
_ALLOWED_DOWNLOAD_HOSTS = (
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
)

UPDATE_FILE_NAME = "_MFChanger_update.exe"
OLD_SUFFIX = ".old.exe"
# 구버전(bat 방식) 업데이터가 남길 수 있는 파일
_LEGACY_LEFTOVERS = ("_update.bat",)


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

        # exe 에셋 URL 탐색 (GitHub 외 호스트는 무시)
        download_url: Optional[str] = None
        for asset in data.get("assets", []):
            name = asset.get("name", "").lower()
            url = asset.get("browser_download_url") or ""
            if name.endswith(".exe") and urlparse(url).hostname in _ALLOWED_DOWNLOAD_HOSTS:
                download_url = url
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

    if urlparse(download_url).hostname not in _ALLOWED_DOWNLOAD_HOSTS:
        raise RuntimeError("허용되지 않은 다운로드 주소입니다.")

    current_exe = Path(sys.executable)
    tmp_path = current_exe.parent / UPDATE_FILE_NAME

    # 실행 파일은 인증서 검증 없이 받지 않음 (verify=False 폴백 금지)
    try:
        resp = requests.get(download_url, verify=certifi.where(), stream=True, timeout=60)
    except requests.exceptions.SSLError:
        raise RuntimeError(
            "보안 연결(SSL) 확인에 실패했습니다. 릴리즈 페이지에서 직접 받아주세요."
        )

    try:
        with resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        progress_cb(downloaded / total)

        # 중간에 끊긴 파일로 exe를 교체하지 않도록 크기 검증
        if downloaded == 0 or (total and downloaded != total):
            raise RuntimeError(
                f"다운로드가 완료되지 않았습니다. ({downloaded:,} / {total:,} bytes)"
            )
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    if progress_cb:
        progress_cb(1.0)

    # Zone.Identifier ADS 제거 — 인터넷 다운로드 표시를 지워
    # Windows Defender/SmartScreen이 추출된 DLL을 격리하는 것을 방지
    try:
        ctypes.windll.kernel32.DeleteFileW(str(tmp_path) + ":Zone.Identifier")
    except Exception:
        pass

    return tmp_path


def _old_exe_path(current_exe: Path) -> Path:
    return current_exe.with_name(current_exe.stem + OLD_SUFFIX)


def apply_update(new_exe_path: Path):
    """
    실행 중인 exe를 새 exe로 교체 후 재실행. 반환하지 않음 (sys.exit).

    Windows는 실행 중인 exe의 삭제는 막지만 이름 변경은 허용하므로
    현재 exe → *.old.exe 로 비켜두고 그 자리에 새 exe를 넣는다.
    새 프로세스는 PYINSTALLER_RESET_ENVIRONMENT=1 로 실행해 현재 프로세스의
    _MEI 임시 폴더/환경을 물려받지 않게 한다 (PyInstaller 6.9+ 공식 방식).
    남은 *.old.exe 는 새 버전 시작 시 cleanup_after_update()가 삭제.
    """
    current_exe = Path(sys.executable)
    old_exe = _old_exe_path(current_exe)

    # 이전 업데이트 잔여물 (보통 cleanup에서 지워지지만 남아 있을 수 있음)
    try:
        old_exe.unlink(missing_ok=True)
    except OSError:
        old_exe = current_exe.with_name(f"{current_exe.stem}.{os.getpid()}{OLD_SUFFIX}")

    os.replace(current_exe, old_exe)
    try:
        os.replace(new_exe_path, current_exe)
    except OSError:
        os.replace(old_exe, current_exe)   # 원상복구 — 기존 버전 그대로 유지
        raise

    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    subprocess.Popen(
        [str(current_exe)],
        cwd=str(current_exe.parent),
        env=env,
        close_fds=True,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    sys.exit(0)


def cleanup_after_update():
    """
    앱 시작 시 호출 — 업데이트 잔여 파일 정리 (백그라운드).
    직전 버전 프로세스가 아직 종료 중이면 *.old.exe 가 잠겨 있으므로 잠시 재시도.
    """
    if not IS_FROZEN:
        return
    app_dir = Path(sys.executable).parent

    # 받다 만 업데이트 파일 / 구버전 bat — 한 번만 시도.
    # (재시도 루프에 넣으면 이후 새로 받은 같은 이름의 업데이트 파일을 지울 수 있음)
    for name in (UPDATE_FILE_NAME, *_LEGACY_LEFTOVERS):
        try:
            (app_dir / name).unlink(missing_ok=True)
        except OSError:
            pass

    def _worker():
        # 직전 버전 exe — 그 프로세스가 종료될 때까지 잠겨 있으므로 재시도
        pending = list(app_dir.glob(f"*{OLD_SUFFIX}"))
        for _ in range(30):
            if not pending:
                return
            remaining = []
            for t in pending:
                try:
                    t.unlink(missing_ok=True)
                except OSError:
                    remaining.append(t)
            pending = remaining
            time.sleep(1)

    threading.Thread(target=_worker, daemon=True).start()


def open_release_page(url: str):
    webbrowser.open(url)
