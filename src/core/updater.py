"""GitHub Releases 기반 업데이트 확인 및 설치"""

import ctypes
import os
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

    # Zone.Identifier ADS 제거 — 인터넷 다운로드 표시를 지워
    # Windows Defender/SmartScreen이 추출된 DLL을 격리하는 것을 방지
    try:
        ctypes.windll.kernel32.DeleteFileW(str(tmp_path) + ":Zone.Identifier")
    except Exception:
        pass

    return tmp_path


def apply_update(new_exe_path: Path):
    """
    배치 스크립트로 현재 exe를 새 exe로 교체 후 재실행.
    구 프로세스 PID가 완전히 사라진 뒤에 새 exe를 실행해
    PyInstaller 임시 폴더(_MEI*) 삭제 전 재실행으로 인한 DLL 오류를 방지.
    이 함수가 반환되지 않음 (sys.exit 호출).
    """
    current_exe = Path(sys.executable)
    bat_path = new_exe_path.parent / "_update.bat"
    pid = os.getpid()
    mei_path = getattr(sys, "_MEIPASS", None)  # PyInstaller 임시 추출 경로

    # 1단계: PID 소멸 대기
    bat = (
        "@echo off\r\n"
        ":pidloop\r\n"
        f'tasklist /FI "PID eq {pid}" 2>NUL | find /I "{pid}" >NUL\r\n'
        "if not errorlevel 1 (\r\n"
        "    timeout /t 1 /nobreak >nul\r\n"
        "    goto pidloop\r\n"
        ")\r\n"
    )

    # 2단계: _MEI 임시 폴더 삭제 완료 대기 (atexit cleanup 종료 보장)
    if mei_path:
        bat += (
            ":meiloop\r\n"
            f'if exist "{mei_path}" (\r\n'
            "    timeout /t 1 /nobreak >nul\r\n"
            "    goto meiloop\r\n"
            ")\r\n"
        )

    # 3단계: 파일 교체 및 재실행
    # explorer.exe 경유 실행 — ShellExecute로 완전히 새 환경에서 시작되므로
    # start "" 방식의 DLL 탐색 경로 상속 문제가 없음
    bat += (
        f'move /y "{new_exe_path}" "{current_exe}"\r\n'
        f'explorer.exe "{current_exe}"\r\n'
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
