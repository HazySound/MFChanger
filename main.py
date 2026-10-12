"""MFChanger - FC온라인 미니페이스 변경 프로그램

  python main.py         빌드된 화면(frontend/dist)으로 실행
  python main.py --dev   Vite 개발 서버(npm run dev) 화면으로 실행 — 수정 즉시 반영
"""

import shutil
import sys
from pathlib import Path

import webview

from src.app.api import Api, Context
from src.app.server import UPLOAD_DIR, AssetServer
from src.core import updater
from src.core.config import Config
from version import APP_NAME, __version__

DEV_UI_URL = "http://localhost:5173"
DEV_SERVER_PORT = 17865   # 개발 모드에서는 고정 포트 (Vite 화면이 이미지 주소를 그대로 사용)


def _web_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "frontend" / "dist"


def main():
    dev = "--dev" in sys.argv
    updater.cleanup_after_update()
    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)   # 지난 실행에서 올린 임시 이미지

    config = Config()
    server = AssetServer(config, None if dev else _web_dir(), DEV_SERVER_PORT if dev else 0)
    server.start()

    ctx = Context(config, server)
    ctx.window = webview.create_window(
        f"{APP_NAME} v{__version__}",
        DEV_UI_URL if dev else server.url,
        js_api=Api(ctx),
        width=1180,
        height=780,
        min_size=(900, 620),
        background_color="#1C1C1E",
    )
    webview.start(debug=dev)


if __name__ == "__main__":
    main()
