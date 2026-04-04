"""설정 화면 프레임"""

import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from src.core.config import Config
from src.core import updater
from src.ui import font_manager as fm
from version import __version__


class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master, config: Config, on_install: Callable[[str], None],
                 on_sync_done: Callable = None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._config = config
        self._on_install = on_install  # App에서 주입 — 실제 다운로드는 App이 처리
        self._on_sync_done = on_sync_done  # 동기화 완료 시 App이 main_frame 갱신
        self._update_result: dict = {}
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, label_text="설정")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)
        scroll.columnconfigure(1, weight=1)

        row = 0

        # ── FC온라인 설치 경로 ──
        self._section_label(scroll, "FC온라인 설치 경로", row)
        row += 1

        self._fc_path_entry = ctk.CTkEntry(scroll, height=34)
        self._fc_path_entry.insert(0, self._config.fc_online_path)
        self._fc_path_entry.grid(row=row, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 4))
        row += 1

        fc_btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        fc_btn_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 12))

        ctk.CTkButton(fc_btn_frame, text="폴더 선택", width=100, command=self._browse_fc_path).pack(side="left", padx=(0, 8))
        ctk.CTkButton(fc_btn_frame, text="저장", width=80, command=self._save_fc_path).pack(side="left")

        self._fc_path_status = ctk.CTkLabel(scroll, text="", font=fm.font(11))
        self._fc_path_status.grid(row=row, column=1, sticky="e", padx=16)
        row += 1

        self._validate_fc_path()

        # ── 백업 설정 ──
        self._section_label(scroll, "백업 설정", row)
        row += 1

        self._backup_switch = ctk.CTkSwitch(
            scroll, text="교체 전 원본 파일 자동 백업",
            command=self._toggle_backup
        )
        self._backup_switch.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))
        if self._config.backup_enabled:
            self._backup_switch.select()
        row += 1

        ctk.CTkLabel(scroll, text="백업 저장 위치", font=fm.font(12)).grid(
            row=row, column=0, sticky="w", padx=16, pady=(0, 4)
        )
        row += 1

        self._backup_path_entry = ctk.CTkEntry(scroll, height=34)
        self._backup_path_entry.insert(0, str(self._config.backup_path))
        self._backup_path_entry.grid(row=row, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 4))
        row += 1

        backup_btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        backup_btn_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 16))
        ctk.CTkButton(backup_btn_frame, text="폴더 선택", width=100, command=self._browse_backup_path).pack(side="left", padx=(0, 8))
        ctk.CTkButton(backup_btn_frame, text="저장", width=80, command=self._save_backup_path).pack(side="left")
        row += 1

        # ── 폰트 크기 설정 ──
        self._section_label(scroll, "폰트 크기", row)
        row += 1

        _SCALE_OPTIONS = {"작게": 0.85, "보통": 1.0, "크게": 1.25, "매우 크게": 1.5}
        _SCALE_REVERSE = {v: k for k, v in _SCALE_OPTIONS.items()}
        self._scale_options = _SCALE_OPTIONS

        scale_row = ctk.CTkFrame(scroll, fg_color="transparent")
        scale_row.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 4))

        self._scale_seg = ctk.CTkSegmentedButton(
            scale_row,
            values=list(_SCALE_OPTIONS.keys()),
            command=self._on_scale_change,
        )
        current_label = _SCALE_REVERSE.get(self._config.ui_scale, "크게")
        self._scale_seg.set(current_label)
        self._scale_seg.pack(side="left", padx=(0, 12))

        self._scale_status = ctk.CTkLabel(
            scale_row, text="", font=fm.font(11), text_color="gray"
        )
        self._scale_status.pack(side="left")
        row += 1

        row += 1  # 여백

        # ── 선수 데이터 동기화 ──
        self._section_label(scroll, "선수 데이터", row)
        row += 1

        sync_btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        sync_btn_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 4))

        self._sync_btn = ctk.CTkButton(
            sync_btn_frame, text="데이터 동기화", width=120, command=self._sync_meta
        )
        self._sync_btn.pack(side="left", padx=(0, 12))

        self._sync_status = ctk.CTkLabel(
            sync_btn_frame, text="선수 목록과 시즌 정보를 최신으로 업데이트합니다.",
            font=fm.font(11), text_color="gray"
        )
        self._sync_status.pack(side="left")
        row += 1

        row += 1  # 여백

        # ── 업데이트 설정 ──
        self._section_label(scroll, "업데이트", row)
        row += 1

        self._update_switch = ctk.CTkSwitch(
            scroll, text="시작 시 업데이트 자동 확인",
            command=self._toggle_update_check
        )
        self._update_switch.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))
        if self._config.check_update_on_start:
            self._update_switch.select()
        row += 1

        update_btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        update_btn_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 4))

        self._check_btn = ctk.CTkButton(
            update_btn_frame, text="업데이트 확인", width=120, command=self._check_update
        )
        self._check_btn.pack(side="left", padx=(0, 8))

        # 업데이트 있을 때만 표시
        self._install_btn = ctk.CTkButton(
            update_btn_frame,
            text="업데이트 설치",
            width=120,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            command=self._on_install_click,
        )

        self._release_page_btn = ctk.CTkButton(
            update_btn_frame,
            text="릴리즈 페이지",
            width=110,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self._open_release_page,
        )
        row += 1

        self._update_status = ctk.CTkLabel(
            scroll, text=f"현재 버전: v{__version__}", font=fm.font(12), text_color="gray"
        )
        self._update_status.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 8))

    # ──────────────────────────────────────────
    # 헬퍼
    # ──────────────────────────────────────────

    def _section_label(self, parent, text: str, row: int):
        ctk.CTkLabel(
            parent, text=text, font=fm.font(14, "bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(16, 6))

    # ──────────────────────────────────────────
    # UI 크기
    # ──────────────────────────────────────────

    def _on_scale_change(self, label: str):
        from src.ui import font_manager
        scale = self._scale_options[label]
        self._config.ui_scale = scale
        font_manager.apply_scale(scale)
        self._scale_status.configure(text="적용됨!")

    # ──────────────────────────────────────────
    # 선수 데이터 동기화
    # ──────────────────────────────────────────

    def _sync_meta(self):
        from src.api import nexon_api
        self._sync_btn.configure(state="disabled", text="동기화 중...")
        self._sync_status.configure(text="서버에서 최신 데이터를 받아오는 중...", text_color="gray")

        def _worker():
            try:
                result = nexon_api.sync_meta(self._config.backup_path)
                self.after(0, lambda r=result: self._on_sync_complete(r))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_sync_error(m))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_sync_complete(self, result: dict):
        spid_count = result.get("spid", 0)
        season_count = result.get("seasons", 0)
        self._sync_btn.configure(state="normal", text="데이터 동기화")
        self._sync_status.configure(
            text=f"완료 — 선수 {spid_count:,}명 / 시즌 {season_count}개",
            text_color="#4CAF50",
        )
        if self._on_sync_done:
            self._on_sync_done()

    def _on_sync_error(self, msg: str):
        self._sync_btn.configure(state="normal", text="데이터 동기화")
        self._sync_status.configure(text=f"실패: {msg}", text_color="#F44336")

    # ──────────────────────────────────────────
    # FC온라인 경로
    # ──────────────────────────────────────────

    def _browse_fc_path(self):
        path = filedialog.askdirectory(title="FC온라인 설치 폴더 선택")
        if path:
            self._fc_path_entry.delete(0, "end")
            self._fc_path_entry.insert(0, path)

    def _save_fc_path(self):
        path = self._fc_path_entry.get().strip()
        self._config.fc_online_path = path
        self._validate_fc_path()

    def _validate_fc_path(self):
        if self._config.is_fc_path_valid():
            self._fc_path_status.configure(text="경로 확인됨", text_color="#4CAF50")
        else:
            self._fc_path_status.configure(text="경로를 찾을 수 없음", text_color="#F44336")

    # ──────────────────────────────────────────
    # 백업
    # ──────────────────────────────────────────

    def _toggle_backup(self):
        self._config.backup_enabled = bool(self._backup_switch.get())

    def _browse_backup_path(self):
        path = filedialog.askdirectory(title="백업 저장 폴더 선택")
        if path:
            self._backup_path_entry.delete(0, "end")
            self._backup_path_entry.insert(0, path)

    def _save_backup_path(self):
        path = self._backup_path_entry.get().strip()
        self._config.backup_path = path
        messagebox.showinfo("저장 완료", f"백업 경로가 저장됐습니다.\n{path}")

    # ──────────────────────────────────────────
    # 업데이트
    # ──────────────────────────────────────────

    def _toggle_update_check(self):
        self._config.check_update_on_start = bool(self._update_switch.get())

    def _check_update(self):
        self._check_btn.configure(state="disabled", text="확인 중...")
        self._update_status.configure(text="GitHub에서 확인 중...", text_color="gray")
        self._install_btn.pack_forget()
        self._release_page_btn.pack_forget()

        def _worker():
            result = updater.check_for_update()
            self.after(0, lambda: self._on_update_result(result))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_update_result(self, result):
        self._check_btn.configure(state="normal", text="업데이트 확인")

        if result:
            self._update_result = result
            version = result["version"]
            has_download = bool(result.get("download_url")) and updater.IS_FROZEN

            self._update_status.configure(
                text=f"새 버전 {version}이(가) 있습니다!", text_color="#FF9800"
            )
            if has_download:
                self._install_btn.pack(side="left", padx=(0, 8))
            self._release_page_btn.pack(side="left")
        else:
            self._update_result = {}
            self._update_status.configure(
                text=f"최신 버전입니다. (v{__version__})", text_color="#4CAF50"
            )

    def _on_install_click(self):
        """설치 버튼 클릭 → App에 위임 (App이 오버레이 + 다운로드 처리)."""
        download_url = self._update_result.get("download_url", "")
        if download_url:
            self._update_status.configure(text="다운로드 준비 중...", text_color="gray")
            self._on_install(download_url)

    def on_download_error(self, msg: str):
        """App에서 다운로드 실패 시 호출."""
        self._install_btn.configure(state="normal")
        self._update_status.configure(text=f"다운로드 실패: {msg}", text_color="#F44336")

    def _open_release_page(self):
        url = self._update_result.get("url", "")
        if url:
            updater.open_release_page(url)
