"""화면(빌드된 웹 파일)과 이미지를 제공하는 로컬 HTTP 서버.

  /                  빌드된 프론트엔드 (frontend/dist)
  /game/<경로>        게임 리소스 폴더의 파일 — ?fallback=cdn 이면 없을 때 CDN으로 리다이렉트
  /file?path=<경로>   백업·업로드 폴더의 파일 (그 밖의 경로는 거부)
  /data/players.json  선수 메타데이터 캐시
"""

import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, quote, unquote, urlsplit

from src.api import nexon_api
from src.core import history
from src.core.config import CACHE_DIR, Config

UPLOAD_DIR = CACHE_DIR / "uploads"

NO_STORE = "no-store"                        # 게임 파일·백업 — 언제든 바뀜
IMMUTABLE = "max-age=31536000, immutable"   # 빌드 산출물 (파일명에 해시 포함)
REVALIDATE = "no-cache"                      # index.html 등

# Windows 레지스트리 설정에 따라 .js가 text/plain으로 잡히는 경우가 있어 직접 지정
_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}


@dataclass
class _Response:
    file: Optional[Path] = None
    redirect: Optional[str] = None
    cache: str = NO_STORE


def _inside(root: Path, path: Path) -> Optional[Path]:
    """root 아래의 파일이면 정규화된 경로, 아니면 None (../ 로 벗어나는 경로 차단)."""
    try:
        resolved = path.resolve()
    except (OSError, ValueError):
        return None
    if resolved.is_relative_to(root.resolve()) and resolved.is_file():
        return resolved
    return None


class AssetServer:
    def __init__(self, config: Config, web_dir: Optional[Path], port: int = 0):
        self._config = config
        self._web_dir = web_dir
        self._httpd = ThreadingHTTPServer(("127.0.0.1", port), self._handler_class())
        self._httpd.daemon_threads = True

    @property
    def url(self) -> str:
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self):
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    # ── 화면에서 쓸 이미지 주소 ──

    def game_url(self, relative: str, fallback_cdn: bool = False) -> Optional[str]:
        """게임 리소스 파일 주소. 파일이 없으면 CDN 주소(fallback_cdn) 또는 None.
        수정 시각을 붙여 교체 직후 웹뷰가 이전 이미지를 다시 쓰지 않게 한다."""
        path = self._config.assets_dir / relative
        if path.is_file():
            return f"{self.url}/game/{quote(relative)}?v={path.stat().st_mtime_ns}"
        return nexon_api.cdn_url(relative) if fallback_cdn else None

    def file_url(self, path: Optional[str]) -> Optional[str]:
        if not path or not Path(path).is_file():
            return None
        return f"{self.url}/file?path={quote(path)}&v={Path(path).stat().st_mtime_ns}"

    # ── 요청 처리 ──

    def _allowed_file(self, requested: Path) -> Optional[Path]:
        """백업·업로드 폴더의 파일, 또는 이력이 가리키는 파일(백업 폴더를 옮긴 경우)만 허용."""
        for root in (self._config.backup_path, UPLOAD_DIR):
            file = _inside(root, requested)
            if file is not None:
                return file
        resolved = requested.resolve()
        return resolved if resolved in history.referenced_files() and resolved.is_file() else None

    def _route(self, target: str) -> _Response:
        parts = urlsplit(target)
        path, query = unquote(parts.path), parse_qs(parts.query)

        if path.startswith("/game/"):
            relative = path.removeprefix("/game/")
            file = _inside(self._config.assets_dir, self._config.assets_dir / relative)
            if file is None and query.get("fallback") == ["cdn"]:
                return _Response(redirect=nexon_api.cdn_url(relative))
            return _Response(file)

        if path == "/file":
            return _Response(self._allowed_file(Path(query.get("path", [""])[0])))

        if path == "/data/players.json":
            return _Response(nexon_api.SPID_CACHE_FILE)

        if self._web_dir is None:   # 개발 모드: 화면은 Vite 개발 서버가 제공
            return _Response()
        file = _inside(self._web_dir, self._web_dir / path.lstrip("/"))
        if file is None:            # 없는 경로는 index.html (SPA)
            return _Response(self._web_dir / "index.html", cache=REVALIDATE)
        return _Response(file, cache=IMMUTABLE if path.startswith("/assets/") else REVALIDATE)

    def _handler_class(self) -> type[BaseHTTPRequestHandler]:
        route = self._route
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                # 다른 사이트가 DNS 리바인딩으로 이 서버를 읽지 못하게 Host를 확인
                port = server._httpd.server_address[1]
                if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                response = route(self.path)
                if response.redirect:
                    self.send_response(HTTPStatus.FOUND)
                    self.send_header("Location", response.redirect)
                    self.end_headers()
                    return
                try:
                    body = response.file.read_bytes() if response.file else None
                except OSError:
                    body = None
                if body is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", _MIME.get(response.file.suffix.lower(), "application/octet-stream"))
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", response.cache)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass   # 요청마다 콘솔에 찍지 않음

        return Handler
