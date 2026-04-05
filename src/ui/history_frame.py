"""변경 이력 화면 프레임"""

import subprocess
import threading
from pathlib import Path
from tkinter import messagebox
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from src.core import history, face_changer, crest_changer, manager_changer
from src.core.config import Config
from src.core.face_changer import ChangeRecord
from src.core.crest_changer import CrestChangeRecord
from src.core.manager_changer import ManagerChangeRecord
from src.ui import font_manager as fm

_THUMB = 52


def _load_thumb(path: Optional[str]) -> Optional[ctk.CTkImage]:
    if not path:
        return None
    try:
        img = Image.open(path).convert("RGBA")
        img.thumbnail((_THUMB, _THUMB), Image.LANCZOS)
        sq = Image.new("RGBA", (_THUMB, _THUMB), (0, 0, 0, 0))
        sq.paste(img, ((_THUMB - img.width) // 2, (_THUMB - img.height) // 2))
        return ctk.CTkImage(light_image=sq, dark_image=sq, size=(_THUMB, _THUMB))
    except Exception:
        return None


def _open_folder(path: Path):
    target = path if path.exists() else path.parent
    if target.exists():
        subprocess.Popen(f'explorer "{target}"')


class FaceHistoryGroup(ctk.CTkFrame):
    """SPID별 미페 변경 이력 아코디언 그룹."""

    def __init__(
        self,
        master,
        spid: int,
        records: list[ChangeRecord],   # 오래된 순
        config: Config,
        on_restore: Callable[[int], None],
        on_delete: Callable[[int], None],
        **kwargs,
    ):
        super().__init__(master, corner_radius=8, **kwargs)
        self._spid = spid
        self._records = records
        self._config = config
        self._on_restore = on_restore
        self._on_delete = on_delete
        self._collapsed = False
        self._check_vars: dict[int, ctk.BooleanVar] = {}  # pos → BooleanVar

        self._build()

    def _build(self):
        self._build_header()

        # 구분선
        ctk.CTkFrame(self, height=1, fg_color=("gray80", "gray35")).pack(
            fill="x", padx=8, pady=(0, 2)
        )

        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="x", padx=8, pady=(0, 6))
        self._build_entries()

    def _build_header(self):
        player_name = self._records[-1].player_name
        count = len(self._records)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))

        # 접기/펼치기 영역 (왼쪽)
        toggle_area = ctk.CTkFrame(header, fg_color="transparent", cursor="hand2")
        toggle_area.pack(side="left", fill="y")

        self._arrow = ctk.CTkLabel(
            toggle_area, text="▼", font=fm.font(11), width=20
        )
        self._arrow.pack(side="left")

        ctk.CTkLabel(
            toggle_area,
            text=player_name,
            font=fm.font(13, "bold"),
        ).pack(side="left")

        ctk.CTkLabel(
            toggle_area,
            text=f"  {count}개 기록",
            font=fm.font(11),
            text_color="gray",
        ).pack(side="left")

        for w in toggle_area.winfo_children() + [toggle_area]:
            w.bind("<Button-1>", self._toggle)

        # 버튼 영역 (오른쪽)
        btn_area = ctk.CTkFrame(header, fg_color="transparent")
        btn_area.pack(side="right")

        backup_dir = self._config.backup_path / f"p{self._spid}"
        ctk.CTkButton(
            btn_area, text="폴더",
            width=52, height=26,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            text_color=("gray10", "gray90"),
            font=fm.font(11),
            command=lambda d=backup_dir: _open_folder(d),
        ).pack(side="right", padx=(4, 0))

        ctk.CTkButton(
            btn_area, text="전체 삭제",
            width=72, height=26,
            fg_color="#F44336",
            hover_color="#C62828",
            font=fm.font(11),
            command=self._delete_all,
        ).pack(side="right", padx=4)

        self._del_sel_btn = ctk.CTkButton(
            btn_area, text="선택 삭제",
            width=80, height=26,
            fg_color=("gray60", "gray40"),
            hover_color=("gray50", "gray50"),
            font=fm.font(11),
            state="disabled",
            command=self._delete_selected,
        )
        self._del_sel_btn.pack(side="right", padx=4)

    def _build_entries(self):
        """최신순으로 항목 표시."""
        n = len(self._records)
        game_file = str(self._config.face_dir / f"p{self._spid}.png")

        for display_idx, record in enumerate(reversed(self._records)):
            pos = n - 1 - display_idx   # 원본 리스트 인덱스
            is_active = (display_idx == 0)

            # after_path 계산 (우선순위: result_path → 다음기록 backup → 현재게임파일)
            rp = record.result_path
            if rp and Path(rp).exists():
                after_path = rp
            elif is_active:
                after_path = game_file
            else:
                next_record = self._records[pos + 1]
                after_path = next_record.backup_path

            self._add_entry_row(record, pos, is_active, after_path)

    def _add_entry_row(
        self,
        record: ChangeRecord,
        pos: int,
        active: bool,
        after_path: Optional[str],
    ):
        var = ctk.BooleanVar(value=False)
        self._check_vars[pos] = var

        row_color = "transparent" if active else ("gray92", "gray18")
        row = ctk.CTkFrame(self._body, fg_color=row_color, corner_radius=6)
        row.pack(fill="x", pady=(0, 3))
        row.columnconfigure(5, weight=1)

        alpha = ("gray20", "gray80") if active else ("gray60", "gray50")

        # 체크박스
        cb = ctk.CTkCheckBox(
            row, text="", variable=var,
            width=20, height=20,
            command=self._on_check_changed,
        )
        cb.grid(row=0, column=0, padx=(8, 2), pady=8)

        # before 썸네일
        before_label = self._make_thumb(row, active)
        before_label.grid(row=0, column=1, padx=(2, 4), pady=8)

        ctk.CTkLabel(
            row, text="→", font=fm.font(13), text_color=alpha
        ).grid(row=0, column=2, padx=2)

        # after 썸네일
        after_label = self._make_thumb(row, active)
        after_label.grid(row=0, column=3, padx=(4, 8), pady=8)

        # 정보 텍스트
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=5, sticky="ew", padx=4, pady=8)

        src = Path(record.image_path).name if record.image_path else ""
        ctk.CTkLabel(
            info, text=src, font=fm.font(11), text_color=alpha, anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            info, text=record.changed_at, font=fm.font(10), text_color="gray", anchor="w"
        ).pack(anchor="w")

        # 복원/삭제 버튼 (최신 항목만)
        if active:
            has_backup = bool(record.backup_path) and Path(record.backup_path).exists()
            ctk.CTkButton(
                row,
                text="복원" if has_backup else "삭제(백업없음)",
                width=90 if not has_backup else 64, height=30,
                fg_color="#607D8B" if has_backup else "#F44336",
                hover_color="#455A64" if has_backup else "#C62828",
                font=fm.font(11),
                command=lambda r=record: self._restore(r),
            ).grid(row=0, column=6, padx=(0, 8), pady=8)

        # 썸네일 비동기 로드
        before_path = record.backup_path if (
            record.backup_path and Path(record.backup_path).exists()
        ) else None
        self._load_thumb_async(before_label, before_path, active)
        self._load_thumb_async(after_label, after_path, active)

    def _toggle(self, _event=None):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._arrow.configure(text="▶")
            self._body.pack_forget()
        else:
            self._arrow.configure(text="▼")
            self._body.pack(fill="x", padx=8, pady=(0, 6))

    def _on_check_changed(self):
        checked = sum(1 for v in self._check_vars.values() if v.get())
        if checked:
            self._del_sel_btn.configure(
                text=f"선택 삭제({checked})", state="normal",
                fg_color="#F44336", hover_color="#C62828",
            )
        else:
            self._del_sel_btn.configure(
                text="선택 삭제", state="disabled",
                fg_color=("gray60", "gray40"), hover_color=("gray50", "gray50"),
            )

    def _restore(self, record: ChangeRecord):
        has_backup = bool(record.backup_path) and Path(record.backup_path).exists()
        msg = (
            f"'{record.player_name}'의 미페를 이 백업으로 복원하겠습니까?\n"
            f"변경 일시: {record.changed_at}"
            if has_backup
            else f"'{record.player_name}'의 교체 파일을 삭제하겠습니까?\n(백업 없음 - 게임 재실행 시 자동 복구)"
        )
        if not messagebox.askyesno("복원 확인", msg):
            return
        try:
            face_changer.restore_face(record, self._config)
            history.remove_record(record.spid)
            self._on_restore(record.spid)
        except Exception as e:
            messagebox.showerror("복원 실패", str(e))

    def _delete_selected(self):
        selected_positions = [pos for pos, var in self._check_vars.items() if var.get()]
        if not selected_positions:
            return
        count = len(selected_positions)
        if not messagebox.askyesno(
            "선택 삭제",
            f"{count}개 항목의 백업 파일을 삭제하고 이력에서 제거하겠습니까?\n"
            "현재 게임 파일은 변경되지 않습니다.",
        ):
            return
        selected_set = set(selected_positions)
        for pos in selected_set:
            face_changer.delete_face_record(self._records[pos])
        # 선택된 위치의 기록 제거
        new_records = [
            r for i, r in enumerate(self._records) if i not in selected_set
        ]
        # JSON 전체 다시 저장 (SPID 전체 교체)
        all_records = history.load_history()
        all_records = [r for r in all_records if r.spid != self._spid]
        all_records.extend(new_records)
        history.save_history(all_records)
        self._on_delete(self._spid)

    def _delete_all(self):
        player_name = self._records[-1].player_name
        if not messagebox.askyesno(
            "전체 삭제",
            f"'{player_name}'의 모든 이력 {len(self._records)}개를 삭제하겠습니까?\n"
            "백업 파일도 모두 삭제되며, 현재 게임 파일은 변경되지 않습니다.",
        ):
            return
        for record in self._records:
            face_changer.delete_face_record(record)
        history.remove_all_face_records(self._spid)
        self._on_delete(self._spid)

    # ── 썸네일 헬퍼 ──────────────────────────

    def _make_thumb(self, parent, active: bool) -> ctk.CTkLabel:
        bg = ("gray80", "gray25") if active else ("gray86", "gray20")
        return ctk.CTkLabel(
            parent, text="…", width=_THUMB, height=_THUMB,
            fg_color=bg, corner_radius=4,
            font=fm.font(10), text_color="gray",
        )

    def _load_thumb_async(self, label: ctk.CTkLabel, path: Optional[str], active: bool):
        if not path:
            label.configure(text="-")
            return

        def _worker():
            img = _load_thumb(path)
            if img and not active:
                try:
                    from PIL import ImageEnhance
                    pil = img._light_image
                    pil = ImageEnhance.Brightness(pil).enhance(0.55)
                    pil = ImageEnhance.Color(pil).enhance(0.4)
                    img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(_THUMB, _THUMB))
                except Exception:
                    pass
            if img:
                label.after(0, lambda i=img: label.configure(image=i, text=""))
            else:
                label.after(0, lambda: label.configure(text="?"))

        threading.Thread(target=_worker, daemon=True).start()


# ══════════════════════════════════════════════════════
# 메인 이력 프레임
# ══════════════════════════════════════════════════════

class HistoryFrame(ctk.CTkFrame):
    def __init__(self, master, config: Config, on_face_restored=None, on_manager_restored=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._config = config
        self._on_face_restored = on_face_restored
        self._on_manager_restored = on_manager_restored
        self._build()
        self.refresh()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(10, 4))

        ctk.CTkLabel(top, text="변경 이력", font=fm.font(16, "bold")).pack(side="left")
        ctk.CTkButton(top, text="새로고침", width=90, command=self.refresh).pack(side="right")

        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def refresh(self):
        for widget in self._scroll.winfo_children():
            widget.destroy()

        face_records = history.load_history()
        crest_records = history.load_crest_history()
        manager_records = history.load_manager_history()

        if not face_records and not crest_records and not manager_records:
            ctk.CTkLabel(
                self._scroll, text="변경 이력이 없습니다.", text_color="gray"
            ).pack(pady=20)
            return

        # ── 미페 이력 ──
        self._add_section_title("미페 변경 이력")
        if face_records:
            self._render_face_groups(face_records)
        else:
            ctk.CTkLabel(
                self._scroll, text="미페 변경 이력이 없습니다.",
                text_color="gray", font=fm.font(11),
            ).pack(anchor="w", padx=16, pady=(0, 4))

        # ── 크레스트 이력 ──
        self._add_section_title("크레스트 변경 이력")
        if crest_records:
            for record in crest_records:
                self._add_crest_row(record)
        else:
            ctk.CTkLabel(
                self._scroll, text="크레스트 변경 이력이 없습니다.",
                text_color="gray", font=fm.font(11),
            ).pack(anchor="w", padx=16, pady=(0, 4))

        # ── 감독 이력 ──
        self._add_section_title("감독 변경 이력")
        if manager_records:
            for record in manager_records:
                self._add_manager_row(record)
        else:
            ctk.CTkLabel(
                self._scroll, text="감독 변경 이력이 없습니다.",
                text_color="gray", font=fm.font(11),
            ).pack(anchor="w", padx=16, pady=(0, 4))

    def _add_section_title(self, title: str):
        ctk.CTkLabel(
            self._scroll, text=title, font=fm.font(13, "bold")
        ).pack(anchor="w", padx=4, pady=(12, 4))

    def _render_face_groups(self, all_records: list[ChangeRecord]):
        # SPID별 그룹화 (삽입 순서 유지)
        spid_order: list[int] = []
        spid_groups: dict[int, list[ChangeRecord]] = {}
        for r in all_records:
            if r.spid not in spid_groups:
                spid_order.append(r.spid)
                spid_groups[r.spid] = []
            spid_groups[r.spid].append(r)

        for spid in spid_order:
            group = FaceHistoryGroup(
                self._scroll,
                spid=spid,
                records=spid_groups[spid],
                config=self._config,
                on_restore=self._on_face_restored_internal,
                on_delete=self._on_face_deleted,
            )
            group.pack(fill="x", pady=(0, 6))

    def _on_face_restored_internal(self, spid: int):
        if self._on_face_restored:
            self._on_face_restored(spid)
        self.refresh()

    def _on_face_deleted(self, spid: int):
        if self._on_face_restored:
            self._on_face_restored(spid)
        self.refresh()

    # ── 크레스트 이력 ──────────────────────────

    def _add_crest_row(self, record: CrestChangeRecord):
        row = ctk.CTkFrame(self._scroll, corner_radius=8)
        row.pack(fill="x", pady=3)
        row.columnconfigure(4, weight=1)

        ctk.CTkLabel(
            row, text=f"c{record.crest_id}",
            font=fm.font(13, "bold"), width=80,
        ).grid(row=0, column=0, padx=(12, 4), pady=10, sticky="w")

        before_label = self._make_thumb_label(row)
        before_label.grid(row=0, column=1, padx=4, pady=10)

        ctk.CTkLabel(row, text="→", font=fm.font(14)).grid(row=0, column=2, padx=2)

        after_label = self._make_thumb_label(row)
        after_label.grid(row=0, column=3, padx=4, pady=10)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=4, sticky="ew", padx=8, pady=10)
        src_name = Path(record.image_path).name if record.image_path else ""
        ctk.CTkLabel(info, text=src_name, font=fm.font(12)).pack(anchor="w")
        ctk.CTkLabel(
            info, text=f"변경: {record.changed_at}",
            font=fm.font(11), text_color="gray",
        ).pack(anchor="w")

        has_backup = any(Path(bp).exists() for bp in record.backup_paths)
        ctk.CTkButton(
            row, text="복원" if has_backup else "삭제",
            width=64, height=32,
            fg_color="#607D8B" if has_backup else "#F44336",
            hover_color="#455A64" if has_backup else "#C62828",
            font=fm.font(11),
            command=lambda r=record: self._restore_crest(r),
        ).grid(row=0, column=5, padx=4, pady=10)

        backup_dir = self._config.backup_path / f"crest_{record.crest_id}"
        ctk.CTkButton(
            row, text="폴더",
            width=52, height=32,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            text_color=("gray10", "gray90"),
            font=fm.font(11),
            command=lambda d=backup_dir: _open_folder(d),
        ).grid(row=0, column=6, padx=(0, 10), pady=10)

        before_path = next(
            (bp for bp in record.backup_paths
             if ("/dark/large/" in bp or "\\dark\\large\\" in bp) and Path(bp).exists()),
            None,
        )
        after_path = str(crest_changer.get_crest_file(
            self._config.crest_dir, "dark", "large", record.crest_id
        ))
        self._load_crest_thumb_async(before_label, before_path)
        self._load_crest_thumb_async(after_label, after_path)

    def _make_thumb_label(self, parent) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            parent, text="…", width=_THUMB, height=_THUMB,
            fg_color=("gray80", "gray25"), corner_radius=4,
            font=fm.font(10), text_color="gray",
        )

    def _load_crest_thumb_async(self, label: ctk.CTkLabel, path: Optional[str]):
        if not path:
            label.configure(text="-")
            return

        def _worker():
            img = _load_thumb(path)
            if img:
                label.after(0, lambda i=img: label.configure(image=i, text=""))
            else:
                label.after(0, lambda: label.configure(text="?"))

        threading.Thread(target=_worker, daemon=True).start()

    def _restore_crest(self, record: CrestChangeRecord):
        has_backup = any(Path(bp).exists() for bp in record.backup_paths)
        msg = (
            f"크레스트 {record.crest_id}번을 원본으로 복원하겠습니까?"
            if has_backup
            else f"크레스트 {record.crest_id}번의 교체 파일을 삭제하겠습니까?\n(백업 없음 - 게임 재실행 시 자동 복구됩니다)"
        )
        if not messagebox.askyesno("복원 확인", msg):
            return
        try:
            crest_changer.restore_crest(record, self._config)
            history.remove_crest_record(record.crest_id)
            self.refresh()
        except Exception as e:
            messagebox.showerror("복원 실패", str(e))

    # ── 감독 이력 ──────────────────────────────

    def _add_manager_row(self, record: ManagerChangeRecord):
        row = ctk.CTkFrame(self._scroll, corner_radius=8)
        row.pack(fill="x", pady=3)
        row.columnconfigure(2, weight=1)

        # 현재 얼굴 썸네일
        thumb_label = self._make_thumb_label(row)
        thumb_label.grid(row=0, column=0, padx=(12, 8), pady=10)

        # 감독 정보
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=2, sticky="ew", padx=4, pady=10)
        ctk.CTkLabel(
            info, text=f"{record.manager_name}",
            font=fm.font(13, "bold"), anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            info, text=record.team,
            font=fm.font(11), text_color="gray", anchor="w",
        ).pack(anchor="w")
        src_name = Path(record.image_path).name if record.image_path not in ("", "(공식 얼굴)") else record.image_path
        ctk.CTkLabel(
            info, text=f"{src_name}  •  {record.changed_at}",
            font=fm.font(10), text_color="gray", anchor="w",
        ).pack(anchor="w")

        # 공식 복원 버튼
        ctk.CTkButton(
            row, text="공식 복원",
            width=72, height=32,
            fg_color="#607D8B", hover_color="#455A64",
            font=fm.font(11),
            command=lambda r=record: self._restore_manager_official(r),
        ).grid(row=0, column=3, padx=4, pady=10)

        # 이력 삭제 버튼
        ctk.CTkButton(
            row, text="삭제",
            width=52, height=32,
            fg_color="#F44336", hover_color="#C62828",
            font=fm.font(11),
            command=lambda r=record: self._delete_manager_record(r),
        ).grid(row=0, column=4, padx=(0, 10), pady=10)

        # 썸네일 비동기 로드 (로컬 파일)
        self._load_manager_thumb_async(thumb_label, record.manager_id)

    def _load_manager_thumb_async(self, label: ctk.CTkLabel, manager_id: str):
        def _worker():
            img = manager_changer.load_manager_image(self._config, manager_id)
            if img is None:
                label.after(0, lambda: label.configure(text="?"))
                return
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(_THUMB, _THUMB))
            label.after(0, lambda i=ctk_img: label.configure(image=i, text=""))
        threading.Thread(target=_worker, daemon=True).start()

    def _restore_manager_official(self, record: ManagerChangeRecord):
        if not messagebox.askyesno(
            "공식 복원",
            f"'{record.manager_name}'의 얼굴을 CDN 공식 이미지로 복원하겠습니까?",
        ):
            return
        try:
            manager_changer.restore_to_official(
                manager_id=record.manager_id,
                manager_name=record.manager_name,
                team=record.team,
                config=self._config,
            )
            history.remove_manager_record(record.manager_id)
            if self._on_manager_restored:
                self._on_manager_restored(record.manager_id)
            self.refresh()
        except Exception as e:
            messagebox.showerror("복원 실패", str(e))

    def _delete_manager_record(self, record: ManagerChangeRecord):
        if not messagebox.askyesno(
            "이력 삭제",
            f"'{record.manager_name}' 변경 이력을 삭제하겠습니까?\n현재 게임 파일은 변경되지 않습니다.",
        ):
            return
        history.remove_manager_record(record.manager_id)
        self.refresh()
