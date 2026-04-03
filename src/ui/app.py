"""메인 앱 윈도우"""

import threading

import customtkinter as ctk

from src.api import nexon_api
from src.core.config import Config
from src.core import updater
from src.ui.main_frame import MainFrame
from src.ui.settings_frame import SettingsFrame
from src.ui.history_frame import HistoryFrame
from version import APP_NAME, __version__


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._config = Config()

        # API 초기화
        nexon_api.init(self._config.get_api_key())

        # 윈도우 설정
        self.title(f"{APP_NAME} v{__version__}")
        self.geometry("960x680")
        self.minsize(800, 580)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._build()

        # 시작 시 업데이트 확인
        if self._config.check_update_on_start:
            threading.Thread(target=self._startup_update_check, daemon=True).start()

    # ──────────────────────────────────────────
    # 레이아웃
    # ──────────────────────────────────────────

    def _build(self):
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        # 업데이트 알림 배너 (기본 숨김)
        self._update_banner = ctk.CTkFrame(self, fg_color="#E65100", corner_radius=0, height=36)
        self._update_banner.columnconfigure(0, weight=1)

        self._banner_label = ctk.CTkLabel(
            self._update_banner,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="white",
        )
        self._banner_label.grid(row=0, column=0, sticky="w", padx=12)

        self._banner_btn = ctk.CTkButton(
            self._update_banner,
            text="다운로드",
            width=90,
            height=26,
            fg_color="white",
            text_color="#E65100",
            hover_color="#f5f5f5",
            command=self._open_update_url,
        )
        self._banner_btn.grid(row=0, column=1, padx=8, pady=4)

        ctk.CTkButton(
            self._update_banner,
            text="✕",
            width=28,
            height=26,
            fg_color="transparent",
            hover_color="#BF360C",
            text_color="white",
            command=self._hide_banner,
        ).grid(row=0, column=2, padx=(0, 6), pady=4)

        # 탭 뷰
        self._tabs = ctk.CTkTabview(self, anchor="nw")
        self._tabs.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        self._tabs.add("미페 변경")
        self._tabs.add("변경 이력")
        self._tabs.add("설정")

        self._main_frame = MainFrame(
            self._tabs.tab("미페 변경"), config=self._config
        )
        self._main_frame.pack(fill="both", expand=True)

        self._history_frame = HistoryFrame(
            self._tabs.tab("변경 이력"), config=self._config
        )
        self._history_frame.pack(fill="both", expand=True)

        self._settings_frame = SettingsFrame(
            self._tabs.tab("설정"), config=self._config
        )
        self._settings_frame.pack(fill="both", expand=True)

        # 탭 전환 시 이력 새로고침
        self._tabs.configure(command=self._on_tab_change)

    def _on_tab_change(self):
        if self._tabs.get() == "변경 이력":
            self._history_frame.refresh()

    # ──────────────────────────────────────────
    # 업데이트 배너
    # ──────────────────────────────────────────

    def _startup_update_check(self):
        result = updater.check_for_update(timeout=5)
        if result:
            self.after(0, lambda: self._show_banner(result))

    def _show_banner(self, result: dict):
        self._update_url = result["url"]
        version = result["version"]
        self._banner_label.configure(
            text=f"새 버전 {version}이(가) 출시됐습니다!"
        )
        self._update_banner.grid(row=0, column=0, sticky="ew")

    def _hide_banner(self):
        self._update_banner.grid_forget()

    def _open_update_url(self):
        if hasattr(self, "_update_url"):
            updater.open_release_page(self._update_url)

    def run(self):
        self.mainloop()
