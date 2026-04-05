"""메인 앱 윈도우"""

import threading
import webbrowser
from pathlib import Path

import customtkinter as ctk

from src.api import nexon_api
from src.ui import font_manager as fm
from src.core.config import Config
from src.core import updater, db_init
from src.ui.main_frame import MainFrame
from src.ui.crest_frame import CrestFrame
from src.ui.manager_frame import ManagerFrame
from src.ui.settings_frame import SettingsFrame
from src.ui.history_frame import HistoryFrame
from version import APP_NAME, __version__


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._config = Config()
        self._update_result: dict = {}

        # API 초기화 (CF Worker 프록시 사용 — 클라이언트 키 불필요)
        nexon_api.init("")
        nexon_api.set_assets_dir(self._config.assets_dir)

        # 폰트 크기 설정 (위젯 크기는 고정, 폰트만 배율 적용)
        from src.ui import font_manager
        font_manager.init(self._config.ui_scale)

        # 윈도우 설정
        self.title(f"{APP_NAME} v{__version__}")
        self.geometry("960x680")
        self.minsize(780, 560)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # 윈도우 아이콘 (ctypes로 대/소 아이콘 모두 설정)
        self.after(0, self._apply_icon)

        # DnD 초기화 (루트 윈도우에 단일 훅)
        from src.core import dnd_manager
        dnd_manager.init(self)

        self._build()

        # 업데이트 확인 → 완료 후 DB 파일 체크 → 없으면 생성
        # (업데이트가 항상 우선: DB 로직이 바뀐 버전으로 먼저 업데이트 후 DB 빌드)
        self._pending_db_missing = db_init.check_missing()
        if self._config.check_update_on_start:
            threading.Thread(target=self._startup_update_check, daemon=True).start()
        elif self._pending_db_missing:
            self.after(0, lambda: self._start_db_init(self._pending_db_missing))

    def _apply_icon(self):
        try:
            import ctypes
            import sys
            if getattr(sys, "frozen", False):
                # PyInstaller frozen: _MEIPASS 안에 번들된 경로
                base = Path(sys._MEIPASS)
            else:
                # 개발 환경: 프로젝트 루트
                base = Path(__file__).parent.parent.parent
            icon_path = base / "assets" / "icon" / "icon.ico"
            if not icon_path.exists():
                return
            path_str = str(icon_path)

            # 기본 아이콘 (제목표시줄 / 작업표시줄 소 아이콘)
            self.iconbitmap(path_str)

            # 큰 아이콘 별도 설정 (Alt+Tab, 작업표시줄 큰 아이콘 등)
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, self.title())
            if hwnd:
                hicon_big = user32.LoadImageW(
                    None, path_str,
                    1,              # IMAGE_ICON
                    0, 0,           # 0,0 = 시스템 기본 큰 아이콘 크기
                    0x0010 | 0x0040 # LR_LOADFROMFILE | LR_DEFAULTSIZE
                )
                user32.SendMessageW(hwnd, 0x0080, 1, hicon_big)  # WM_SETICON, ICON_BIG
        except Exception:
            pass

    # ──────────────────────────────────────────
    # 레이아웃
    # ──────────────────────────────────────────

    def _build(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # 업데이트 알림 배너 (기본 숨김)
        self._update_banner = ctk.CTkFrame(self, fg_color="#E65100", corner_radius=0)
        self._update_banner.columnconfigure(0, weight=1)

        self._banner_label = ctk.CTkLabel(
            self._update_banner,
            text="",
            font=fm.font(12),
            text_color="white",
        )
        self._banner_label.grid(row=0, column=0, sticky="w", padx=12, pady=(6, 2))

        self._banner_install_btn = ctk.CTkButton(
            self._update_banner,
            text="업데이트 설치",
            width=110,
            height=26,
            fg_color="white",
            text_color="#E65100",
            hover_color="#f5f5f5",
            command=self._on_banner_install_click,
        )
        self._banner_install_btn.grid(row=0, column=1, padx=(0, 4), pady=4)

        self._banner_page_btn = ctk.CTkButton(
            self._update_banner,
            text="릴리즈 페이지",
            width=100,
            height=26,
            fg_color="transparent",
            border_width=1,
            border_color="white",
            text_color="white",
            hover_color="#BF360C",
            command=self._open_update_url,
        )
        self._banner_page_btn.grid(row=0, column=2, padx=(0, 4), pady=4)

        ctk.CTkButton(
            self._update_banner,
            text="✕",
            width=28,
            height=26,
            fg_color="transparent",
            hover_color="#BF360C",
            text_color="white",
            command=self._hide_banner,
        ).grid(row=0, column=3, padx=(0, 6), pady=4)

        # 탭 뷰
        self._tabs = ctk.CTkTabview(self, anchor="nw")
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        # 사용법 버튼 — 탭 헤더 우측에 부유 배치
        ctk.CTkButton(
            self,
            text="사용법",
            width=68,
            height=28,
            font=fm.font(12),
            fg_color="transparent",
            border_width=1,
            border_color=("gray65", "gray45"),
            text_color=("gray20", "gray90"),
            hover_color=("gray85", "gray30"),
            command=lambda: webbrowser.open("https://github.com/HazySound/MFChanger"),
        ).place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=8)

        self._tabs.add("미페 변경")
        self._tabs.add("크레스트 변경")
        self._tabs.add("감독 변경")
        self._tabs.add("변경 이력")
        self._tabs.add("설정")

        self._main_frame = MainFrame(
            self._tabs.tab("미페 변경"), config=self._config
        )
        self._main_frame.pack(fill="both", expand=True)

        self._crest_frame = CrestFrame(
            self._tabs.tab("크레스트 변경"), config=self._config
        )
        self._crest_frame.pack(fill="both", expand=True)

        self._manager_frame = ManagerFrame(
            self._tabs.tab("감독 변경"), config=self._config
        )
        self._manager_frame.pack(fill="both", expand=True)

        self._history_frame = HistoryFrame(
            self._tabs.tab("변경 이력"),
            config=self._config,
            on_face_restored=self._on_face_restored,
            on_manager_restored=self._manager_frame.refresh_manager,
        )
        self._history_frame.pack(fill="both", expand=True)

        self._settings_frame = SettingsFrame(
            self._tabs.tab("설정"),
            config=self._config,
            on_install=self._start_update,
            on_sync_done=self._on_meta_synced,
        )
        self._settings_frame.pack(fill="both", expand=True)

        # 탭 전환 시 이력 새로고침
        self._tabs.configure(command=self._on_tab_change)

    def _on_tab_change(self):
        if self._tabs.get() == "변경 이력":
            self._history_frame.refresh()

    def _on_meta_synced(self):
        """동기화 완료 → 미페 변경 탭 검색 결과 즉시 갱신."""
        self._main_frame.reload_meta()

    def _on_face_restored(self, spid: int):
        """이력에서 미페 복원 → 검색 목록 썸네일 갱신."""
        self._main_frame.refresh_thumb(spid)

    # ──────────────────────────────────────────
    # 업데이트 배너
    # ──────────────────────────────────────────

    def _startup_update_check(self):
        result = updater.check_for_update(timeout=5)
        if result:
            self.after(0, lambda: self._show_banner(result))
        # 업데이트 확인 완료 후 누락 DB 생성
        if self._pending_db_missing:
            self.after(0, lambda: self._start_db_init(self._pending_db_missing))

    def _show_banner(self, result: dict):
        self._update_result = result
        version = result["version"]
        has_download = bool(result.get("download_url")) and updater.IS_FROZEN

        self._banner_label.configure(text=f"새 버전 {version}이(가) 출시됐습니다!")

        if has_download:
            self._banner_install_btn.grid()
        else:
            self._banner_install_btn.grid_remove()

        self._update_banner.grid(row=0, column=0, sticky="ew")

    def _hide_banner(self):
        self._update_banner.grid_forget()

    def _open_update_url(self):
        url = self._update_result.get("url", "")
        if url:
            updater.open_release_page(url)

    def _on_banner_install_click(self):
        download_url = self._update_result.get("download_url", "")
        if download_url:
            self._start_update(download_url)

    # ──────────────────────────────────────────
    # 업데이트 설치 (중앙화된 다운로드 + 잠금)
    # ──────────────────────────────────────────

    def _start_update(self, download_url: str):
        """배너/설정 양쪽에서 호출. 전체 화면 잠금 후 다운로드 시작."""
        self._show_update_overlay()

        def _worker():
            try:
                def _progress(pct: float):
                    self.after(0, lambda p=pct: self._on_download_progress(p))

                new_exe = updater.download_update(download_url, progress_cb=_progress)
                self.after(0, lambda: self._on_download_complete(new_exe))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_download_error(m))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_update_overlay(self):
        """전체 화면을 덮는 오버레이로 모든 입력 차단."""
        self._overlay = ctk.CTkFrame(self, corner_radius=0)
        self._overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self._overlay.lift()
        self._overlay.focus_set()  # 포커스 탈취로 키보드 입력 차단

        ctk.CTkLabel(
            self._overlay,
            text="업데이트 다운로드 중...",
            font=fm.font(20, "bold"),
        ).place(relx=0.5, rely=0.42, anchor="center")

        self._overlay_progress = ctk.CTkProgressBar(
            self._overlay, width=420, height=12
        )
        self._overlay_progress.set(0)
        self._overlay_progress.place(relx=0.5, rely=0.5, anchor="center")

        self._overlay_pct_label = ctk.CTkLabel(
            self._overlay,
            text="0%",
            font=fm.font(13),
            text_color="gray",
        )
        self._overlay_pct_label.place(relx=0.5, rely=0.56, anchor="center")

        ctk.CTkLabel(
            self._overlay,
            text="완료 후 자동으로 재시작됩니다. 프로그램을 종료하지 마세요.",
            font=fm.font(12),
            text_color="gray",
        ).place(relx=0.5, rely=0.62, anchor="center")

    def _on_download_progress(self, pct: float):
        self._overlay_progress.set(pct)
        self._overlay_pct_label.configure(text=f"{int(pct * 100)}%")

    def _on_download_complete(self, new_exe):
        self._overlay_pct_label.configure(text="설치 중... 잠시 후 재시작됩니다.", text_color="#4CAF50")
        self.after(500, lambda: updater.apply_update(new_exe))

    def _on_download_error(self, msg: str):
        # 오버레이 제거 후 입력 복원
        if hasattr(self, "_overlay"):
            self._overlay.place_forget()
            del self._overlay

        # 배너가 표시 중이면 상태 원상복구
        self._banner_label.configure(text=f"다운로드 실패: {msg}")
        self._banner_install_btn.configure(state="normal")

        # 설정 프레임 상태도 복구
        self._settings_frame.on_download_error(msg)

    # ──────────────────────────────────────────
    # DB 초기화 오버레이
    # ──────────────────────────────────────────

    def _start_db_init(self, missing: list[str]):
        """DB 파일 생성 오버레이 표시 후 백그라운드 작업 시작."""
        self._show_db_overlay(len(missing))
        threading.Thread(
            target=db_init.build_missing,
            args=(missing, lambda key, label, frac: self.after(0, lambda k=key, l=label, f=frac: self._on_db_step(k, l, f))),
            daemon=True,
        ).start()

    def _show_db_overlay(self, total_steps: int):
        self._db_overlay = ctk.CTkFrame(self, corner_radius=0)
        self._db_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self._db_overlay.lift()
        self._db_overlay.focus_set()

        ctk.CTkLabel(
            self._db_overlay,
            text="DB 생성 중...",
            font=fm.font(20, "bold"),
        ).place(relx=0.5, rely=0.38, anchor="center")

        self._db_step_label = ctk.CTkLabel(
            self._db_overlay,
            text="준비 중",
            font=fm.font(13),
            text_color="gray",
        )
        self._db_step_label.place(relx=0.5, rely=0.45, anchor="center")

        self._db_progress = ctk.CTkProgressBar(self._db_overlay, width=420, height=12)
        self._db_progress.set(0)
        self._db_progress.place(relx=0.5, rely=0.52, anchor="center")

        self._db_pct_label = ctk.CTkLabel(
            self._db_overlay,
            text="0%",
            font=fm.font(13),
            text_color="gray",
        )
        self._db_pct_label.place(relx=0.5, rely=0.58, anchor="center")

        ctk.CTkLabel(
            self._db_overlay,
            text=f"총 {total_steps}개 파일을 생성합니다. 잠시만 기다려주세요.",
            font=fm.font(12),
            text_color="gray",
        ).place(relx=0.5, rely=0.64, anchor="center")

    def _on_db_step(self, key: str, label: str, fraction: float):
        if key == "done":
            self._db_overlay.place_forget()
            del self._db_overlay
            return
        self._db_step_label.configure(text=f"생성 중: {label}")
        self._db_progress.set(fraction)
        self._db_pct_label.configure(text=f"{int(fraction * 100)}%")

    def run(self):
        self.mainloop()
