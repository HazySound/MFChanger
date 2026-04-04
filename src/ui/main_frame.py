"""메인 화면 프레임"""

import subprocess
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk
from PIL import Image

from src.api import nexon_api
from src.core.config import Config
from src.core import face_changer, history
from src.ui.components.image_preview import ImagePreview
from src.ui.components.player_list import PlayerSearchPanel


class MainFrame(ctk.CTkFrame):
    def __init__(self, master, config: Config, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._config = config
        self._selected_player: Optional[dict] = None
        self._selected_image_path: Optional[Path] = None
        self._loading_image = False
        self._preview_mode = "공식 미페"   # "공식 미페" | "현재 미페"

        self._build()
        self._load_meta_data()

    # ──────────────────────────────────────────
    # 레이아웃 구성
    # ──────────────────────────────────────────

    def _build(self):
        self.columnconfigure(0, weight=1, minsize=280)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        self._search_panel = PlayerSearchPanel(self, on_select=self._on_player_selected)
        self._search_panel.grid(row=0, column=0, sticky="nsew", padx=(10, 4), pady=10)

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 10), pady=10)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(2, weight=0)
        right.columnconfigure(0, weight=1)

        self._build_preview_area(right)
        self._build_image_select_area(right)
        self._build_action_area(right)

    def _build_preview_area(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        # 미페 미리보기 (토글 포함)
        preview_wrap = ctk.CTkFrame(frame, fg_color="transparent")
        preview_wrap.grid(row=0, column=0, padx=(20, 8), pady=10)

        # 토글 버튼 (공식 / 현재)
        self._preview_toggle = ctk.CTkSegmentedButton(
            preview_wrap,
            values=["공식 미페", "현재 미페"],
            command=self._on_preview_toggle,
            font=ctk.CTkFont(size=11),
            height=26,
        )
        self._preview_toggle.set("공식 미페")
        self._preview_toggle.pack(pady=(0, 4))

        self._preview_current = ImagePreview(preview_wrap, size=160, label_text="")
        self._preview_current.pack()

        # 선수 정보 + 탐색기 버튼
        info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        info_frame.grid(row=0, column=1, padx=(8, 20), pady=10, sticky="nsew")

        self._player_name_label = ctk.CTkLabel(
            info_frame, text="선수를 선택하세요", font=ctk.CTkFont(size=16, weight="bold")
        )
        self._player_name_label.pack(anchor="w", pady=(16, 4))

        self._player_spid_label = ctk.CTkLabel(
            info_frame, text="", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self._player_spid_label.pack(anchor="w")

        self._player_season_label = ctk.CTkLabel(
            info_frame, text="", font=ctk.CTkFont(size=12), text_color="gray"
        )
        self._player_season_label.pack(anchor="w", pady=(2, 0))

        self._player_status_label = ctk.CTkLabel(
            info_frame, text="", font=ctk.CTkFont(size=11), text_color="#FF9800"
        )
        self._player_status_label.pack(anchor="w", pady=(6, 0))

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

    def _build_image_select_area(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.grid(row=1, column=0, sticky="nsew", pady=(4, 4))
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        self._preview_new = ImagePreview(frame, size=160, label_text="교체할 이미지")
        self._preview_new.grid(row=0, column=0, padx=(20, 8), pady=10)
        self._preview_new.enable_drop(self._set_image)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.grid(row=0, column=1, padx=(8, 20), pady=10, sticky="nsew")

        select_btn = ctk.CTkButton(
            btn_frame,
            text="이미지 파일 선택",
            height=40,
            command=self._select_image,
        )
        select_btn.pack(anchor="w", pady=(16, 8))

        self._image_info_label = ctk.CTkLabel(
            btn_frame, text="JPG, PNG, BMP, WEBP 지원", font=ctk.CTkFont(size=11), text_color="gray"
        )
        self._image_info_label.pack(anchor="w")

        self._image_warn_label = ctk.CTkLabel(
            btn_frame, text="", font=ctk.CTkFont(size=11), text_color="#FF9800"
        )
        self._image_warn_label.pack(anchor="w", pady=(4, 0))

        frame.bind("<Control-v>", self._paste_image)

    def _build_action_area(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        frame.columnconfigure(0, weight=1)

        self._apply_btn = ctk.CTkButton(
            frame,
            text="미페 교체 실행",
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
    # 데이터 로딩
    # ──────────────────────────────────────────

    def _load_meta_data(self):
        self._search_panel.set_loading(True)

        def _worker():
            try:
                spid_list = nexon_api.fetch_spid_meta()
                seasons = nexon_api.fetch_season_meta()
                season_map = nexon_api.build_season_map(seasons)
                # 뱃지 이미지 백그라운드 프리패치
                nexon_api.prefetch_season_badges(seasons)
                self.after(0, lambda: self._on_meta_loaded(spid_list, seasons, season_map))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._search_panel._status_label.configure(
                    text=f"데이터 로딩 실패: {m}"
                ))
            finally:
                self.after(0, lambda: self._search_panel.set_loading(False))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_meta_loaded(self, spid_list: list, seasons: list, season_map: dict):
        self._search_panel.set_spid_list(spid_list)
        self._search_panel.set_season_data(seasons, season_map)

    def reload_meta(self):
        """동기화 후 호출 — 캐시 재로드 후 현재 검색 결과 즉시 갱신."""
        self._search_panel.set_loading(True)

        def _worker():
            try:
                spid_list = nexon_api.fetch_spid_meta()
                seasons = nexon_api.fetch_season_meta()
                season_map = nexon_api.build_season_map(seasons)
                nexon_api.prefetch_season_badges(seasons)
                self.after(0, lambda: self._on_meta_reloaded(spid_list, seasons, season_map))
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._search_panel._status_label.configure(
                    text=f"데이터 로딩 실패: {m}"
                ))
            finally:
                self.after(0, lambda: self._search_panel.set_loading(False))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_meta_reloaded(self, spid_list: list, seasons: list, season_map: dict):
        self._on_meta_loaded(spid_list, seasons, season_map)
        self._search_panel._do_search()  # 현재 검색어/필터로 즉시 재검색

    # ──────────────────────────────────────────
    # 이벤트 핸들러
    # ──────────────────────────────────────────

    def _on_player_selected(self, player: dict):
        self._selected_player = player
        spid = player.get("id", 0)
        name = player.get("name", "알 수 없음")

        # 시즌명 조회
        season_id = nexon_api.get_season_id(spid)
        season_info = self._search_panel._season_map.get(season_id, {})
        season_name = season_info.get("shortName", f"시즌{season_id}")

        self._player_name_label.configure(text=name)
        self._player_spid_label.configure(text=f"SPID: p{spid}")
        self._player_season_label.configure(text=f"시즌: {season_name}")

        record = history.find_record(spid)
        if record:
            self._player_status_label.configure(text=f"변경됨: {record.changed_at}")
        else:
            self._player_status_label.configure(text="")

        self._open_folder_btn.configure(state="normal")
        self._update_apply_btn()
        self._preview_current.clear()
        self._load_player_image(spid)

    def _on_preview_toggle(self, mode: str):
        self._preview_mode = mode
        if self._selected_player:
            spid = self._selected_player.get("id", 0)
            self._load_player_image(spid)

    def _load_player_image(self, spid: int):
        if self._loading_image:
            return
        self._loading_image = True
        self._preview_current.clear()

        if self._preview_mode == "현재 미페":
            # 로컬 파일에서 로드
            local_file = self._config.face_dir / f"p{spid}.png"
            if local_file.exists():
                self._preview_current.set_from_path(local_file)
            else:
                self._preview_current.set_image(None)
                self._preview_current.set_label("로컬 파일 없음")
            self._loading_image = False
        else:
            # CDN에서 로드
            def _worker():
                img = nexon_api.get_player_image(spid)
                self.after(0, lambda: self._on_image_loaded(img))
            threading.Thread(target=_worker, daemon=True).start()

    def _on_image_loaded(self, img: Optional[Image.Image]):
        self._loading_image = False
        self._preview_current.set_image(img)

    def _open_file_location(self):
        if not self._selected_player:
            return
        spid = self._selected_player.get("id", 0)

        if self._preview_mode == "현재 미페":
            # 현재 미페 모드: 게임의 playersAction 로컬 파일
            target = self._config.face_dir / f"p{spid}.png"
            if target.exists():
                subprocess.Popen(f'explorer /select,"{target}"')
            elif self._config.face_dir.exists():
                subprocess.Popen(f'explorer "{self._config.face_dir}"')
            else:
                messagebox.showwarning("경로 없음", f"미페 폴더를 찾을 수 없습니다.\n{self._config.face_dir}")
        else:
            # 공식 미페 모드: 실제 이미지를 로드한 CDN 경로 기준
            source = nexon_api.get_image_source(spid)
            if source:
                local_file = self._config.assets_dir / source
                if local_file.exists():
                    subprocess.Popen(f'explorer /select,"{local_file}"')
                    return
                folder = local_file.parent
                if folder.exists():
                    subprocess.Popen(f'explorer "{folder}"')
                    return
            # 소스 정보 없거나 로컬에 없으면 playersAction 폴더로 폴백
            face_dir = self._config.face_dir
            if face_dir.exists():
                subprocess.Popen(f'explorer "{face_dir}"')
            else:
                messagebox.showwarning("경로 없음", f"미페 폴더를 찾을 수 없습니다.\n{face_dir}")

    def _select_image(self):
        path_str = filedialog.askopenfilename(
            title="교체할 이미지 선택",
            filetypes=[
                ("이미지 파일", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("모든 파일", "*.*"),
            ],
        )
        if path_str:
            self._set_image(Path(path_str))

    def _set_image(self, path: Path):
        self._selected_image_path = path
        self._preview_new.set_from_path(path)

        size = face_changer.get_image_size(path)
        if size:
            w, h = size
            self._image_info_label.configure(text=f"{w} × {h} px")
            if w != h:
                self._image_warn_label.configure(text="비정방형 이미지 - 교체 시 중앙 크롭됩니다.")
            else:
                self._image_warn_label.configure(text="")
        self._update_apply_btn()

    def _paste_image(self, _event=None):
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                tmp = Path.cwd() / ".cache" / "_clipboard.png"
                tmp.parent.mkdir(exist_ok=True)
                img.save(tmp, "PNG")
                self._set_image(tmp)
        except Exception:
            pass

    def _update_apply_btn(self):
        if self._selected_player and self._selected_image_path:
            self._apply_btn.configure(state="normal")
        else:
            self._apply_btn.configure(state="disabled")

    def _apply_change(self):
        if not self._selected_player or not self._selected_image_path:
            return

        spid = self._selected_player.get("id", 0)
        name = self._selected_player.get("name", "")

        if not self._config.is_fc_path_valid():
            messagebox.showerror(
                "경로 오류",
                f"FC온라인 미페 폴더를 찾을 수 없습니다.\n"
                f"설정에서 설치 경로를 확인해주세요.\n\n"
                f"현재 경로: {self._config.face_dir}"
            )
            return

        self._apply_btn.configure(state="disabled", text="처리 중...")
        self._result_label.configure(text="")

        def _worker():
            try:
                record = face_changer.replace_face(
                    spid=spid,
                    player_name=name,
                    src_image_path=self._selected_image_path,
                    config=self._config,
                )
                history.add_record(record)
                self.after(0, self._on_change_success)
            except Exception as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_change_error(m))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_change_success(self):
        self._apply_btn.configure(state="normal", text="미페 교체 실행")
        self._result_label.configure(text="미페 교체 완료!", text_color="#4CAF50")
        if self._selected_player:
            spid = self._selected_player.get("id", 0)
            record = history.find_record(spid)
            if record:
                self._player_status_label.configure(text=f"변경됨: {record.changed_at}")

    def _on_change_error(self, msg: str):
        self._apply_btn.configure(state="normal", text="미페 교체 실행")
        self._result_label.configure(text=f"오류: {msg}", text_color="#F44336")
        messagebox.showerror("교체 실패", msg)
