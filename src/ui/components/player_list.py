"""선수 검색 결과 목록 위젯"""

import threading
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from src.ui.components.filter_panel import FilterDropdown

THUMB_SIZE = 48
BADGE_SIZE = 30

_BLANK_THUMB: Optional[ctk.CTkImage] = None
_BLANK_BADGE: Optional[ctk.CTkImage] = None


def _blank(size: int) -> ctk.CTkImage:
    px = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return ctk.CTkImage(light_image=px, dark_image=px, size=(size, size))


def _get_blank_thumb() -> ctk.CTkImage:
    global _BLANK_THUMB
    if _BLANK_THUMB is None:
        _BLANK_THUMB = _blank(THUMB_SIZE)
    return _BLANK_THUMB


def _get_blank_badge() -> ctk.CTkImage:
    global _BLANK_BADGE
    if _BLANK_BADGE is None:
        _BLANK_BADGE = _blank(BADGE_SIZE)
    return _BLANK_BADGE


class PlayerListItem(ctk.CTkFrame):
    def __init__(
        self,
        master,
        player: dict,
        season_info: dict,
        on_click: Callable,
        on_no_image: Callable,
        **kwargs,
    ):
        super().__init__(master, cursor="hand2", corner_radius=6, **kwargs)
        self._player = player
        self._on_click = on_click
        self._on_no_image = on_no_image
        self._selected = False
        self._destroyed = False

        spid = player.get("id", 0)
        name = player.get("name", "알 수 없음")

        self._thumb_label = ctk.CTkLabel(
            self, text="", image=_get_blank_thumb(), width=THUMB_SIZE, height=THUMB_SIZE
        )
        self._thumb_label.pack(side="left", padx=(6, 4), pady=6)

        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, pady=6)

        name_label = ctk.CTkLabel(
            text_frame, text=name, font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        )
        name_label.pack(anchor="w")

        # 시즌 뱃지만 표시 (시즌명/pid 텍스트 제거)
        season_row = ctk.CTkFrame(text_frame, fg_color="transparent")
        season_row.pack(anchor="w", pady=(1, 0))

        self._badge_label = ctk.CTkLabel(
            season_row, text="", image=_get_blank_badge(), width=BADGE_SIZE, height=BADGE_SIZE
        )
        self._badge_label.pack(side="left")

        for widget in (self, self._thumb_label, text_frame, name_label, season_row, self._badge_label):
            widget.bind("<Button-1>", self._click)
            widget.bind("<Enter>", self._hover_enter)
            widget.bind("<Leave>", self._hover_leave)

        season_id = season_info.get("seasonId", 0)
        season_img_url = season_info.get("seasonImg", "")

        threading.Thread(
            target=self._load_assets,
            args=(spid, season_id, season_img_url),
            daemon=True,
        ).start()

    def _load_assets(self, spid: int, season_id: int, season_img_url: str):
        from src.api.nexon_api import get_player_image, get_season_badge
        import threading as th

        player_img = [None]
        badge_img = [None]
        done = [0]

        def load_player():
            player_img[0] = get_player_image(spid)
            done[0] += 1
            if done[0] == 2:
                self._apply_assets(player_img[0], badge_img[0])

        def load_badge():
            badge_img[0] = get_season_badge(season_id, season_img_url)
            done[0] += 1
            if done[0] == 2:
                self._apply_assets(player_img[0], badge_img[0])

        th.Thread(target=load_player, daemon=True).start()
        th.Thread(target=load_badge, daemon=True).start()

    def _apply_assets(self, player_img, badge_img):
        if self._destroyed:
            return
        if player_img is None:
            self.after(0, self._on_no_image)
            return
        if player_img:
            ctk_thumb = ctk.CTkImage(
                light_image=player_img, dark_image=player_img, size=(THUMB_SIZE, THUMB_SIZE)
            )
            self.after(0, lambda i=ctk_thumb: self._set_thumb(i))
        if badge_img:
            ctk_badge = ctk.CTkImage(
                light_image=badge_img, dark_image=badge_img, size=(BADGE_SIZE, BADGE_SIZE)
            )
            self.after(0, lambda i=ctk_badge: self._set_badge(i))

    def _set_thumb(self, img: ctk.CTkImage):
        if not self._destroyed:
            try:
                self._thumb_label.configure(image=img)
                self._thumb_img = img
            except Exception:
                pass

    def _set_badge(self, img: ctk.CTkImage):
        if not self._destroyed:
            try:
                self._badge_label.configure(image=img)
                self._badge_img = img
            except Exception:
                pass

    def destroy(self):
        self._destroyed = True
        super().destroy()

    def _click(self, _event=None):
        self._on_click(self._player)

    def _hover_enter(self, _event=None):
        if not self._selected:
            self.configure(fg_color=("gray85", "gray25"))

    def _hover_leave(self, _event=None):
        if not self._selected:
            self.configure(fg_color="transparent")

    def set_selected(self, selected: bool):
        self._selected = selected
        self.configure(fg_color=("gray75", "gray30") if selected else "transparent")


class PlayerSearchPanel(ctk.CTkFrame):
    def __init__(self, master, on_select: Callable[[dict], None], **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._items: list[PlayerListItem] = []
        self._spid_list: list[dict] = []
        self._season_map: dict[int, dict] = {}
        self._seasons: list[dict] = []

        # 필터 상태: {category: set[year]} 또는 {"__season_ids__": set[int]}
        self._active_filters: dict = {}
        self._dropdown: Optional[FilterDropdown] = None

        self._build()

    def _build(self):
        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", padx=10, pady=(10, 4))
        search_row.columnconfigure(0, weight=1)

        self._search_var = ctk.StringVar()

        self._search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="선수 이름 검색...",
            textvariable=self._search_var,
            height=36,
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._search_entry.bind("<Return>", lambda _: self._do_search())

        self._search_btn = ctk.CTkButton(
            search_row,
            text="검색",
            width=52, height=36,
            font=ctk.CTkFont(size=12),
            command=self._do_search,
        )
        self._search_btn.grid(row=0, column=1, padx=(0, 6))

        self._filter_btn = ctk.CTkButton(
            search_row,
            text="필터 ▼",
            width=72, height=36,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            border_width=1,
            border_color=("gray65", "gray45"),
            text_color=("gray20", "gray90"),
            hover_color=("gray85", "gray30"),
            command=self._toggle_dropdown,
        )
        self._filter_btn.grid(row=0, column=2)

        self._status_label = ctk.CTkLabel(
            self, text="데이터 로딩 중...", font=ctk.CTkFont(size=11), text_color="gray"
        )
        self._status_label.pack(pady=2)

        self._scroll = ctk.CTkScrollableFrame(self, label_text="")
        self._scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ──────────────────────────────────────────
    # 드롭다운
    # ──────────────────────────────────────────

    def _toggle_dropdown(self):
        if self._dropdown and self._dropdown.winfo_exists():
            self._dropdown._close()
            return

        root = self.nametowidget(".")
        # 카테고리 필터만 복원 (season_ids는 드롭다운 내부 임시 상태)
        restore_filters = {
            cat: years
            for cat, years in self._active_filters.items()
            if cat != "__season_ids__"
        }
        self._dropdown = FilterDropdown(
            main_window=root,
            anchor=self._filter_btn,
            seasons=self._seasons,
            active_filters=restore_filters,
            on_change=self._on_filter_changed,
            on_close=self._on_dropdown_closed,
        )

    def _on_dropdown_closed(self):
        self._dropdown = None
        # season_ids 필터는 드롭다운 닫힐 때 해제 (임시)
        if "__season_ids__" in self._active_filters:
            self._active_filters = {
                cat: years
                for cat, years in self._active_filters.items()
                if cat != "__season_ids__"
            }
            self._do_search()
        self._update_filter_btn_style()

    def _on_filter_changed(self, active_filters: dict):
        self._active_filters = active_filters
        self._update_filter_btn_style()
        self._do_search()

    def _update_filter_btn_style(self):
        # season_ids 외 카테고리 필터가 있으면 활성
        cat_filters = {k: v for k, v in self._active_filters.items() if k != "__season_ids__"}
        active = bool(cat_filters)
        self._filter_btn.configure(
            text="필터 ●" if active else "필터 ▼",
            fg_color="#2196F3" if active else "transparent",
            text_color="white" if active else ("gray20", "gray90"),
            border_color="#2196F3" if active else ("gray65", "gray45"),
        )

    # ──────────────────────────────────────────
    # 검색
    # ──────────────────────────────────────────

    def _do_search(self):
        from src.api.nexon_api import search_players, get_season_id
        query = self._search_var.get()

        has_filter = bool(self._active_filters)
        if not query.strip() and not has_filter:
            self._clear_list()
            count = len(self._spid_list)
            self._status_label.configure(
                text=f"선수 이름을 입력하세요. (총 {count:,}명)" if count else "선수 이름을 입력하세요."
            )
            return

        results = search_players(query, self._spid_list) if query.strip() else self._spid_list

        if "__season_ids__" in self._active_filters:
            # 시즌 검색 모드: 특정 시즌 ID로 필터
            season_ids = self._active_filters["__season_ids__"]
            if season_ids:
                results = [p for p in results if get_season_id(p.get("id", 0)) in season_ids]
        elif self._active_filters:
            # 카테고리/연도 필터
            filtered = []
            for player in results:
                spid = player.get("id", 0)
                season_id = get_season_id(spid)
                info = self._season_map.get(season_id, {})
                cat = info.get("category", "")
                if cat not in self._active_filters:
                    continue
                selected_years = self._active_filters[cat]
                if "전체" not in selected_years:
                    year = info.get("year", "")
                    if "기타" in selected_years and not year:
                        pass  # 연도 없는 항목 포함
                    elif year in selected_years:
                        pass
                    else:
                        continue
                filtered.append(player)
            results = filtered

        results = results[:50]
        self._render_results(results)

    def _render_results(self, results: list[dict]):
        from src.api.nexon_api import get_season_id
        self._clear_list()

        if not results:
            self._status_label.configure(text="검색 결과가 없습니다.")
            return

        self._status_label.configure(text=f"로딩 중... ({len(results)}명)")

        for player in results:
            spid = player.get("id", 0)
            season_id = get_season_id(spid)
            season_info = self._season_map.get(season_id, {
                "seasonId": season_id,
                "shortName": "",
                "seasonImg": "",
                "category": "기타",
                "year": "",
            })

            item = PlayerListItem(
                self._scroll,
                player=player,
                season_info=season_info,
                on_click=self._item_clicked,
                on_no_image=lambda p=player: self._remove_no_image_item(p),
            )
            item.pack(fill="x", pady=2)
            self._items.append(item)

    def _remove_no_image_item(self, player: dict):
        to_remove = [i for i in self._items if i._player is player]
        for item in to_remove:
            self._items.remove(item)
            item.destroy()
        count = len(self._items)
        self._status_label.configure(
            text=f"{count}명 검색됨" if count else "검색 결과가 없습니다."
        )

    def _item_clicked(self, player: dict):
        for item in self._items:
            item.set_selected(item._player is player)
        self._on_select(player)

    def _clear_list(self):
        for item in self._items:
            item.destroy()
        self._items.clear()

    # ──────────────────────────────────────────
    # 외부 데이터 설정
    # ──────────────────────────────────────────

    def set_spid_list(self, spid_list: list[dict]):
        self._spid_list = spid_list
        count = len(spid_list)
        self._status_label.configure(text=f"선수 이름을 입력하세요. (총 {count:,}명)")

    def set_season_data(self, seasons: list[dict], season_map: dict[int, dict]):
        self._seasons = seasons
        self._season_map = season_map

    def set_loading(self, loading: bool):
        self._search_entry.configure(state="disabled" if loading else "normal")
        self._search_btn.configure(state="disabled" if loading else "normal")
        if loading:
            self._status_label.configure(text="선수 데이터 로딩 중...")
