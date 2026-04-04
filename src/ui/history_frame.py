"""변경 이력 화면 프레임"""

import subprocess
import threading
from pathlib import Path
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk
from PIL import Image

from src.core import history, face_changer, crest_changer
from src.core.config import Config
from src.core.face_changer import ChangeRecord
from src.core.crest_changer import CrestChangeRecord
from src.ui import font_manager as fm

_THUMB = 52  # 썸네일 픽셀 크기


def _load_thumb(path: Optional[str]) -> Optional[ctk.CTkImage]:
    """경로에서 썸네일 CTkImage 생성 (None이면 None 반환)."""
    if not path:
        return None
    try:
        img = Image.open(path).convert("RGBA")
        img.thumbnail((_THUMB, _THUMB), Image.LANCZOS)
        # 정방형 패딩
        sq = Image.new("RGBA", (_THUMB, _THUMB), (0, 0, 0, 0))
        sq.paste(img, ((_THUMB - img.width) // 2, (_THUMB - img.height) // 2))
        return ctk.CTkImage(light_image=sq, dark_image=sq, size=(_THUMB, _THUMB))
    except Exception:
        return None


def _open_folder(path: Path):
    """폴더 열기. 없으면 부모 폴더로."""
    target = path if path.exists() else path.parent
    if target.exists():
        subprocess.Popen(f'explorer "{target}"')


class HistoryFrame(ctk.CTkFrame):
    def __init__(self, master, config: Config, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._config = config
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

        if not face_records and not crest_records:
            ctk.CTkLabel(
                self._scroll, text="변경 이력이 없습니다.", text_color="gray"
            ).pack(pady=20)
            return

        # ── 미페 변경 이력 섹션 ──
        self._add_section_header(
            "미페 변경 이력",
            len(face_records),
            lambda: self._restore_all_face(face_records),
        )
        if face_records:
            for record in face_records:
                self._add_face_row(record)
        else:
            ctk.CTkLabel(
                self._scroll, text="미페 변경 이력이 없습니다.", text_color="gray",
                font=fm.font(11),
            ).pack(anchor="w", padx=16, pady=(0, 4))

        # ── 크레스트 변경 이력 섹션 ──
        self._add_section_header(
            "크레스트 변경 이력",
            len(crest_records),
            lambda: self._restore_all_crest(crest_records),
        )
        if crest_records:
            for record in crest_records:
                self._add_crest_row(record)
        else:
            ctk.CTkLabel(
                self._scroll, text="크레스트 변경 이력이 없습니다.", text_color="gray",
                font=fm.font(11),
            ).pack(anchor="w", padx=16, pady=(0, 4))

    # ──────────────────────────────────────────
    # 섹션 헤더
    # ──────────────────────────────────────────

    def _add_section_header(self, title: str, count: int, restore_all_cmd):
        header = ctk.CTkFrame(self._scroll, fg_color="transparent")
        header.pack(fill="x", pady=(12, 4))

        ctk.CTkLabel(
            header,
            text=f"{title} ({count})",
            font=fm.font(13, "bold"),
        ).pack(side="left", padx=4)

        if count > 0:
            ctk.CTkButton(
                header,
                text="전체 복원",
                width=80,
                height=26,
                fg_color="#F44336",
                hover_color="#C62828",
                font=fm.font(11),
                command=restore_all_cmd,
            ).pack(side="right", padx=4)

    # ──────────────────────────────────────────
    # 행 생성
    # ──────────────────────────────────────────

    def _add_face_row(self, record: ChangeRecord):
        row = ctk.CTkFrame(self._scroll, corner_radius=8)
        row.pack(fill="x", pady=3)
        row.columnconfigure(4, weight=1)

        # ID
        ctk.CTkLabel(
            row, text=f"p{record.spid}",
            font=fm.font(13, "bold"), width=80,
        ).grid(row=0, column=0, padx=(12, 4), pady=10, sticky="w")

        # 원본 썸네일 (백업 파일)
        before_label = self._make_thumb_label(row)
        before_label.grid(row=0, column=1, padx=4, pady=10)

        ctk.CTkLabel(row, text="→", font=fm.font(14)).grid(row=0, column=2, padx=2)

        # 변경후 썸네일 (현재 게임 파일)
        after_label = self._make_thumb_label(row)
        after_label.grid(row=0, column=3, padx=4, pady=10)

        # 날짜 정보
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=4, sticky="ew", padx=8, pady=10)
        ctk.CTkLabel(info, text=record.player_name, font=fm.font(12)).pack(anchor="w")
        ctk.CTkLabel(
            info, text=f"변경: {record.changed_at}",
            font=fm.font(11), text_color="gray",
        ).pack(anchor="w")

        # 버튼
        has_backup = bool(record.backup_path) and Path(record.backup_path).exists()
        btn = ctk.CTkButton(
            row, text="복원" if has_backup else "삭제",
            width=64, height=32,
            fg_color="#607D8B" if has_backup else "#F44336",
            hover_color="#455A64" if has_backup else "#C62828",
            font=fm.font(11),
            command=lambda r=record: self._restore_face(r),
        )
        btn.grid(row=0, column=5, padx=4, pady=10)

        backup_dir = self._config.backup_path / f"p{record.spid}"
        ctk.CTkButton(
            row, text="폴더",
            width=52, height=32,
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40"),
            text_color=("gray10", "gray90"),
            font=fm.font(11),
            command=lambda d=backup_dir: _open_folder(d),
        ).grid(row=0, column=6, padx=(0, 10), pady=10)

        # 썸네일 비동기 로드
        before_path = record.backup_path if has_backup else None
        after_path = str(self._config.face_dir / f"p{record.spid}.png")
        self._load_thumb_async(before_label, before_path)
        self._load_thumb_async(after_label, after_path)

    def _add_crest_row(self, record: CrestChangeRecord):
        row = ctk.CTkFrame(self._scroll, corner_radius=8)
        row.pack(fill="x", pady=3)
        row.columnconfigure(4, weight=1)

        # ID
        ctk.CTkLabel(
            row, text=f"c{record.crest_id}",
            font=fm.font(13, "bold"), width=80,
        ).grid(row=0, column=0, padx=(12, 4), pady=10, sticky="w")

        # 원본 썸네일 (dark/large 백업)
        before_label = self._make_thumb_label(row)
        before_label.grid(row=0, column=1, padx=4, pady=10)

        ctk.CTkLabel(row, text="→", font=fm.font(14)).grid(row=0, column=2, padx=2)

        # 변경후 썸네일 (현재 게임 파일 dark/large)
        after_label = self._make_thumb_label(row)
        after_label.grid(row=0, column=3, padx=4, pady=10)

        # 날짜 정보
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.grid(row=0, column=4, sticky="ew", padx=8, pady=10)
        src_name = Path(record.image_path).name if record.image_path else ""
        ctk.CTkLabel(info, text=src_name, font=fm.font(12)).pack(anchor="w")
        ctk.CTkLabel(
            info, text=f"변경: {record.changed_at}",
            font=fm.font(11), text_color="gray",
        ).pack(anchor="w")

        # 버튼
        has_backup = any(Path(bp).exists() for bp in record.backup_paths)
        btn = ctk.CTkButton(
            row, text="복원" if has_backup else "삭제",
            width=64, height=32,
            fg_color="#607D8B" if has_backup else "#F44336",
            hover_color="#455A64" if has_backup else "#C62828",
            font=fm.font(11),
            command=lambda r=record: self._restore_crest(r),
        )
        btn.grid(row=0, column=5, padx=4, pady=10)

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

        # 썸네일 비동기 로드
        before_path = next(
            (bp for bp in record.backup_paths
             if ("/dark/large/" in bp or "\\dark\\large\\" in bp) and Path(bp).exists()),
            None,
        )
        after_path = str(crest_changer.get_crest_file(
            self._config.crest_dir, "dark", "large", record.crest_id
        ))
        self._load_thumb_async(before_label, before_path)
        self._load_thumb_async(after_label, after_path)

    # ──────────────────────────────────────────
    # 썸네일 헬퍼
    # ──────────────────────────────────────────

    def _make_thumb_label(self, parent) -> ctk.CTkLabel:
        """빈 썸네일 플레이스홀더 레이블 생성."""
        return ctk.CTkLabel(
            parent, text="…", width=_THUMB, height=_THUMB,
            fg_color=("gray80", "gray25"), corner_radius=4,
            font=fm.font(10), text_color="gray",
        )

    def _load_thumb_async(self, label: ctk.CTkLabel, path: Optional[str]):
        if not path:
            label.configure(text="-")
            return

        def _worker():
            ctk_img = _load_thumb(path)
            if ctk_img:
                label.after(0, lambda i=ctk_img: label.configure(image=i, text=""))
            else:
                label.after(0, lambda: label.configure(text="?"))

        threading.Thread(target=_worker, daemon=True).start()

    # ──────────────────────────────────────────
    # 복원 핸들러
    # ──────────────────────────────────────────

    def _restore_face(self, record: ChangeRecord):
        has_backup = bool(record.backup_path) and Path(record.backup_path).exists()
        msg = (
            f"'{record.player_name}'의 미페를 원본으로 복원하겠습니까?"
            if has_backup
            else f"'{record.player_name}'의 교체 파일을 삭제하겠습니까?\n(백업 없음 - 게임 재실행 시 자동 복구됩니다)"
        )
        if not messagebox.askyesno("복원 확인", msg):
            return
        try:
            face_changer.restore_face(record, self._config)
            history.remove_record(record.spid)
            self.refresh()
        except Exception as e:
            messagebox.showerror("복원 실패", str(e))

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

    def _restore_all_face(self, records: list[ChangeRecord]):
        if not messagebox.askyesno(
            "전체 복원", f"변경된 미페 {len(records)}개를 모두 복원하겠습니까?"
        ):
            return
        errors = []
        for record in records:
            try:
                face_changer.restore_face(record, self._config)
                history.remove_record(record.spid)
            except Exception as e:
                errors.append(f"p{record.spid}: {e}")
        self.refresh()
        if errors:
            messagebox.showerror("일부 복원 실패", "\n".join(errors))
        else:
            messagebox.showinfo("완료", "미페 전체 복원이 완료됐습니다.")

    def _restore_all_crest(self, records: list[CrestChangeRecord]):
        if not messagebox.askyesno(
            "전체 복원", f"변경된 크레스트 {len(records)}개를 모두 복원하겠습니까?"
        ):
            return
        errors = []
        for record in records:
            try:
                crest_changer.restore_crest(record, self._config)
                history.remove_crest_record(record.crest_id)
            except Exception as e:
                errors.append(f"c{record.crest_id}: {e}")
        self.refresh()
        if errors:
            messagebox.showerror("일부 복원 실패", "\n".join(errors))
        else:
            messagebox.showinfo("완료", "크레스트 전체 복원이 완료됐습니다.")
