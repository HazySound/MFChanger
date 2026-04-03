"""설정 화면 프레임"""

import threading
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from src.core.config import Config
from src.core import updater
from version import __version__


class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master, config: Config, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._config = config
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

        self._fc_path_status = ctk.CTkLabel(scroll, text="", font=ctk.CTkFont(size=11))
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

        ctk.CTkLabel(scroll, text="백업 저장 위치", font=ctk.CTkFont(size=12)).grid(
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

        update_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        update_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 4))

        self._update_btn = ctk.CTkButton(
            update_frame, text="업데이트 확인", width=120, command=self._check_update
        )
        self._update_btn.pack(side="left", padx=(0, 12))

        self._update_status = ctk.CTkLabel(
            update_frame, text=f"현재 버전: v{__version__}", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self._update_status.pack(side="left")
        row += 1

    # ──────────────────────────────────────────
    # 헬퍼
    # ──────────────────────────────────────────

    def _section_label(self, parent, text: str, row: int):
        ctk.CTkLabel(
            parent, text=text, font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(16, 6))

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
        self._update_btn.configure(state="disabled", text="확인 중...")
        self._update_status.configure(text="GitHub에서 확인 중...", text_color="gray")

        def _worker():
            result = updater.check_for_update()
            self.after(0, lambda: self._on_update_result(result))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_update_result(self, result):
        self._update_btn.configure(state="normal", text="업데이트 확인")
        if result:
            version = result["version"]
            url = result["url"]
            self._update_status.configure(
                text=f"새 버전 있음: {version}", text_color="#FF9800"
            )
            if messagebox.askyesno(
                "업데이트 가능",
                f"새 버전 {version}이(가) 있습니다.\n다운로드 페이지를 열까요?"
            ):
                updater.open_release_page(url)
        else:
            self._update_status.configure(
                text=f"최신 버전입니다. (v{__version__})", text_color="#4CAF50"
            )
