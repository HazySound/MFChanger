"""감독 얼굴 변경 화면 프레임"""

import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk
from PIL import Image

from src.core.config import Config
from src.core import manager_changer
from src.core.manager_db import ensure_db, search
from src.core.history import add_manager_record, find_manager_record
from src.ui.components.image_preview import ImagePreview
from src.ui import font_manager as fm

THUMB_SIZE = 44
_thumb_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="mgr_thumb")


class ManagerFrame(ctk.CTkFrame):
    def __init__(self, master, config: Config, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._config = config
        self._db: dict = {}
        self._selected_id: Optional[str] = None
        self._selected_name: str = ""
        self._selected_team: str = ""
        self._selected_image_path: Optional[Path] = None
        self._preview_mode = "현재 얼굴"
        self._render_gen = 0  # 검색 세대 — 이전 결과의 썸네일 콜백 무시용
        self._thumb_labels: dict[str, ctk.CTkLabel] = {}  # manager_id → 썸네일 레이블

        self._build()
        threading.Thread(target=self._load_db, daemon=True).start()

    # ──────────────────────────────────────────
    # 레이아웃
    # ──────────────────────────────────────────

    def _build(self):
        self.columnconfigure(0, weight=1, minsize=260)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        self._build_search_panel()
        self._build_right_panel()

    def _build_search_panel(self):
        panel = ctk.CTkFrame(self)
        panel.grid(row=0, column=0, sticky="nsew", padx=(10, 4), pady=10)
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)

        # 검색 입력 + 버튼
        search_row = ctk.CTkFrame(panel, fg_color="transparent")
        search_row.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        search_row.columnconfigure(0, weight=1)

        self._search_var = ctk.StringVar()
        self._search_entry = ctk.CTkEntry(
            search_row,
            textvariable=self._search_var,
            placeholder_text="감독 이름 또는 팀명...",
            height=36,
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._search_entry.bind("<Return>", lambda _: self._do_search())

        self._search_btn = ctk.CTkButton(
            search_row,
            text="검색",
            width=52,
            height=36,
            font=fm.font(12),
            command=self._do_search,
        )
        self._search_btn.grid(row=0, column=1)

        self._status_label = ctk.CTkLabel(
            panel, text="DB 로딩 중...", font=fm.font(11), text_color="gray"
        )
        self._status_label.grid(row=2, column=0, pady=(0, 6))

        # 결과 목록
        self._scroll = ctk.CTkScrollableFrame(panel, label_text="")
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 0))
        self._scroll.columnconfigure(0, weight=1)

    def _build_right_panel(self):
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 10), pady=10)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(2, weight=0)
        right.columnconfigure(0, weight=1)

        self._build_current_area(right)
        self._build_new_image_area(right)
        self._build_action_area(right)

    def _build_current_area(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        # 토글 + 미리보기 (main_frame과 동일한 구조)
        preview_wrap = ctk.CTkFrame(frame, fg_color="transparent")
        preview_wrap.grid(row=0, column=0, padx=(20, 8), pady=10)

        self._preview_toggle = ctk.CTkSegmentedButton(
            preview_wrap,
            values=["현재 얼굴", "공식 얼굴"],
            command=self._on_preview_toggle,
            font=fm.font(11),
            height=26,
        )
        self._preview_toggle.set("현재 얼굴")
        self._preview_toggle.pack(pady=(0, 4))

        self._preview_current = ImagePreview(preview_wrap, size=160, label_text="")
        self._preview_current.pack()

        # 감독 정보 + 버튼
        info = ctk.CTkFrame(frame, fg_color="transparent")
        info.grid(row=0, column=1, padx=(8, 20), pady=10, sticky="nsew")

        self._name_label = ctk.CTkLabel(
            info, text="감독을 선택하세요", font=fm.font(16, "bold")
        )
        self._name_label.pack(anchor="w", pady=(16, 4))

        self._team_label = ctk.CTkLabel(info, text="", font=fm.font(12), text_color="gray")
        self._team_label.pack(anchor="w")

        self._id_label = ctk.CTkLabel(info, text="", font=fm.font(11), text_color="gray")
        self._id_label.pack(anchor="w", pady=(2, 0))

        self._changed_label = ctk.CTkLabel(
            info, text="", font=fm.font(11), text_color="#FF9800"
        )
        self._changed_label.pack(anchor="w", pady=(6, 0))

        self._open_folder_btn = ctk.CTkButton(
            info,
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

        self._restore_btn = ctk.CTkButton(
            info,
            text="공식 얼굴로 복원",
            width=120,
            height=32,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            text_color=("gray10", "gray90"),
            command=self._restore_to_official,
            state="disabled",
        )
        self._restore_btn.pack(anchor="w", pady=(6, 0))

    def _build_new_image_area(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.grid(row=1, column=0, sticky="nsew", pady=(4, 4))
        frame.columnconfigure(1, weight=1)

        self._preview_new = ImagePreview(frame, size=160, label_text="교체할 이미지")
        self._preview_new.grid(row=0, column=0, padx=(20, 8), pady=10)
        self._preview_new.enable_drop(self._set_image)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, padx=(8, 20), pady=10, sticky="nsew")

        ctk.CTkButton(
            btn_frame, text="이미지 파일 선택", height=40, command=self._select_image,
        ).pack(anchor="w", pady=(16, 8))

        self._image_info_label = ctk.CTkLabel(
            btn_frame, text="JPG, PNG, BMP, WEBP 지원", font=fm.font(11), text_color="gray"
        )
        self._image_info_label.pack(anchor="w")

        self._image_warn_label = ctk.CTkLabel(
            btn_frame, text="", font=fm.font(11), text_color="#FF9800"
        )
        self._image_warn_label.pack(anchor="w", pady=(4, 0))

    def _build_action_area(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        frame.columnconfigure(0, weight=1)

        self._apply_btn = ctk.CTkButton(
            frame,
            text="감독 얼굴 교체 실행",
            height=48,
            font=fm.font(15, "bold"),
            fg_color="#2196F3",
            hover_color="#1976D2",
            command=self._apply_change,
            state="disabled",
        )
        self._apply_btn.grid(row=0, column=0, padx=10, pady=8, sticky="ew")

        self._result_label = ctk.CTkLabel(frame, text="", font=fm.font(12))
        self._result_label.grid(row=1, column=0, padx=10)

    # ──────────────────────────────────────────
    # DB 로딩 & 검색
    # ──────────────────────────────────────────

    def _load_db(self):
        try:
            db = ensure_db()
            self.after(0, lambda: self._on_db_loaded(db))
        except Exception as e:
            msg = str(e)
            self.after(0, lambda m=msg: self._status_label.configure(
                text=f"DB 로딩 실패: {m}", text_color="#F44336"
            ))

    def _on_db_loaded(self, db: dict):
        self._db = db
        self._status_label.configure(
            text=f"감독 이름 또는 팀명을 입력하세요. (총 {len(db)}명)", text_color="gray"
        )
        self._search_entry.configure(state="normal")
        self._search_btn.configure(state="normal")

    def _do_search(self):
        if not self._db:
            return
        q = self._search_var.get().strip()
        if not q:
            self._clear_list()
            self._status_label.configure(
                text=f"감독 이름 또는 팀명을 입력하세요. (총 {len(self._db)}명)", text_color="gray"
            )
            return

        results = search(q, self._db)
        shown = results[:100]
        self._render_list(shown)

        total = len(results)
        suffix = f" (상위 100개 표시)" if total > 100 else ""
        self._status_label.configure(
            text=f"{total}명 검색됨{suffix}" if total else "검색 결과가 없습니다.",
            text_color="gray",
        )

    def _clear_list(self):
        self._render_gen += 1
        for w in self._scroll.winfo_children():
            w.destroy()

    def _render_list(self, results: list[tuple[str, str, str]]):
        self._render_gen += 1
        gen = self._render_gen
        self._thumb_labels.clear()

        for w in self._scroll.winfo_children():
            w.destroy()

        for mid, name, team in results:
            item = ctk.CTkFrame(self._scroll, fg_color="transparent", cursor="hand2", corner_radius=6)
            item.grid(sticky="ew", pady=1)
            item.columnconfigure(1, weight=1)

            # 썸네일 (빈 자리 먼저 표시)
            thumb_lbl = ctk.CTkLabel(item, text="", width=THUMB_SIZE, height=THUMB_SIZE)
            thumb_lbl.grid(row=0, column=0, rowspan=2, padx=(6, 4), pady=4)

            name_lbl = ctk.CTkLabel(item, text=name, font=fm.font(12, "bold"), anchor="w")
            name_lbl.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(4, 0))
            team_lbl = ctk.CTkLabel(item, text=team, font=fm.font(10), text_color="gray", anchor="w")
            team_lbl.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 4))

            for w in (item, thumb_lbl, name_lbl, team_lbl):
                w.bind("<Button-1>", lambda e, m=mid, n=name, t=team: self._select_manager(m, n, t))
                w.bind("<Enter>", lambda e, f=item: f.configure(fg_color=("gray85", "gray25")))
                w.bind("<Leave>", lambda e, f=item: f.configure(fg_color="transparent"))

            self._thumb_labels[mid] = thumb_lbl
            # 썸네일을 풀에서 비동기 로드
            _thumb_pool.submit(self._load_thumb, mid, thumb_lbl, gen)

    def _load_thumb(self, manager_id: str, label: ctk.CTkLabel, gen: int):
        if gen != self._render_gen:
            return
        img = manager_changer.load_manager_image(self._config, manager_id)
        if img is None:
            img = manager_changer.load_generic_image(self._config)
        if img is None or gen != self._render_gen:
            return
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(THUMB_SIZE, THUMB_SIZE))

        def _apply():
            if gen == self._render_gen and label.winfo_exists():
                label.configure(image=ctk_img)
                label._thumb_ref = ctk_img  # GC 방지
        self.after(0, _apply)

    def _reload_thumb(self, manager_id: str):
        """변경/복원 후 특정 감독의 썸네일만 갱신."""
        label = self._thumb_labels.get(manager_id)
        if label is None:
            return
        _thumb_pool.submit(self._load_thumb, manager_id, label, self._render_gen)

    def refresh_manager(self, manager_id: str):
        """이력 탭 등 외부에서 호출 — 썸네일 + 미리보기 갱신."""
        self._reload_thumb(manager_id)
        if self._selected_id == manager_id:
            self._refresh_preview(manager_id)

    # ──────────────────────────────────────────
    # 감독 선택
    # ──────────────────────────────────────────

    def _select_manager(self, manager_id: str, name: str, team: str):
        self._selected_id = manager_id
        self._selected_name = name
        self._selected_team = team
        self._name_label.configure(text=name)
        self._team_label.configure(text=team)
        self._id_label.configure(text=f"ID: heads_staff_{manager_id}.png")
        self._open_folder_btn.configure(state="normal")
        self._restore_btn.configure(state="normal")
        self._result_label.configure(text="")

        record = find_manager_record(manager_id)
        self._changed_label.configure(
            text=f"변경됨: {record.changed_at}" if record else ""
        )

        self._update_apply_btn()
        self._refresh_preview(manager_id)

    def _on_preview_toggle(self, mode: str):
        self._preview_mode = mode
        if self._selected_id:
            self._refresh_preview(self._selected_id)

    def _refresh_preview(self, manager_id: str):
        self._preview_current.clear()
        if self._preview_mode == "현재 얼굴":
            threading.Thread(target=lambda: self._load_current_preview(manager_id), daemon=True).start()
        else:
            threading.Thread(target=lambda: self._load_official_preview(manager_id), daemon=True).start()

    def _load_current_preview(self, manager_id: str):
        img = manager_changer.load_manager_image(self._config, manager_id)
        if img is None:
            img = manager_changer.load_generic_image(self._config)
        self.after(0, lambda: self._preview_current.set_image(img))

    def _load_official_preview(self, manager_id: str):
        img = manager_changer.fetch_official_image(manager_id)
        if img is None:
            img = manager_changer.load_generic_image(self._config)
        self.after(0, lambda: self._preview_current.set_image(img))

    # ──────────────────────────────────────────
    # 이미지 선택
    # ──────────────────────────────────────────

    def _select_image(self):
        path_str = filedialog.askopenfilename(
            title="교체할 감독 이미지 선택",
            filetypes=[("이미지 파일", "*.png *.jpg *.jpeg *.bmp *.webp"), ("모든 파일", "*.*")],
        )
        if path_str:
            self._set_image(Path(path_str))

    def _set_image(self, path: Path):
        self._selected_image_path = path
        self._preview_new.set_from_path(path)
        try:
            with Image.open(path) as img:
                w, h = img.size
            self._image_info_label.configure(text=f"{w} × {h} px")
            self._image_warn_label.configure(
                text="비정방형 이미지 - 교체 시 중앙 크롭됩니다." if w != h else ""
            )
        except Exception:
            pass
        self._update_apply_btn()

    # ──────────────────────────────────────────
    # 교체 실행
    # ──────────────────────────────────────────

    def _update_apply_btn(self):
        self._apply_btn.configure(
            state="normal" if (self._selected_id and self._selected_image_path) else "disabled"
        )

    def _apply_change(self):
        if not self._selected_id or not self._selected_image_path:
            return
        if not manager_changer.is_manager_dir_valid(self._config):
            messagebox.showerror(
                "경로 오류",
                f"감독 이미지 폴더를 찾을 수 없습니다.\n"
                f"설정에서 FC온라인 설치 경로를 확인해주세요.\n\n"
                f"현재 경로: {manager_changer.get_manager_dir(self._config)}"
            )
            return

        mid, name, team = self._selected_id, self._selected_name, self._selected_team
        self._apply_btn.configure(state="disabled", text="처리 중...")
        self._result_label.configure(text="")

        def _worker():
            try:
                record = manager_changer.replace_manager(
                    manager_id=mid,
                    manager_name=name,
                    team=team,
                    src_image_path=self._selected_image_path,
                    config=self._config,
                )
                add_manager_record(record)
                self.after(0, lambda: self._on_change_success(mid, record.changed_at))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_change_error(m))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_change_success(self, manager_id: str, changed_at: str):
        self._apply_btn.configure(state="normal", text="감독 얼굴 교체 실행")
        self._result_label.configure(text="감독 얼굴 교체 완료!", text_color="#4CAF50")
        self._changed_label.configure(text=f"변경됨: {changed_at}")
        self._reload_thumb(manager_id)
        self._refresh_preview(manager_id)

    def _restore_to_official(self):
        if not self._selected_id:
            return
        if not messagebox.askyesno(
            "공식 얼굴로 복원",
            f"'{self._selected_name}'의 얼굴을 공식 이미지로 복원하겠습니까?\n"
            "CDN에서 공식 이미지를 다운로드해 덮어씁니다.",
        ):
            return

        mid, name, team = self._selected_id, self._selected_name, self._selected_team
        self._restore_btn.configure(state="disabled", text="다운로드 중...")
        self._result_label.configure(text="")

        def _worker():
            try:
                record = manager_changer.restore_to_official(
                    manager_id=mid, manager_name=name, team=team, config=self._config
                )
                add_manager_record(record)
                self.after(0, lambda: self._on_restore_success(mid, record.changed_at))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_restore_error(m))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_restore_success(self, manager_id: str, changed_at: str):
        self._restore_btn.configure(state="normal", text="공식 얼굴로 복원")
        self._result_label.configure(text="공식 얼굴로 복원 완료!", text_color="#4CAF50")
        self._changed_label.configure(text=f"변경됨: {changed_at}")
        self._reload_thumb(manager_id)
        self._refresh_preview(manager_id)

    def _on_restore_error(self, msg: str):
        self._restore_btn.configure(state="normal", text="공식 얼굴로 복원")
        self._result_label.configure(text=f"오류: {msg}", text_color="#F44336")
        messagebox.showerror("복원 실패", msg)

    def _on_change_error(self, msg: str):
        self._apply_btn.configure(state="normal", text="감독 얼굴 교체 실행")
        self._result_label.configure(text=f"오류: {msg}", text_color="#F44336")
        messagebox.showerror("교체 실패", msg)

    def _open_file_location(self):
        if not self._selected_id:
            return
        target = manager_changer.get_manager_file(self._config, self._selected_id)
        if target.exists():
            subprocess.Popen(f'explorer /select,"{target}"')
        else:
            folder = target.parent
            if folder.exists():
                subprocess.Popen(f'explorer "{folder}"')
