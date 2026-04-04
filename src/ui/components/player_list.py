"""선수 검색 결과 목록 위젯"""

import concurrent.futures
import threading
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from src.ui.components.filter_panel import FilterDropdown
from src.ui import font_manager as fm

THUMB_SIZE = 48
BADGE_SIZE = 30

_BLANK_THUMB: Optional[ctk.CTkImage] = None
_BLANK_BADGE: Optional[ctk.CTkImage] = None

# 이미지 로드 전용 스레드풀 — 최대 20개 동시 요청으로 CDN 과부하 방지
_img_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=20, thread_name_prefix="imgload"
)


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
        **kwargs,
    ):
        super().__init__(master, cursor="hand2", corner_radius=6, **kwargs)
        self._player = player
        self._on_click = on_click
        self._selected = False
        self._destroyed = False
        self._futures: list[concurrent.futures.Future] = []

        spid = player.get("id", 0)
        name = player.get("name", "알 수 없음")
        self._spid = spid
        self._season_id = season_info.get("seasonId", 0)
        self._season_img_url = season_info.get("seasonImg", "")

        self._thumb_label = ctk.CTkLabel(
            self, text="", image=_get_blank_thumb(), width=THUMB_SIZE, height=THUMB_SIZE
        )
        self._thumb_label.pack(side="left", padx=(6, 4), pady=6)

        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True, pady=6)

        name_label = ctk.CTkLabel(
            text_frame, text=name, font=fm.font(13, "bold"), anchor="w"
        )
        name_label.pack(anchor="w")

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

    def start_loading(self):
        """위젯 표시 후 호출 — 스레드풀에 이미지 로드 예약."""
        if self._destroyed:
            return
        f1 = _img_pool.submit(self._load_player)
        f2 = _img_pool.submit(self._load_badge)
        self._futures = [f1, f2]

    def _load_player(self):
        if self._destroyed:
            return
        from src.api.nexon_api import get_player_image
        img = get_player_image(self._spid)
        if self._destroyed or img is None:
            return
        ctk_img = ctk.CTkImage(
            light_image=img, dark_image=img, size=(THUMB_SIZE, THUMB_SIZE)
        )
        self.after(0, lambda i=ctk_img: self._set_thumb(i))

    def _load_badge(self):
        if self._destroyed:
            return
        from src.api.nexon_api import get_season_badge
        img = get_season_badge(self._season_id, self._season_img_url)
        if self._destroyed or img is None:
            return
        ctk_img = ctk.CTkImage(
            light_image=img, dark_image=img, size=(BADGE_SIZE, BADGE_SIZE)
        )
        self.after(0, lambda i=ctk_img: self._set_badge(i))

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
        for f in self._futures:
            f.cancel()
        self._futures.clear()
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


_HDR_NORMAL = ("gray92", "gray20")
_HDR_HOVER  = ("gray85", "gray25")
_HDR_ACTIVE = ("gray75", "gray30")


class PlayerGroupItem(ctk.CTkFrame):
    """PID 기준으로 묶인 선수 카드 그룹 (아코디언)."""

    def __init__(
        self,
        master,
        pid: str,
        player_name: str,
        players: list[dict],
        season_map: dict,
        on_click: Callable,
        expanded: bool = False,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._pid = pid
        self._players = players
        self._season_map = season_map
        self._on_click = on_click
        self._expanded = False
        self._items: list[PlayerListItem] = []
        self._body_frame: Optional[ctk.CTkFrame] = None

        # ── 헤더 ──
        self._header = ctk.CTkFrame(self, fg_color=_HDR_NORMAL, corner_radius=6, cursor="hand2")
        self._header.pack(fill="x")

        self._arrow_label = ctk.CTkLabel(
            self._header,
            text="▶",
            font=fm.font(11),
            width=20,
        )
        self._arrow_label.pack(side="left", padx=(8, 2), pady=8)

        self._name_label = ctk.CTkLabel(
            self._header,
            text=player_name,
            font=fm.font(13, "bold"),
            anchor="w",
        )
        self._name_label.pack(side="left", pady=8)

        count_label = ctk.CTkLabel(
            self._header,
            text=f"  {len(players)}개 카드",
            font=fm.font(11),
            text_color="gray",
            anchor="w",
        )
        count_label.pack(side="left", pady=8)

        for widget in (self._header, self._arrow_label, self._name_label, count_label):
            widget.bind("<Button-1>", self._toggle)
            widget.bind("<Enter>", self._hover_enter)
            widget.bind("<Leave>", self._hover_leave)

        if expanded:
            self._expand(start_loading=False)

    def _toggle(self, _event=None):
        if self._expanded:
            self._collapse()
        else:
            self._expand()

    def _hover_enter(self, _event=None):
        self._header.configure(fg_color=_HDR_HOVER)

    def _hover_leave(self, _event=None):
        self._header.configure(fg_color=_HDR_ACTIVE if self._expanded else _HDR_NORMAL)

    def _expand(self, start_loading: bool = True):
        if self._expanded:
            return
        self._expanded = True
        self._arrow_label.configure(text="▼")
        self._header.configure(fg_color=_HDR_ACTIVE)

        self._body_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._body_frame.pack(fill="x", padx=(16, 0), pady=(2, 0))

        from src.api.nexon_api import get_season_id
        for player in self._players:
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
                self._body_frame,
                player=player,
                season_info=season_info,
                on_click=self._on_click,
                fg_color="transparent",
            )
            item.pack(fill="x", pady=2)
            self._items.append(item)

        if start_loading:
            items_snapshot = list(self._items)
            self.after(0, lambda: [
                item.start_loading() for item in items_snapshot if not item._destroyed
            ])

    def _collapse(self):
        if not self._expanded:
            return
        self._expanded = False
        self._arrow_label.configure(text="▶")
        self._header.configure(fg_color="transparent")

        for item in self._items:
            item.destroy()
        self._items.clear()

        if self._body_frame:
            self._body_frame.destroy()
            self._body_frame = None

    def start_loading_items(self):
        """확장된 상태에서 이미지 로드 시작."""
        items_snapshot = list(self._items)
        for item in items_snapshot:
            if not item._destroyed:
                item.start_loading()

    def deselect_all(self):
        for item in self._items:
            item.set_selected(False)

    def find_and_select(self, spid: int) -> Optional[PlayerListItem]:
        """SPID가 일치하는 아이템을 선택하고 반환. 없으면 None."""
        for item in self._items:
            if item._player.get("id") == spid:
                item.set_selected(True)
                return item
        return None

    def reload_thumb(self, spid: int) -> bool:
        """해당 SPID 썸네일 다시 로드. 찾으면 True 반환."""
        for item in self._items:
            if item._player.get("id") == spid:
                item.start_loading()
                return True
        return False

    def destroy(self):
        for item in self._items:
            item.destroy()
        self._items.clear()
        super().destroy()


class PlayerSearchPanel(ctk.CTkFrame):
    def __init__(self, master, on_select: Callable[[dict], None], **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._groups: list[PlayerGroupItem] = []
        self._spid_list: list[dict] = []
        self._season_map: dict[int, dict] = {}
        self._seasons: list[dict] = []
        self._search_job: Optional[str] = None

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
            font=fm.font(12),
            command=self._do_search,
        )
        self._search_btn.grid(row=0, column=1, padx=(0, 6))

        self._filter_btn = ctk.CTkButton(
            search_row,
            text="필터 ▼",
            width=72, height=36,
            font=fm.font(12),
            fg_color="transparent",
            border_width=1,
            border_color=("gray65", "gray45"),
            text_color=("gray20", "gray90"),
            hover_color=("gray85", "gray30"),
            command=self._toggle_dropdown,
        )
        self._filter_btn.grid(row=0, column=2)

        self._status_label = ctk.CTkLabel(
            self, text="데이터 로딩 중...", font=fm.font(11), text_color="gray"
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

        # 전체 매칭 결과 (제한 없음) — 필터 후에 자름
        results = search_players(query, self._spid_list) if query.strip() else list(self._spid_list)

        if "__season_ids__" in self._active_filters:
            season_ids = self._active_filters["__season_ids__"]
            if season_ids:
                results = [p for p in results if get_season_id(p.get("id", 0)) in season_ids]
        elif self._active_filters:
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
                        pass
                    elif year in selected_years:
                        pass
                    else:
                        continue
                filtered.append(player)
            results = filtered

        # 필터 적용 후 상위 200개 렌더 (그룹화 후에는 카드가 많아도 헤더만 보임)
        self._render_groups(results[:200])

    def _render_groups(self, results: list[dict]):
        self._clear_list()

        if not results:
            self._status_label.configure(text="검색 결과가 없습니다.")
            return

        # PID 기준으로 그룹화
        from src.api.nexon_api import get_season_id
        pid_order: list[str] = []
        pid_groups: dict[str, list[dict]] = {}
        pid_names: dict[str, str] = {}

        for player in results:
            spid = player.get("id", 0)
            pid = str(spid)[3:]  # 앞 3자리 = 시즌 ID, 나머지 = PID
            if pid not in pid_groups:
                pid_order.append(pid)
                pid_groups[pid] = []
                pid_names[pid] = player.get("name", "알 수 없음")
            pid_groups[pid].append(player)

        # 가나다순 정렬
        pid_order.sort(key=lambda pid: pid_names[pid])

        total_players = len(results)
        total_groups = len(pid_order)
        auto_expand = total_groups == 1

        for pid in pid_order:
            players = pid_groups[pid]
            name = pid_names[pid]
            group = PlayerGroupItem(
                self._scroll,
                pid=pid,
                player_name=name,
                players=players,
                season_map=self._season_map,
                on_click=self._item_clicked,
                expanded=auto_expand,
            )
            group.pack(fill="x", pady=2)
            self._groups.append(group)

        if total_groups == 1:
            # 단일 그룹: 바로 이미지 로드
            items_snapshot = list(self._groups[0]._items)
            self.after(0, lambda: [
                item.start_loading() for item in items_snapshot if not item._destroyed
            ])
            self._status_label.configure(
                text=f"{total_players}개 카드 검색됨"
            )
        else:
            self._status_label.configure(
                text=f"{total_players}명 / {total_groups}개 선수 검색됨"
            )

    def _item_clicked(self, player: dict):
        # 모든 그룹의 모든 아이템 선택 해제
        for group in self._groups:
            group.deselect_all()
        # 클릭된 아이템 선택
        target_spid = player.get("id", 0)
        for group in self._groups:
            found = group.find_and_select(target_spid)
            if found:
                break
        self._on_select(player)

    def _clear_list(self):
        for group in self._groups:
            group.destroy()
        self._groups.clear()

    # ──────────────────────────────────────────
    # 외부 데이터 설정
    # ──────────────────────────────────────────

    def search_by_pid(self, pid_str: str, auto_select_spid: int = 0):
        """PID 기반 검색. pid_str = str(spid)[3:] 형식의 문자열."""
        results = [
            p for p in self._spid_list
            if str(p.get("id", 0))[3:] == pid_str
        ]
        self._search_var.set("")
        self._render_groups(results[:200])
        if results:
            self._status_label.configure(text=f"PID {pid_str} — {len(results)}개 카드 검색됨")

        if auto_select_spid:
            # 레이아웃 강제 완료 후 스크롤·선택을 한 번에 처리 → 목록이 이미 맞는 위치에서 보임
            self._scroll.update_idletasks()
            self._auto_select(auto_select_spid)

    def _auto_select(self, spid: int):
        """렌더링된 목록에서 해당 SPID 항목을 자동 선택 후 스크롤."""
        # 먼저 해당 SPID가 속한 그룹 찾기
        target_group: Optional[PlayerGroupItem] = None
        for group in self._groups:
            for player in group._players:
                if player.get("id") == spid:
                    target_group = group
                    break
            if target_group:
                break

        if not target_group:
            return

        # 그룹이 접혀있으면 먼저 펼치기
        if not target_group._expanded:
            target_group._expand(start_loading=True)
            self._scroll.update_idletasks()

        # 아이템 선택
        found_item = target_group.find_and_select(spid)
        if found_item:
            self._scroll_to_item(found_item)
            self._on_select(found_item._player)

    def _scroll_to_item(self, item):
        """항목이 스크롤 영역 중앙에 오도록 스크롤."""
        try:
            canvas = self._scroll._parent_canvas
            bbox = canvas.bbox("all")
            if not bbox:
                return
            total_h = bbox[3]
            visible_h = canvas.winfo_height()
            if total_h <= visible_h:
                return
            item_y = item.winfo_y()
            item_h = item.winfo_height()
            fraction = max(0.0, min(1.0, (item_y + item_h / 2 - visible_h / 2) / total_h))
            canvas.yview_moveto(fraction)
        except Exception:
            pass

    def reload_thumb(self, spid: int):
        """특정 SPID 항목의 썸네일만 다시 로드."""
        for group in self._groups:
            if group.reload_thumb(spid):
                break

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
