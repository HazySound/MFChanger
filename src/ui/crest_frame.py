"""크레스트 변경 화면 프레임"""

import subprocess
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk
from PIL import Image

from src.core.config import Config
from src.core import crest_changer
from src.ui.components.image_preview import ImagePreview


class CrestFrame(ctk.CTkFrame):
    def __init__(self, master, config: Config, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._config = config
        self._crest_id: Optional[int] = None
        self._selected_image_path: Optional[Path] = None

        self._build()

    # ──────────────────────────────────────────
    # 레이아웃 구성
    # ──────────────────────────────────────────

    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        self._build_current_area()
        self._build_new_image_area()
        self._build_action_area()

    def _build_current_area(self):
        """상단: 크레스트 ID 입력 + 현재 크레스트 미리보기"""
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 4))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        # 현재 크레스트 미리보기 (dark/large)
        self._preview_current = ImagePreview(frame, size=160, label_text="현재 크레스트 (dark/large)")
        self._preview_current.grid(row=0, column=0, padx=(20, 8), pady=10)

        # 우측 정보 영역
        info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        info_frame.grid(row=0, column=1, padx=(8, 20), pady=10, sticky="nsew")

        ctk.CTkLabel(
            info_frame,
            text="크레스트 ID",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(16, 6))

        # ID 입력 행
        id_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        id_row.pack(anchor="w")

        self._id_entry = ctk.CTkEntry(
            id_row,
            placeholder_text="숫자 ID 입력",
            width=140,
            height=36,
        )
        self._id_entry.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            id_row,
            text="미리보기",
            width=80,
            height=36,
            command=self._load_current_preview,
        ).pack(side="left")

        self._id_info_label = ctk.CTkLabel(
            info_frame,
            text="이미지를 선택하면 파일명에서 자동으로 ID를 인식합니다.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=240,
            justify="left",
        )
        self._id_info_label.pack(anchor="w", pady=(8, 0))

        self._current_status_label = ctk.CTkLabel(
            info_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#FF9800",
        )
        self._current_status_label.pack(anchor="w", pady=(6, 0))

        # 파일 위치 열기 버튼
        self._open_folder_btn = ctk.CTkButton(
            info_frame,
            text="파일 위치 열기",
            width=120,
            height=32,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            text_color=("gray10", "gray90"),
            command=self._open_file_location,
            state="disabled",
        )
        self._open_folder_btn.pack(anchor="w", pady=(14, 0))

    def _build_new_image_area(self):
        """중단: 교체할 이미지 선택"""
        frame = ctk.CTkFrame(self)
        frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(4, 4))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        self._preview_new = ImagePreview(frame, size=160, label_text="교체할 이미지")
        self._preview_new.grid(row=0, column=0, padx=(20, 8), pady=10)
        self._preview_new.enable_drop(self._handle_image_path)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, padx=(8, 20), pady=10, sticky="nsew")

        ctk.CTkButton(
            btn_frame,
            text="이미지 파일 선택",
            height=40,
            command=self._select_image,
        ).pack(anchor="w", pady=(16, 8))

        self._image_info_label = ctk.CTkLabel(
            btn_frame,
            text="JPG, PNG, BMP, WEBP 지원\n파일명이 숫자면 ID로 자동 인식됩니다.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left",
        )
        self._image_info_label.pack(anchor="w")

        self._image_warn_label = ctk.CTkLabel(
            btn_frame, text="", font=ctk.CTkFont(size=11), text_color="#FF9800"
        )
        self._image_warn_label.pack(anchor="w", pady=(4, 0))

        ctk.CTkLabel(
            btn_frame,
            text="교체 시 dark/light × large/medium/small\n총 6개 파일이 자동으로 생성됩니다.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            justify="left",
        ).pack(anchor="w", pady=(12, 0))

    def _build_action_area(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 0))
        frame.columnconfigure(0, weight=1)

        self._apply_btn = ctk.CTkButton(
            frame,
            text="크레스트 교체 실행",
            height=48,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2196F3",
            hover_color="#1976D2",
            command=self._apply_change,
            state="disabled",
        )
        self._apply_btn.grid(row=0, column=0, padx=10, pady=8, sticky="ew")

        self._result_label = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=12))
        self._result_label.grid(row=1, column=0, padx=10)

    # ──────────────────────────────────────────
    # 이벤트 핸들러
    # ──────────────────────────────────────────

    def _select_image(self):
        path_str = filedialog.askopenfilename(
            title="교체할 크레스트 이미지 선택",
            filetypes=[
                ("이미지 파일", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("모든 파일", "*.*"),
            ],
        )
        if path_str:
            self._handle_image_path(Path(path_str))

    def _handle_image_path(self, path: Path):
        """선택/드롭된 이미지 경로 처리 (공통 로직)."""
        self._selected_image_path = path
        self._preview_new.set_from_path(path)

        # 파일명에서 ID 자동 인식
        stem = path.stem
        if stem.isdigit():
            self._id_entry.delete(0, "end")
            self._id_entry.insert(0, stem)
            self._crest_id = int(stem)
            self._load_current_preview()

        # 이미지 크기 표시
        try:
            with Image.open(path) as img:
                w, h = img.size
            self._image_info_label.configure(text=f"{w} × {h} px")
            if w != h:
                self._image_warn_label.configure(text="비정방형 이미지 - 교체 시 중앙 크롭됩니다.")
            else:
                self._image_warn_label.configure(text="")
        except Exception:
            pass

        self._update_apply_btn()

    def _load_current_preview(self):
        """ID 입력 기반으로 현재 dark/large 크레스트 미리보기 로드."""
        id_text = self._id_entry.get().strip()
        if not id_text.isdigit():
            self._current_status_label.configure(text="숫자 ID를 입력해주세요.")
            return

        crest_id = int(id_text)
        self._crest_id = crest_id

        if not self._config.is_crest_path_valid():
            self._current_status_label.configure(text="크레스트 폴더를 찾을 수 없습니다.")
            self._preview_current.clear()
            return

        def _worker():
            img = crest_changer.load_crest_image(self._config.crest_dir, crest_id)
            self.after(0, lambda: self._on_current_loaded(img, crest_id))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_current_loaded(self, img: Optional[Image.Image], crest_id: int):
        self._preview_current.set_image(img)
        if img is None:
            self._current_status_label.configure(
                text=f"dark/large/d{crest_id}.png 파일이 없습니다."
            )
        else:
            self._current_status_label.configure(text="")
            self._open_folder_btn.configure(state="normal")
        self._update_apply_btn()

    def _open_file_location(self):
        if self._crest_id is None:
            return
        crest_file = crest_changer.get_crest_file(
            self._config.crest_dir, "dark", "large", self._crest_id
        )
        if crest_file.exists():
            subprocess.Popen(f'explorer /select,"{crest_file}"')
        else:
            dark_large = self._config.crest_dir / "dark" / "large"
            if dark_large.exists():
                subprocess.Popen(f'explorer "{dark_large}"')

    def _update_apply_btn(self):
        if self._crest_id is not None and self._selected_image_path:
            self._apply_btn.configure(state="normal")
        else:
            self._apply_btn.configure(state="disabled")

    def _apply_change(self):
        if self._crest_id is None or not self._selected_image_path:
            return

        if not self._config.is_crest_path_valid():
            messagebox.showerror(
                "경로 오류",
                f"FC온라인 크레스트 폴더를 찾을 수 없습니다.\n"
                f"설정에서 설치 경로를 확인해주세요.\n\n"
                f"현재 경로: {self._config.crest_dir}"
            )
            return

        crest_id = self._crest_id
        self._apply_btn.configure(state="disabled", text="처리 중...")
        self._result_label.configure(text="")

        def _worker():
            try:
                record = crest_changer.replace_crest(
                    crest_id=crest_id,
                    src_image_path=self._selected_image_path,
                    config=self._config,
                )
                self.after(0, lambda r=record: self._on_change_success(crest_id, r))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_change_error(m))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_change_success(self, crest_id: int, record):
        from src.core import history as hist
        hist.add_crest_record(record)

        self._apply_btn.configure(state="normal", text="크레스트 교체 실행")
        self._result_label.configure(text="크레스트 교체 완료!", text_color="#4CAF50")

        # 미리보기 갱신 (dark/large)
        def _reload():
            img = crest_changer.load_crest_image(self._config.crest_dir, crest_id)
            self.after(0, lambda: self._preview_current.set_image(img))

        threading.Thread(target=_reload, daemon=True).start()

    def _on_change_error(self, msg: str):
        self._apply_btn.configure(state="normal", text="크레스트 교체 실행")
        self._result_label.configure(text=f"오류: {msg}", text_color="#F44336")
        messagebox.showerror("교체 실패", msg)
