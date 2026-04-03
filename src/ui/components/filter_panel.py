"""아코디언 방식 시즌 필터 드롭다운"""

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from src.api.nexon_api import CATEGORY_ORDER


class FilterDropdown(tk.Toplevel):
    WIDTH = 320
    SCROLL_HEIGHT = 240

    def __init__(
        self,
        main_window: tk.Tk,
        anchor: tk.Widget,
        seasons: list[dict],
        active_filters: dict,        # {category: set[year]} 현재 선택 상태 복원용
        on_change: Callable,         # on_change(active_filters: dict)
        on_close: Callable,
    ):
        super().__init__(main_window)
        self._main_window = main_window
        self._on_change = on_change
        self._on_close = on_close
        self._seasons = seasons

        # 선택 상태: {category: set[year | "전체" | "기타"]}
        # 드롭다운 열 때 이전 카테고리 필터 복원 (season_ids 제외)
        self._selected: dict[str, set[str]] = {
            cat: set(years)
            for cat, years in active_filters.items()
            if cat != "__season_ids__"
        }
        # 펼쳐진 카테고리 (선택된 카테고리는 기본 펼침)
        self._expanded: set[str] = set(self._selected.keys())

        # 시즌 검색 모드
        self._in_search_mode = False
        self._selected_season_ids: set[int] = set()

        # 위젯 참조
        self._cat_year_frames: dict[str, ctk.CTkFrame] = {}
        self._year_btns: dict[str, dict[str, ctk.CTkButton]] = {}
        self._cat_sel_btns: dict[str, ctk.CTkButton] = {}   # "N개 ✕" 버튼
        self._cat_expand_btns: dict[str, ctk.CTkButton] = {}
        self._season_btns: dict[int, ctk.CTkButton] = {}

        self._outside_bind_id: Optional[str] = None

        self.withdraw()  # 위치 확정 전까지 숨김 (좌상단 깜빡임 방지)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#1a1a1a")

        self._build()

        # build + idletasks 이후 위치 계산 (위젯 크기 확정된 뒤)
        self.update_idletasks()
        ax = anchor.winfo_rootx()
        ay = anchor.winfo_rooty() + anchor.winfo_height() + 2
        h = self.winfo_reqheight()
        self.geometry(f"{self.WIDTH}x{h}+{ax}+{ay}")
        self.deiconify()  # 올바른 위치에서 표시

        self.after(50, self._bind_outside_click)
        self.focus_set()

    # ──────────────────────────────────────────
    # 팝업 관리
    # ──────────────────────────────────────────

    def _bind_outside_click(self):
        if not self.winfo_exists():
            return
        self._outside_bind_id = self._main_window.bind(
            "<Button-1>", self._on_outside_click, add="+"
        )
        self.bind("<Escape>", lambda _: self._close())

    def _on_outside_click(self, event: tk.Event):
        if not self.winfo_exists():
            return
        px, py = self.winfo_rootx(), self.winfo_rooty()
        pw, ph = self.winfo_width(), self.winfo_height()
        if not (px <= event.x_root <= px + pw and py <= event.y_root <= py + ph):
            self._close()

    def _close(self):
        if self._outside_bind_id:
            try:
                self._main_window.unbind("<Button-1>", self._outside_bind_id)
            except Exception:
                pass
        self._on_close()
        if self.winfo_exists():
            self.destroy()

    # ──────────────────────────────────────────
    # UI 구성
    # ──────────────────────────────────────────

    def _build(self):
        outer = ctk.CTkFrame(
            self, corner_radius=10, border_width=1,
            border_color=("gray70", "gray30"),
        )
        outer.pack(fill="both", expand=True, padx=1, pady=1)

        # ── 헤더
        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 6))
        ctk.CTkLabel(
            header, text="시즌 필터",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            header, text="전체 초기화", width=72, height=26,
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            text_color=("gray50", "gray60"),
            font=ctk.CTkFont(size=11),
            command=self._reset,
        ).pack(side="right")

        ctk.CTkFrame(outer, height=1, fg_color=("gray80", "gray30")).pack(fill="x", padx=8)

        # ── 시즌 이름 검색창
        search_row = ctk.CTkFrame(outer, fg_color="transparent")
        search_row.pack(fill="x", padx=10, pady=(8, 6))
        search_row.columnconfigure(0, weight=1)

        self._season_search_var = tk.StringVar()
        self._season_search_var.trace_add("write", self._on_season_search)

        ctk.CTkEntry(
            search_row,
            placeholder_text="시즌 이름 검색 (예: GR, TOTS...)",
            textvariable=self._season_search_var,
            height=30,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))

        ctk.CTkButton(
            search_row,
            text="✕", width=30, height=30,
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            text_color=("gray50", "gray60"),
            font=ctk.CTkFont(size=12),
            command=lambda: self._season_search_var.set(""),
        ).grid(row=0, column=1)

        ctk.CTkFrame(outer, height=1, fg_color=("gray80", "gray30")).pack(fill="x", padx=8, pady=(0, 2))

        # ── 아코디언 (카테고리 → 연도 선택)
        self._accordion_scroll = ctk.CTkScrollableFrame(
            outer, height=self.SCROLL_HEIGHT,
            fg_color="transparent",
        )
        self._accordion_scroll.pack(fill="x", padx=6, pady=(0, 6))
        self._build_accordion(self._accordion_scroll)

        # ── 시즌 검색 결과 (처음엔 숨김)
        self._search_scroll = ctk.CTkScrollableFrame(
            outer, height=self.SCROLL_HEIGHT,
            fg_color="transparent",
        )
        self._search_results_grid = ctk.CTkFrame(self._search_scroll, fg_color="transparent")
        self._search_results_grid.pack(fill="x", padx=4, pady=4)
        for i in range(3):
            self._search_results_grid.columnconfigure(i, weight=1)

    def _build_accordion(self, parent):
        existing = {s["category"] for s in self._seasons}
        cats = [c for c in CATEGORY_ORDER if c in existing]
        for cat in cats:
            self._build_cat_section(parent, cat)

    def _build_cat_section(self, parent, cat):
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", pady=1)

        # ── 카테고리 헤더 행 (grid 레이아웃으로 안정적인 고정 구조)
        header = ctk.CTkFrame(section, fg_color=("gray88", "gray22"), corner_radius=6)
        header.pack(fill="x", padx=2)
        header.columnconfigure(1, weight=1)  # 카테고리명 칸이 남은 공간 차지

        expand_btn = ctk.CTkButton(
            header, text="▶", width=28, height=32,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            text_color=("gray40", "gray70"),
            command=lambda c=cat: self._toggle_expand(c),
        )
        expand_btn.grid(row=0, column=0, padx=(2, 0), pady=2)
        self._cat_expand_btns[cat] = expand_btn

        ctk.CTkButton(
            header, text=cat,
            anchor="w",
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            text_color=("gray10", "gray95"),
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda c=cat: self._toggle_expand(c),
        ).grid(row=0, column=1, sticky="ew", padx=2, pady=2)

        # 선택 현황 버튼 — 항상 grid에 존재, 선택 없으면 투명하게 숨김
        # pack/unpack 대신 configure()만 사용해서 geometry 재계산 루프 방지
        sel_btn = ctk.CTkButton(
            header, text="", width=64, height=24,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="transparent",
            hover_color=("gray88", "gray22"),  # 헤더 배경과 동일 → 비활성 시 invisible
            text_color="white",
            corner_radius=4,
            command=lambda c=cat: self._clear_category(c),
        )
        sel_btn.grid(row=0, column=2, padx=(0, 6), pady=4)
        self._cat_sel_btns[cat] = sel_btn

        # ── 연도 버튼 그리드 (처음엔 숨김)
        year_frame = ctk.CTkFrame(
            section,
            fg_color=("gray92", "gray18"),
            corner_radius=6,
        )
        self._cat_year_frames[cat] = year_frame
        self._year_btns[cat] = {}
        self._build_year_buttons(year_frame, cat)

        # 초기 상태 적용 (이전 세션 선택 복원)
        if cat in self._expanded:
            year_frame.pack(fill="x", padx=2, pady=(2, 0))
            expand_btn.configure(text="▼")

        self._refresh_cat_sel_btn(cat)

    def _build_year_buttons(self, parent, cat):
        years = sorted(
            {s["year"] for s in self._seasons if s["category"] == cat and s["year"]},
            reverse=True,
        )
        has_other = any(s["category"] == cat and not s.get("year") for s in self._seasons)

        all_opts = ["전체"] + list(years)
        if has_other:
            all_opts.append("기타")

        col, row = 0, 0
        for opt in all_opts:
            selected = opt in self._selected.get(cat, set())
            label = f"'{opt}" if (opt.isdigit() and len(opt) == 2) else opt
            btn = ctk.CTkButton(
                parent,
                text=label,
                width=52, height=26,
                font=ctk.CTkFont(size=11),
                fg_color="#4CAF50" if selected else "transparent",
                text_color="white" if selected else ("gray20", "gray90"),
                border_width=1,
                border_color="#4CAF50" if selected else ("gray65", "gray45"),
                hover_color="#388E3C" if selected else ("gray80", "gray25"),
                command=lambda c=cat, y=opt: self._toggle_year(c, y),
            )
            btn.grid(row=row, column=col, padx=4, pady=4)
            self._year_btns[cat][opt] = btn
            col += 1
            if col >= 4:
                col = 0
                row += 1

    # ──────────────────────────────────────────
    # 아코디언 동작
    # ──────────────────────────────────────────

    def _toggle_expand(self, cat: str):
        frame = self._cat_year_frames[cat]
        if cat in self._expanded:
            self._expanded.discard(cat)
            frame.pack_forget()
            self._cat_expand_btns[cat].configure(text="▶")
        else:
            self._expanded.add(cat)
            frame.pack(fill="x", padx=2, pady=(2, 0))
            self._cat_expand_btns[cat].configure(text="▼")

    def _toggle_year(self, cat: str, year: str):
        if cat not in self._selected:
            self._selected[cat] = set()

        if year == "전체":
            # 이미 전체 선택 → 해제
            if "전체" in self._selected[cat]:
                del self._selected[cat]
            else:
                # 전체 선택 → 나머지 해제
                self._selected[cat] = {"전체"}
        else:
            # 특정 연도 선택 시 "전체" 해제
            self._selected[cat].discard("전체")
            if year in self._selected[cat]:
                self._selected[cat].discard(year)
                if not self._selected[cat]:
                    del self._selected[cat]
            else:
                self._selected[cat].add(year)

        self._refresh_year_btns(cat)
        self._refresh_cat_sel_btn(cat)
        self._notify()

    def _refresh_year_btns(self, cat: str):
        selected_years = self._selected.get(cat, set())
        for opt, btn in self._year_btns.get(cat, {}).items():
            sel = opt in selected_years
            btn.configure(
                fg_color="#4CAF50" if sel else "transparent",
                text_color="white" if sel else ("gray20", "gray90"),
                border_color="#4CAF50" if sel else ("gray65", "gray45"),
                hover_color="#388E3C" if sel else ("gray80", "gray25"),
            )

    def _refresh_cat_sel_btn(self, cat: str):
        """카테고리 헤더의 '선택 현황 + 클리어' 버튼 업데이트.
        pack/unpack 없이 configure()만 사용 — geometry 재계산 루프 방지."""
        selected_years = self._selected.get(cat, set())
        btn = self._cat_sel_btns[cat]

        if selected_years:
            label = "전체 ✕" if "전체" in selected_years else f"{len(selected_years)}개 ✕"
            btn.configure(
                text=label,
                fg_color="#4CAF50",
                hover_color="#388E3C",
            )
        else:
            btn.configure(
                text="",
                fg_color="transparent",
                hover_color=("gray88", "gray22"),
            )

    def _clear_category(self, cat: str):
        if cat not in self._selected:
            return  # 선택 없으면 무시 (투명 버튼 클릭 시 안전하게 처리)
        del self._selected[cat]
        self._refresh_year_btns(cat)
        self._refresh_cat_sel_btn(cat)
        self._notify()

    # ──────────────────────────────────────────
    # 시즌 이름 검색
    # ──────────────────────────────────────────

    def _on_season_search(self, *_):
        text = self._season_search_var.get().strip()
        if text:
            if not self._in_search_mode:
                self._accordion_scroll.pack_forget()
                self._search_scroll.pack(fill="x", padx=6, pady=(0, 6))
                self._in_search_mode = True
            self._render_season_results(text)
        else:
            if self._in_search_mode:
                self._search_scroll.pack_forget()
                self._accordion_scroll.pack(fill="x", padx=6, pady=(0, 6))
                self._in_search_mode = False
            if self._selected_season_ids:
                self._selected_season_ids.clear()
                self._notify()

    def _render_season_results(self, text: str):
        for w in self._search_results_grid.winfo_children():
            w.destroy()
        self._season_btns.clear()
        # 선택 상태는 유지 (검색어 바꿔도 체크 유지)

        q = text.lower()
        matches = [
            s for s in self._seasons
            if q in s.get("shortName", "").lower() or q in s.get("className", "").lower()
        ]

        if not matches:
            ctk.CTkLabel(
                self._search_results_grid, text="검색 결과 없음",
                font=ctk.CTkFont(size=11), text_color="gray",
            ).grid(row=0, column=0, columnspan=3, padx=8, pady=16)
            return

        col, row = 0, 0
        for s in matches[:24]:
            sid = s["seasonId"]
            selected = sid in self._selected_season_ids
            label = s.get("shortName", str(sid))[:12]
            btn = ctk.CTkButton(
                self._search_results_grid,
                text=label, width=80, height=28,
                font=ctk.CTkFont(size=11),
                fg_color="#2196F3" if selected else "transparent",
                text_color="white" if selected else ("gray20", "gray90"),
                border_width=1,
                border_color="#2196F3" if selected else ("gray65", "gray45"),
                hover_color="#1976D2" if selected else ("gray80", "gray25"),
                command=lambda i=sid: self._toggle_season(i),
            )
            btn.grid(row=row, column=col, padx=4, pady=4)
            self._season_btns[sid] = btn
            col += 1
            if col >= 3:
                col = 0
                row += 1

        if len(matches) > 24:
            extra_row = row + (1 if col > 0 else 0)
            ctk.CTkLabel(
                self._search_results_grid,
                text=f"... 외 {len(matches) - 24}개",
                font=ctk.CTkFont(size=10), text_color="gray",
            ).grid(row=extra_row, column=0, columnspan=3, pady=(0, 4))

    def _toggle_season(self, season_id: int):
        if season_id in self._selected_season_ids:
            self._selected_season_ids.discard(season_id)
        else:
            self._selected_season_ids.add(season_id)

        for sid, btn in self._season_btns.items():
            sel = sid in self._selected_season_ids
            btn.configure(
                fg_color="#2196F3" if sel else "transparent",
                text_color="white" if sel else ("gray20", "gray90"),
                border_color="#2196F3" if sel else ("gray65", "gray45"),
                hover_color="#1976D2" if sel else ("gray80", "gray25"),
            )
        self._notify()

    # ──────────────────────────────────────────
    # 초기화 / 알림
    # ──────────────────────────────────────────

    def _reset(self):
        cats = list(self._cat_year_frames.keys())
        self._selected.clear()
        self._selected_season_ids.clear()
        for cat in cats:
            if cat in self._expanded:
                self._expanded.discard(cat)
                self._cat_year_frames[cat].pack_forget()
                self._cat_expand_btns[cat].configure(text="▶")
            self._refresh_year_btns(cat)
            self._refresh_cat_sel_btn(cat)
        # 검색창 초기화 (trace가 _on_season_search 호출 → 모드 전환)
        self._season_search_var.set("")
        self._notify()

    def _notify(self):
        if self._in_search_mode:
            if self._selected_season_ids:
                self._on_change({"__season_ids__": self._selected_season_ids})
            else:
                self._on_change({})
        else:
            self._on_change(dict(self._selected))
